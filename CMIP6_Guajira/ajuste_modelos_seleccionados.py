"""
Valida las series ya corregidas (wind_bc) en `corrected/` para los 12 modelos
seleccionados, comparando contra ERA5. No aplica nuevas correcciones; solo
calcula métricas y genera gráficas. Resultados en `mod_seleccion_ajustados/`.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
ERA5_PATH = BASE.parent / "Datos_Era5" / "era5_guajira_daily_1981_2014.nc"
CORR_DIR = BASE / "corrected"
OUT_DIR = BASE / "mod_seleccion_ajustados"
PLOTS_DIR = OUT_DIR / "plots"
OUT_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

MODELOS = [
    "ACCESS-CM2",
    "CanESM5",
    "CESM2",
    "CESM2-WACCM",
    "CMCC-CM2-SR5",
    "CMCC-ESM2",
    "EC-Earth3",
    "IPSL-CM6A-LR",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MPI-ESM1-2-LR",
    "NorESM2-MM",
]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def open_wind(path: Path) -> xr.DataArray:
    """Abre un netCDF y devuelve wind_bc como DataArray sin dims extra."""
    ds = xr.open_dataset(path)
    da = ds["wind_bc"].squeeze(drop=True)
    for d in ["lat", "lon", "member_id", "dcpp_init_year"]:
        if d in da.dims and da.sizes[d] == 1:
            da = da.isel({d: 0}, drop=True)
    return da


def drop_singletons(da: xr.DataArray) -> xr.DataArray:
    for d in list(da.dims):
        if d != "time" and da.sizes[d] == 1:
            da = da.isel({d: 0}, drop=True)
    return da


def monthly_percentiles(da: xr.DataArray) -> xr.Dataset:
    p10 = da.groupby("time.month").quantile(0.1).reset_coords("quantile", drop=True)
    p50 = da.groupby("time.month").quantile(0.5).reset_coords("quantile", drop=True)
    p90 = da.groupby("time.month").quantile(0.9).reset_coords("quantile", drop=True)
    return xr.Dataset({"p10": p10, "p50": p50, "p90": p90})


def rmse_all(era: xr.DataArray, mod: xr.DataArray) -> float:
    e = drop_singletons(era).sortby("time")
    m = drop_singletons(mod).sortby("time")
    n = min(e.sizes["time"], m.sizes["time"])
    e = e.isel(time=slice(0, n))
    m = m.isel(time=slice(0, n))
    diff = m.data - e.data
    return float(np.sqrt(np.nanmean(diff**2)))


def rmse_seasonal(era: xr.DataArray, mod: xr.DataArray) -> dict:
    e = drop_singletons(era).sortby("time")
    m = drop_singletons(mod).sortby("time")
    n = min(e.sizes["time"], m.sizes["time"])
    e = e.isel(time=slice(0, n))
    m = m.isel(time=slice(0, n))
    season_months = {
        "DJF": [12, 1, 2],
        "MAM": [3, 4, 5],
        "JJA": [6, 7, 8],
        "SON": [9, 10, 11],
    }
    out = {}
    for name, months in season_months.items():
        e_s = e.where(e["time"].dt.month.isin(months), drop=True)
        m_s = m.where(m["time"].dt.month.isin(months), drop=True)
        diff = m_s.data - e_s.data
        out[name] = float(np.sqrt(np.nanmean(diff**2)))
    return out


def annual_mean(da: xr.DataArray) -> pd.Series:
    return da.groupby("time.year").mean().to_series()


def plot_percentiles(model: str, era_pct: xr.Dataset, mod_pct: xr.Dataset, out: Path):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_facecolor("#032738")
    fig.patch.set_facecolor("#032738")

    ax.plot(era_pct["p50"]["month"], era_pct["p50"], label="ERA5 P50", color="#5ec3ff")
    ax.plot(mod_pct["p50"]["month"], mod_pct["p50"], label="Modelo P50", color="#f5d76e")
    ax.fill_between(
        era_pct["p10"]["month"],
        era_pct["p10"],
        era_pct["p90"],
        color="#5ec3ff",
        alpha=0.25,
        label="ERA5 P10-90",
    )
    ax.fill_between(
        mod_pct["p10"]["month"],
        mod_pct["p10"],
        mod_pct["p90"],
        color="#f5d76e",
        alpha=0.25,
        label="Modelo P10-90",
    )
    ax.set_title(f"{model} vs ERA5 - Percentiles mensuales", color="white")
    ax.set_xlabel("Mes", color="white")
    ax.set_ylabel("Viento (m/s)", color="white")
    ax.tick_params(colors="white")
    ax.legend(facecolor="#032738", edgecolor="white", labelcolor="white")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_annual(model: str, era_ann: pd.Series, mod_ann: pd.Series, out: Path):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_facecolor("#032738")
    fig.patch.set_facecolor("#032738")

    ax.plot(era_ann.index, era_ann.values, label="ERA5", color="#5ec3ff")
    ax.plot(mod_ann.index, mod_ann.values, label="Modelo", color="#f5d76e")
    ax.set_title(f"{model} vs ERA5 - Media anual", color="white")
    ax.set_xlabel("Año", color="white")
    ax.set_ylabel("Viento (m/s)", color="white")
    ax.tick_params(colors="white")
    ax.legend(facecolor="#032738", edgecolor="white", labelcolor="white")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Flujo principal
# --------------------------------------------------------------------------- #
def main():
    era = xr.open_dataset(ERA5_PATH)["wind10"].squeeze(drop=True)
    era_pct = monthly_percentiles(era)
    era_ann = annual_mean(era)

    rows = []

    for model in MODELOS:
        fname = CORR_DIR / f"{model}_historical_wind_bc.nc"
        if not fname.exists():
            print(f"[WARN] No se encontró {fname}, se omite.")
            continue

        wind = open_wind(fname)
        mod_pct = monthly_percentiles(wind)

        rmse_total = rmse_all(era, wind)
        rmse_seas = rmse_seasonal(era, wind)
        rows.append(
            {
                "model": model,
                "rmse_mean_allmonths": rmse_total,
                "rmse_DJF": rmse_seas["DJF"],
                "rmse_MAM": rmse_seas["MAM"],
                "rmse_JJA": rmse_seas["JJA"],
                "rmse_SON": rmse_seas["SON"],
            }
        )

        ann_mod = annual_mean(wind)
        plot_percentiles(
            model,
            era_pct,
            mod_pct,
            PLOTS_DIR / f"{model}_percentiles.png",
        )
        plot_annual(
            model,
            era_ann,
            ann_mod,
            PLOTS_DIR / f"{model}_anual.png",
        )

    metrics_path = OUT_DIR / "metrics_models_ajust.csv"
    if metrics_path.exists():
        metrics_path = OUT_DIR / "metrics_models_ajust_new.csv"
    pd.DataFrame(rows).to_csv(metrics_path, index=False)
    print(f"[OK] Gráficas y métricas guardadas en {OUT_DIR} (métricas: {metrics_path.name}, filas={len(rows)})")


if __name__ == "__main__":
    main()
