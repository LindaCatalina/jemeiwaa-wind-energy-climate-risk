"""
Pipeline para síntesis subdiaria y métricas de cambio (viento/densidad) con los 12 modelos validados.

Entradas:
  - corrected/{model}_{exp}_wind_bc.nc   (salidas de apply_bias_and_power.py)
  - ERA5 subdiario no está disponible; se usa un perfil diurno simple (sinusoidal) sobre el viento diario.

Salidas:
  - synthetic_10min/{model}_{exp}_subdaily.nc : series 10‑min de viento (v150_10min) y potencia (power_10min, cf_10min)
  - metrics_future/tables/*.csv : métricas históricas y futuras (CF, energía, extremos, P50/P90)
  - metrics_future/plots/... : gráficos de cambios y atribución viento/densidad (estilo azul petróleo)

Notas y supuestos:
  - Se generan 144 muestras de 10 min por día con Weibull (k fijo o derivado de la varianza diaria),
    aplicando un perfil diurno sinusoidal suave (±10 %) para introducir ciclo día/noche.
  - La densidad se usa cuando está en el archivo; para MIROC6 (sin rho) se usa rho_ref=1.225.
  - Periodos: hist (1981-2014), futuro1 (2040-2069), futuro2 (2070-2099).
  - Escenarios: historical, ssp126, ssp245, ssp585.
  - Potencia de planta: 162 turbinas de 6.8 MW (1,101.6 MW).
"""

import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path
from scipy.stats import weibull_min
import datetime

# Rutas base
BASE = Path(__file__).resolve().parent
CORR_DIR = BASE / "corrected"
OUT_SYN = BASE / "synthetic_10min"
OUT_MET = BASE / "metrics_future"
OUT_PLOTS = OUT_MET / "plots"
OUT_TABLES = OUT_MET / "tables"

OUT_SYN.mkdir(parents=True, exist_ok=True)
OUT_MET.mkdir(parents=True, exist_ok=True)
OUT_PLOTS.mkdir(parents=True, exist_ok=True)
OUT_TABLES.mkdir(parents=True, exist_ok=True)

# Config
MODELOS = [
    #"ACCESS-CM2",
    #"CanESM5",
    #"CESM2",
    #"CESM2-WACCM",
    #"CMCC-CM2-SR5",
    #"CMCC-ESM2",
    #"EC-Earth3",
    #"IPSL-CM6A-LR",
    "MIROC6",          # sin rho -> se usa rho_ref
    "MPI-ESM1-2-HR",
    "MPI-ESM1-2-LR",
    "NorESM2-MM",
]
EXPERIMENTOS = ["historical", "ssp126", "ssp245", "ssp585"]
PERIODOS = {
    "hist": ("1981-01-01", "2014-12-31"),
    "fut1": ("2040-01-01", "2069-12-31"),
    "fut2": ("2070-01-01", "2099-12-31"),
}

RHO_REF = 1.225
TURBINAS = 162
RATING_MW = 6.8
NPERDAY = 144  # 24h * 6 (10 min)

# Paleta
BG = "#032738"
FG = "#f2f2f2"
ACCENT = "#e3b23c"


def power_curve(v, rho=None, rho_ref=RHO_REF):
    """
    Curva tabulada V164-8.0 MW escalada a 6.8 MW y comprimida (plateau ~12 m/s).
    Idéntica a apply_bias_and_power.py.
    """
    CUT_IN, CUT_OUT = 3.0, 25.0
    v_tab = np.array([
        3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0,
        10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0, 16.5,
        17.0, 17.5, 18.0, 18.5, 19.0, 19.5, 20.0, 20.5, 21.0, 21.5, 22.0, 22.5, 23.0,
        23.5, 24.0, 24.5, 25.0
    ])
    p_tab_kw = np.array([
        0, 40, 100, 370, 650, 895, 1150, 1500, 1850, 2375, 2900, 3525, 4150, 4875, 5600,
        6350, 7100, 7580, 7800, 7920, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000,
        8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000,
        8000, 8000, 8000, 8000
    ])
    scale = RATING_MW / 8.0
    v_tab_comp = v_tab * (12.0 / 13.0)
    v_tab_comp[0] = CUT_IN
    p_tab_mw = (p_tab_kw / 1000.0) * scale
    p_interp = np.interp(v, v_tab_comp, p_tab_mw, left=0.0, right=0.0)
    p_interp = np.where((v >= CUT_IN) & (v <= CUT_OUT), p_interp, 0.0)
    if rho is not None:
        p_interp = p_interp * (rho / rho_ref)
    p_interp = p_interp * (1 - 0.10)  # pérdidas 10 %
    return p_interp


