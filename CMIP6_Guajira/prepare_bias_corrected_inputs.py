"""Prepara los insumos climÃ¡ticos diarios del mÃ©todo con recentrado.

Aplica el Quantile Mapping mensual original, extrapola el viento a 150 m y
calcula densidad cuando existen presiÃ³n y temperatura. Deliberadamente no
calcula potencia ni CF: aplicar una curva no lineal al viento diario fue una
de las fuentes de inconsistencia detectadas. Ese cÃ¡lculo se realiza solamente
mediante la integraciÃ³n subdiaria de ``reproducibilidad/core.py``.

Producto generado: ``corrected/{modelo}_{experimento}_wind_bc.nc`` con ``wind_bc``,
``v150`` y, cuando estÃ¡ disponible, ``rho``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


CMIP6_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CMIP6_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reproducibilidad.config import (  # noqa: E402
    ALPHA,
    CANONICAL_MODELS,
    EXPERIMENTS,
    RHO_REF,
    Z_HUB_M,
    Z_REF_M,
)
from reproducibilidad.core import as_time_series, open_netcdf_robust  # noqa: E402


BIAS_DIR = CMIP6_DIR / "bias_factors"
OUT_DIR = CMIP6_DIR / "corrected"
RD = 287.05
PROBABILITIES = np.array([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
QUANTILE_COLUMNS = ["p5", "p10", "p25", "p50", "p75", "p90", "p95"]


def load_quantiles(model: str) -> dict[int, tuple[np.ndarray, np.ndarray]] | None:
    """Lee cuantiles mensuales y devuelve ``mes: (modelo, ERA5)``."""
    path = BIAS_DIR / f"{model}_quantiles.csv"
    if not path.is_file():
        return None
    frame = pd.read_csv(path)
    result: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for month in range(1, 13):
        model_row = frame[(frame["month"] == month) & (frame["source"] == "model")]
        era5_row = frame[(frame["month"] == month) & (frame["source"] == "era5")]
        if len(model_row) != 1 or len(era5_row) != 1:
            raise ValueError(f"Cuantiles incompletos para {model}, mes {month}")
        q_model = model_row[QUANTILE_COLUMNS].iloc[0].to_numpy(float)
        q_era5 = era5_row[QUANTILE_COLUMNS].iloc[0].to_numpy(float)
        result[month] = (q_model, q_era5)
    return result


def _load_series(pattern: str, variable: str) -> xr.DataArray | None:
    matches = sorted(CMIP6_DIR.glob(pattern))
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(f"MÃ¡s de un archivo coincide con {pattern}: {matches}")
    dataset = open_netcdf_robust(matches[0])
    try:
        return as_time_series(dataset[variable]).load()
    finally:
        dataset.close()


def load_climate_inputs(
    model: str, experiment: str
) -> tuple[xr.DataArray | None, xr.DataArray | None, xr.DataArray | None]:
    """Carga viento y, cuando existen, temperatura y presiÃ³n."""
    wind = _load_series(f"{model}_{experiment}_sfcWind_*_guajira.nc", "sfcWind")
    if wind is None:
        uas = _load_series(f"{model}_{experiment}_uas_*_guajira.nc", "uas")
        vas = _load_series(f"{model}_{experiment}_vas_*_guajira.nc", "vas")
        if uas is not None and vas is not None:
            uas, vas = xr.align(uas, vas, join="inner")
            wind = np.hypot(uas, vas).rename("sfcWind")
    tas = _load_series(f"{model}_{experiment}_tas_*_guajira.nc", "tas")
    ps = _load_series(f"{model}_{experiment}_ps_*_guajira.nc", "ps")
    return wind, tas, ps


def bias_correct_qm_recentered(
    wind: xr.DataArray,
    quantiles: dict[int, tuple[np.ndarray, np.ndarray]],
) -> xr.DataArray:
    """Reproduce el QM original y su recentrado mensual posterior.

    Este tratamiento se mantiene solo como sensibilidad metodolÃ³gica. El
    resultado principal utiliza colas aditivas y no recentra el futuro.
    """
    series = as_time_series(wind)
    values = np.asarray(series.values, dtype=float)
    months = np.asarray(series["time"].dt.month.values, dtype=int)
    corrected = np.empty_like(values, dtype=float)

    for month in range(1, 13):
        mask = months == month
        q_model, q_era5 = quantiles[month]
        q_model = np.maximum.accumulate(q_model)
        q_era5 = np.maximum.accumulate(q_era5)
        probability = np.interp(
            values[mask],
            q_model,
            PROBABILITIES,
            left=PROBABILITIES[0],
            right=PROBABILITIES[-1],
        )
        mapped = np.interp(probability, PROBABILITIES, q_era5)
        mapped += q_era5[3] - np.median(mapped)
        corrected[mask] = mapped

    return xr.DataArray(
        corrected,
        dims=("time",),
        coords={"time": series["time"]},
        name="wind_bc",
        attrs={
            "units": "m s-1",
            "bias_correction": "monthly empirical quantile mapping with bounded tails",
            "future_recentering": "monthly median aligned to historical ERA5 P50",
            "role": "methodological sensitivity, not primary result",
        },
    )


def extrapolate_to_hub(wind_10m: xr.DataArray) -> xr.DataArray:
    factor = (Z_HUB_M / Z_REF_M) ** ALPHA
    return (wind_10m * factor).rename("v150")


def interpolate_density(
    pressure: xr.DataArray | None,
    temperature: xr.DataArray | None,
    target_time: xr.DataArray,
) -> xr.DataArray | None:
    if pressure is None or temperature is None:
        return None
    try:
        pressure_daily = pressure.interp(time=target_time)
        temperature_daily = temperature.interp(time=target_time)
    except Exception as exc:
        print(f"[WARN] No se pudo interpolar ps/tas: {exc}")
        return None
    density = (pressure_daily / (RD * temperature_daily)).rename("rho")
    if int(density.notnull().sum()) == 0:
        return None
    return density.fillna(RHO_REF)


def process_model(
    model: str,
    quantiles: dict[int, tuple[np.ndarray, np.ndarray]],
) -> None:
    """Genera los cuatro insumos diarios de un modelo canÃ³nico."""
    OUT_DIR.mkdir(exist_ok=True)
    for experiment in EXPERIMENTS:
        print(f"[INFO] {model} {experiment}: preparando viento y densidad diarios")
        wind, temperature, pressure = load_climate_inputs(model, experiment)
        if wind is None:
            raise FileNotFoundError(f"No hay viento para {model} {experiment}")
        wind_bc = bias_correct_qm_recentered(wind, quantiles).sortby("time")
        v150 = extrapolate_to_hub(wind_bc)
        density = interpolate_density(pressure, temperature, wind_bc["time"])

        output = xr.Dataset({"wind_bc": wind_bc, "v150": v150})
        if density is not None:
            output["rho"] = density
        output.attrs["product_role"] = (
            "daily climate input; power and CF are computed with the subdaily "
            "integration in scripts/run_analysis.py"
        )
        output = output.sortby("time").chunk({"time": 90})
        destination = OUT_DIR / f"{model}_{experiment}_wind_bc.nc"
        if destination.exists():
            destination.unlink()
        output.to_netcdf(destination, mode="w")
        print(f"[OK] Guardado {destination.name}")


def main() -> int:
    print(f"[INFO] Ensamble canÃ³nico fijo: {len(CANONICAL_MODELS)} modelos")
    for model in CANONICAL_MODELS:
        quantiles = load_quantiles(model)
        if quantiles is None:
            raise FileNotFoundError(f"Faltan cuantiles para {model}")
        process_model(model, quantiles)
    print("[FIN] Insumos diarios corregidos completados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
