"""
Validación y factores de corrección (media/σ y quantile mapping) CMIP6 vs ERA5.

Entrada:
  - ERA5 consolidado: Datos_Era5/era5_guajira_daily_1981_2014.nc (usa wind10).
  - Archivos CMIP6 en CMIP6_Guajira/ con patrón *_historical_*_guajira.nc.

Salida:
  - CSV por modelo con climatología mensual, RMSE y factores media/σ.
  - CSV con cuantiles mensuales (para quantile mapping) por modelo.

Nota: no aplica aún las correcciones a las series; genera factores para usarlos
      luego sobre históricos y futuros.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

# Rutas
ROOT = Path(__file__).resolve().parent
ERA5_PATH = ROOT.parent / "Datos_Era5" / "era5_guajira_daily_1981_2014.nc"
CMIP_DIR = ROOT
OUT_DIR = ROOT / "bias_factors"
OUT_DIR.mkdir(exist_ok=True)

# Percentiles para quantile mapping
PCTS = [5, 10, 25, 50, 75, 90, 95]


def add_date_coord(da):
    """
    Agrega coordenada 'date' (datetime64 diaria) para poder alinear ERA5 (datetime64)
    con CMIP6 (cftime). Usa strftime para cftime y normaliza a fecha sin hora.
    """
    t = da["time"].values
    if np.issubdtype(da["time"].dtype, np.datetime64):
        dates = pd.to_datetime(t).normalize()
    else:
        # Convierte cftime a string YYYY-MM-DD y luego a datetime64; invalidez -> NaT
        dates = pd.to_datetime(
            [getattr(x, "strftime", lambda fmt: "")("%Y-%m-%d") for x in t],
            errors="coerce",
        ).normalize()
    # Elimina entradas con fechas inválidas
    valid_mask = ~pd.isnull(dates)
    da = da.isel(time=valid_mask)
    dates = dates[valid_mask]
    da = da.assign_coords(date=("time", dates)).swap_dims({"time": "date"}).drop_vars("time")
    da = da.sortby("date")
    return da


def load_era5():
    """Carga ERA5 y devuelve el viento diario (wind10) con coordenada 'date'."""
    ds = xr.open_dataset(ERA5_PATH)
    if "wind10" not in ds:
        ds["wind10"] = np.hypot(ds["u10"], ds["v10"])
    ds = ds.sortby("time")
    ds = add_date_coord(ds[["wind10"]])
    return ds


def parse_model(fname: Path):
    """Extrae source_id del nombre de archivo CMIP6."""
    stem = fname.name[:-3]  # quitar .nc
    if not stem.endswith("_guajira"):
        return None
    stem = stem[:-8]
    parts = stem.split("_")
    if len(parts) < 5:
        return None
    member_id = parts[-1]
    table_id = parts[-2]
    variable_id = parts[-3]
    experiment_id = parts[-4]
    source_id = "_".join(parts[:-4])
    return source_id, experiment_id, variable_id, table_id, member_id


def load_cmip_hist(model: str):
    """Carga histórico CMIP6 para un modelo y devuelve viento diario con 'date'."""
    # Preferimos sfcWind; si no, calculamos con uas/vas.
    files = list(CMIP_DIR.glob(f"{model}_historical_sfcWind_*_guajira.nc"))
    if files:
        ds = xr.open_dataset(files[0], use_cftime=True)
        wind = ds["sfcWind"]
    else:
        uas = list(CMIP_DIR.glob(f"{model}_historical_uas_*_guajira.nc"))
        vas = list(CMIP_DIR.glob(f"{model}_historical_vas_*_guajira.nc"))
        if not uas or not vas:
            return None
        dsu = xr.open_dataset(uas[0], use_cftime=True)
        dsv = xr.open_dataset(vas[0], use_cftime=True)
        wind = np.hypot(dsu["uas"], dsv["vas"])
    wind = wind.sortby("time")
    # Recorta al rango 1981-2014 usando dt.year (sirve para calendarios 360d/365d)
    if "time" in wind.coords:
        year_mask = (wind["time"].dt.year >= 1981) & (wind["time"].dt.year <= 2014)
        wind = wind.where(year_mask, drop=True)
    # Si tras el recorte no queda nada, devolvemos None
    if wind.sizes.get("time", 0) == 0:
        return None
    # Asegura que el nombre sea consistente y agrega 'date'
    wind = wind.rename("wind")
    wind = add_date_coord(wind.to_dataset())["wind"]
    return wind


def monthly_stats(da):
    """Devuelve media, std y percentiles mensuales."""
    grp = da.groupby("date.month")
    mean = grp.mean().squeeze(drop=True)  # elimina lat/lon de tamaño 1
    std = grp.std().squeeze(drop=True)
    q = xr.concat([grp.quantile(p / 100.0) for p in PCTS], dim="pct").squeeze(drop=True)
    q = q.assign_coords(pct=("pct", PCTS))
    return mean, std, q


def rmse_monthly(model_da, ref_da):
    """RMSE mensual entre modelo y referencia (usando medias mensuales)."""
    m_mean = model_da.groupby("date.month").mean()
    r_mean = ref_da.groupby("date.month").mean()
    diff = m_mean - r_mean
    return np.sqrt((diff ** 2).mean("month"))


def process_model(model, era):
    wind = load_cmip_hist(model)
    if wind is None:
        print(f"[WARN] No se encontró histórico adecuado para {model}")
        return

    # Alinear tiempos (intersección)
    wind, ref = xr.align(wind, era["wind10"], join="inner")
    if wind.date.size == 0:
        print(f"[WARN] Sin solape temporal para {model}")
        return

    # Estadísticos mensuales
    m_mean, m_std, m_q = monthly_stats(wind)
    e_mean, e_std, e_q = monthly_stats(ref)

    # Factores media/σ
    factor_mean = (e_mean / m_mean).to_series()
    factor_std = (e_std / m_std).to_series()

    # RMSE mensual (sobre medias mensuales)
    rmse = rmse_monthly(wind, ref).item()

    # DataFrame resumen mensual
    df = pd.DataFrame({
        "era_mean": e_mean.values,
        "model_mean": m_mean.values,
        "mean_ratio": factor_mean.values,
        "era_std": e_std.values,
        "model_std": m_std.values,
        "std_ratio": factor_std.values,
    }, index=e_mean["month"].values)
    df.index.name = "month"
    df["rmse_mean_allmonths"] = rmse

    # Guardar CSV factores
    out_csv = OUT_DIR / f"{model}_bias_factors.csv"
    df.to_csv(out_csv)

    # Guardar cuantiles mensuales asegurando monotonicidad p5<p10<...<p95
    cols = [f"p{p}" for p in PCTS]

    def make_q(df_raw: pd.DataFrame, source: str):
        df = df_raw.copy()
        df.columns = cols
        arr = np.maximum.accumulate(df.values, axis=1)  # fuerza orden ascendente
        df_out = pd.DataFrame(arr, index=df.index, columns=cols)
        df_out["source"] = source
        return df_out

    q_mod_df = m_q.transpose("month", "pct").to_pandas()
    q_era_df = e_q.transpose("month", "pct").to_pandas()
    qm_model = make_q(q_mod_df, "model")
    qm_era = make_q(q_era_df, "era5")
    qm_all = pd.concat([qm_model, qm_era])
    qm_all.index.name = "month"
    qm_all = qm_all.reset_index().set_index(["month", "source"])
    out_qm = OUT_DIR / f"{model}_quantiles.csv"
    qm_all.to_csv(out_qm)

    print(f"[OK] Factores guardados para {model}: {out_csv.name}, {out_qm.name}")


def main():
    print("[INFO] Cargando ERA5...")
    era = load_era5()

    # Detecta modelos históricos disponibles
    models = set()
    for f in CMIP_DIR.glob("*_historical_*_guajira.nc"):
        parsed = parse_model(f)
        if parsed is None:
            continue
        source_id, experiment_id, variable_id, table_id, member_id = parsed
        if experiment_id == "historical":
            models.add(source_id)

    if not models:
        print("[ERROR] No se encontraron modelos históricos en CMIP6_Guajira.")
        return

    print(f"[INFO] Modelos a procesar: {len(models)}")
    for m in sorted(models):
        process_model(m, era)

    print("[FIN] Validación y factores generados.")


if __name__ == "__main__":
    main()