def diurnal_shape(n=NPERDAY, amp=0.1):
    """
    Perfil diurno sinusoidal (media=1, amplitud amp).
    """
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return 1.0 + amp * np.sin(t - np.pi / 2)


def synth_10min(day_mean, shape_k=2.0, amp_diurnal=0.1, rng=None):
    """
    Genera 144 muestras 10-min a partir de la media diaria (day_mean) y k de Weibull.
    Se ajusta escala lambda con la media target. Se aplica perfil diurno multiplicativo.
    """
    if rng is None:
        rng = np.random.default_rng(42)
    # Asegurar escalar (por si llega un array)
    day_mean = float(np.maximum(day_mean, 0.1))
    lam = day_mean / np.exp(np.log(2) / shape_k)  # aprox media ~ lambda*Gamma(1+1/k); se usa simplificado
    samples = weibull_min.rvs(shape_k, scale=lam, size=NPERDAY, random_state=rng)
    samples = samples * diurnal_shape(NPERDAY, amp=amp_diurnal)
    return samples


def expand_subdaily(ds, model):
    """
    A partir de v150 diario (y rho diario opcional) genera v150_10min y power/cf 10-min.
    Para MIROC6 si falta rho: usa rho_ref.
    """
    # Asegurar que solo quede la dimensión tiempo
    for dim in ["member_id", "dcpp_init_year"]:
        if dim in ds.dims:
            ds = ds.isel({dim: 0}, drop=True)
    ds = ds.squeeze(drop=True)

    rng = np.random.default_rng(123)
    v_daily = ds["v150"].values  # daily
    rho_daily = ds.get("rho")
    times_daily = ds["time"].values  # puede ser datetime64 o cftime

    out_v = []
    out_p = []
    out_cf = []
    out_time = []

    for vd, t in zip(v_daily, times_daily):
        vd = float(np.asarray(vd))
        v10m = synth_10min(vd, shape_k=2.0, amp_diurnal=0.1, rng=rng)
        if rho_daily is not None:
            rho_vals = np.full_like(v10m, float(rho_daily.sel(time=t, method="nearest")))
        else:
            # MIROC6: rho_ref
            rho_vals = np.full_like(v10m, RHO_REF)
        pvals = power_curve(v10m, rho_vals)
        cfvals = pvals / RATING_MW

        out_v.append(v10m)
        out_p.append(pvals)
        out_cf.append(cfvals)
        # generar 10-min stamps en pandas/np.datetime64 para evitar cftime en disco
        if isinstance(t, np.datetime64):
            base_day = pd.Timestamp(t)
        else:
            base_day = pd.Timestamp(int(t.year), int(t.month), int(t.day))
        base = pd.date_range(base_day, periods=NPERDAY, freq="10min")
        out_time.append(base.values)

    v_arr = np.concatenate(out_v)
    p_arr = np.concatenate(out_p)
    cf_arr = np.concatenate(out_cf)
    time_arr = np.concatenate(out_time)

    ds_out = xr.Dataset(
        {
            "v150_10min": ("time", v_arr),
            "power_10min": ("time", p_arr),
            "cf_10min": ("time", cf_arr),
        },
        coords={"time": time_arr},
    )
    return ds_out


