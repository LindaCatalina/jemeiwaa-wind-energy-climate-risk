"""Funciones científicas compartidas por la auditoría y los percentiles.

La función de potencia conserva deliberadamente la aproximación utilizada en
el trabajo original (curva V164-8 MW escalada y comprimida). No se presenta
como una curva oficial V172: se mantiene para que las comparaciones sean
trazables con los resultados legados.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from .config import (
    ALPHA,
    CMIP6_DIR,
    LOSSES,
    RATING_MW,
    RHO_REF,
    Z_HUB_M,
    Z_REF_M,
)


def open_netcdf_robust(path: Path) -> xr.Dataset:
    """Abre NetCDF y evita que bounds defectuosos impidan decodificar time."""
    raw = xr.open_dataset(path, decode_times=False)
    raw = raw.drop_vars(
        [
            name
            for name in ("time_bnds", "time_bounds", "lat_bnds", "lon_bnds")
            if name in raw
        ],
        errors="ignore",
    )
    try:
        return xr.decode_cf(raw)
    except Exception:
        coder = xr.coders.CFDatetimeCoder(use_cftime=True)
        return xr.decode_cf(raw, decode_times=coder)


def as_time_series(da: xr.DataArray) -> xr.DataArray:
    """Deja únicamente la dimensión temporal, sin seleccionar datos ambiguos."""
    da = da.squeeze(drop=True)
    for dim in list(da.dims):
        if dim == "time":
            continue
        if da.sizes[dim] != 1:
            raise ValueError(f"Dimensión no temporal no singular: {dim}={da.sizes[dim]}")
        da = da.isel({dim: 0}, drop=True)
    if da.dims != ("time",):
        raise ValueError(f"Se esperaba una serie temporal; dimensiones={da.dims}")
    return da.sortby("time")


def raw_wind_path(model: str, experiment: str) -> Path:
    matches = sorted(CMIP6_DIR.glob(f"{model}_{experiment}_sfcWind_*_guajira.nc"))
    if not matches:
        raise FileNotFoundError(f"Falta sfcWind para {model} {experiment}")
    if len(matches) > 1:
        raise RuntimeError(f"Más de un sfcWind para {model} {experiment}: {matches}")
    return matches[0]


def load_raw_wind(model: str, experiment: str) -> xr.DataArray:
    ds = open_netcdf_robust(raw_wind_path(model, experiment))
    try:
        wind = as_time_series(ds["sfcWind"]).load()
    finally:
        ds.close()
    return wind


def load_quantiles(model: str) -> pd.DataFrame:
    path = CMIP6_DIR / "bias_factors" / f"{model}_quantiles.csv"
    df = pd.read_csv(path)
    expected = {"month", "source", "p5", "p10", "p25", "p50", "p75", "p90", "p95"}
    missing = expected.difference(df.columns)
    if missing:
        raise ValueError(f"Columnas ausentes en {path.name}: {sorted(missing)}")
    return df


def trend_preserving_qm(wind: xr.DataArray, quantiles: pd.DataFrame) -> xr.DataArray:
    """EQM mensual con corrección aditiva constante en las colas.

    A diferencia del script legado, no recentra cada escenario futuro a la
    mediana histórica. Por eso conserva la señal climática proyectada. Las
    colas usan el sesgo del P5/P95 en vez de colapsar todos los extremos a un
    único valor. El viento se limita físicamente a valores no negativos.
    """
    values = np.asarray(wind.values, dtype=float)
    months = np.asarray(wind["time"].dt.month.values, dtype=int)
    corrected = np.empty_like(values, dtype=float)
    qcols = ["p5", "p10", "p25", "p50", "p75", "p90", "p95"]

    for month in range(1, 13):
        mask = months == month
        model_row = quantiles[
            (quantiles["month"] == month) & (quantiles["source"] == "model")
        ]
        era_row = quantiles[
            (quantiles["month"] == month) & (quantiles["source"] == "era5")
        ]
        if len(model_row) != 1 or len(era_row) != 1:
            raise ValueError(f"Cuantiles incompletos para mes={month}")
        q_model = np.maximum.accumulate(model_row[qcols].iloc[0].to_numpy(float))
        q_era = np.maximum.accumulate(era_row[qcols].iloc[0].to_numpy(float))
        delta = q_era - q_model
        corrected[mask] = values[mask] + np.interp(
            values[mask], q_model, delta, left=delta[0], right=delta[-1]
        )

    corrected = np.maximum(corrected, 0.0)
    return xr.DataArray(
        corrected,
        dims=("time",),
        coords={"time": wind["time"]},
        name="wind_bc_trend_preserving",
        attrs={
            "units": "m s-1",
            "bias_correction": "monthly empirical quantile mapping; additive constant tails",
            "future_recentering": "none",
        },
    )


def extrapolate_to_hub(wind_10m: xr.DataArray) -> xr.DataArray:
    factor = (Z_HUB_M / Z_REF_M) ** ALPHA
    return (wind_10m * factor).rename("v150")


_V_TABLE = np.array(
    [
        3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5,
        8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 12.5,
        13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0, 16.5, 17.0,
        17.5, 18.0, 18.5, 19.0, 19.5, 20.0, 20.5, 21.0, 21.5,
        22.0, 22.5, 23.0, 23.5, 24.0, 24.5, 25.0,
    ]
)
_P_TABLE_KW = np.array(
    [
        0, 40, 100, 370, 650, 895, 1150, 1500, 1850, 2375, 2900,
        3525, 4150, 4875, 5600, 6350, 7100, 7580, 7800, 7920,
        *([8000] * 25),
    ]
)


def proxy_power_curve_mw(v_hub: xr.DataArray, rho: xr.DataArray | float = RHO_REF) -> xr.DataArray:
    """Curva aproximada legada, con pérdidas y ajuste de densidad explícitos."""
    v_comp = _V_TABLE * (12.0 / 13.0)
    v_comp[0] = 3.0
    p_mw = (_P_TABLE_KW / 1000.0) * (RATING_MW / 8.0)
    values = np.interp(np.asarray(v_hub.values), v_comp, p_mw, left=0.0, right=0.0)
    values = np.where(
        (np.asarray(v_hub.values) >= 3.0) & (np.asarray(v_hub.values) <= 25.0),
        values,
        0.0,
    )
    rho_values = np.asarray(rho.values if isinstance(rho, xr.DataArray) else rho)
    values = values * (rho_values / RHO_REF) * (1.0 - LOSSES)
    return xr.DataArray(values, dims=v_hub.dims, coords=v_hub.coords, name="power_MW")


def cf_from_wind_reference_density(wind_10m: xr.DataArray) -> xr.DataArray:
    power = proxy_power_curve_mw(extrapolate_to_hub(wind_10m), RHO_REF)
    return (power / RATING_MW).rename("cf")


def year_values(da: xr.DataArray) -> np.ndarray:
    return np.asarray(da["time"].dt.year.values, dtype=int)


def month_values(da: xr.DataArray) -> np.ndarray:
    return np.asarray(da["time"].dt.month.values, dtype=int)