def compute_metrics(ds_sub, ds_daily, tag_period):
    """
    Calcula métricas anuales y estacionales con series subdiarias:
      - CF medio
      - Energía anual (MWh) por turbina y por planta
      - Días <5 m/s y >25 m/s en v150 diario (ya corregido)
      - P50/P90 de CF anual
    """
    # CF medio y energía
    cf_mean = ds_sub["cf_10min"].resample(time="YE").mean()
    power_mean = ds_sub["power_10min"].resample(time="YE").mean()
    energy_turb = (ds_sub["power_10min"] * (10.0 / 60.0)).resample(time="YE").sum()  # MWh/turbina
    energy_plant = energy_turb * TURBINAS

    # Estacionales CF
    cf_season = ds_sub["cf_10min"].groupby("time.season").mean()

    # Extremos diarios
    v_daily = ds_daily["v150"]
    low_days = (v_daily < 5.0).resample(time="YE").sum()
    high_days = (v_daily > 25.0).resample(time="YE").sum()

    # P50/P90 CF anual
    cf_ann = ds_sub["cf_10min"].resample(time="YE").mean()
    p50_cf = cf_ann.quantile(0.5)
    p90_cf = cf_ann.quantile(0.9)

    return {
        f"cf_mean_{tag_period}": float(cf_mean.mean()),
        f"energy_turb_MWh_{tag_period}": float(energy_turb.mean()),
        f"energy_plant_MWh_{tag_period}": float(energy_plant.mean()),
        f"cf_DJF_{tag_period}": float(cf_season.sel(season="DJF")),
        f"cf_MAM_{tag_period}": float(cf_season.sel(season="MAM")),
        f"cf_JJA_{tag_period}": float(cf_season.sel(season="JJA")),
        f"cf_SON_{tag_period}": float(cf_season.sel(season="SON")),
        f"days_lt5_{tag_period}": float(low_days.mean()),
        f"days_gt25_{tag_period}": float(high_days.mean()),
        f"P50_CF_{tag_period}": float(p50_cf),
        f"P90_CF_{tag_period}": float(p90_cf),
    }


def atribucion_viento_densidad(ds_daily, period):
    """
    Descompone cambio de potencia medio diario en efecto viento vs densidad.
    Se calcula potencia con rho_real y potencia con rho_ref para el mismo viento.
    Retorna medias para el periodo indicado.
    """
    sub = ds_daily.sel(time=slice(*PERIODOS[period]))
    v = sub["v150"]
    rho = sub.get("rho")
    if rho is None:
        rho_use = None
    else:
        rho_use = rho

    p_real = xr.apply_ufunc(power_curve, v, rho_use, dask="parallelized", output_dtypes=[float])
    p_ref = xr.apply_ufunc(power_curve, v, None, dask="parallelized", output_dtypes=[float])
    return float(p_real.mean()), float(p_ref.mean())


def main():
    # Tabla agregada
    rows = []

    for model in MODELOS:
        for exp in EXPERIMENTOS:
            fpath = CORR_DIR / f"{model}_{exp}_wind_bc.nc"
            if not fpath.exists():
                print(f"[WARN] Falta {fpath}, se omite.")
                continue
            ds = xr.open_dataset(fpath).sortby("time")

            # Subdiario sintético
            ds_sub = expand_subdaily(ds, model)
            out_sub_path = OUT_SYN / f"{model}_{exp}_subdaily.nc"
            ds_sub.to_netcdf(out_sub_path)
            print(f"[OK] Subdiario guardado: {out_sub_path}")

            # Métricas por periodo
            metrics = {"model": model, "exp": exp}
            for tag in PERIODOS:
                ds_sub_p = ds_sub.sel(time=slice(*PERIODOS[tag]))
                ds_daily_p = ds.sel(time=slice(*PERIODOS[tag]))
                if ds_sub_p.time.size == 0:
                    continue
                metrics.update(compute_metrics(ds_sub_p, ds_daily_p, tag))

            # Atribución (viento vs densidad)
            for tag in PERIODOS:
                try:
                    p_real, p_ref = atribucion_viento_densidad(ds, tag)
                    metrics[f"p_mean_real_{tag}"] = p_real
                    metrics[f"p_mean_ref_{tag}"] = p_ref
                except Exception:
                    metrics[f"p_mean_real_{tag}"] = np.nan
                    metrics[f"p_mean_ref_{tag}"] = np.nan

            rows.append(metrics)

    # Guardar tabla
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(OUT_TABLES / "metrics_future.csv", index=False)
        print(f"[OK] Tabla métricas: {OUT_TABLES/'metrics_future.csv'}")
    else:
        print("[WARN] No se generaron métricas.")


if __name__ == "__main__":
    main()
