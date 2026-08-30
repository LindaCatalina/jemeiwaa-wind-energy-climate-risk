"""
Unifica ERA5-Land diarios (1981-2014) para el píxel de La Guajira.
Entrada: archivos por año y variable en esta carpeta:
  - era5land_diario_guajira_10m_u_component_of_wind_*.nc
  - era5land_diario_guajira_10m_v_component_of_wind_*.nc
  - era5land_diario_guajira_2m_temperature_*.nc
  - era5land_diario_guajira_surface_pressure_*.nc
Salida: Datos_Era5/era5_guajira_daily_1981_2014.nc con variables:
  u10, v10, wind10, t2m, sp, opcional dir10
"""

import xarray as xr
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
OUT_PATH = DATA_DIR / "era5_guajira_daily_1981_2014.nc"


def open_var(pattern, var_name):
    """Abre y concatena por tiempo usando un patrón glob (dropping valid_time si existe)."""
    files = sorted(DATA_DIR.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos para {pattern}")
    datasets = []
    for f in files:
        ds = xr.open_dataset(f, decode_times=True)
        # Renombra valid_time -> time si aplica
        if "valid_time" in ds.coords:
            ds = ds.rename({"valid_time": "time"})
        elif "valid_time" in ds.dims:
            ds = ds.rename_dims({"valid_time": "time"})
        # Asegura que time sea coordenada
        if "time" in ds and "time" not in ds.coords:
            ds = ds.assign_coords(time=("time", ds["time"].values))
        rename = {}
        if "latitude" in ds.coords:
            rename["latitude"] = "lat"
        if "longitude" in ds.coords:
            rename["longitude"] = "lon"
        if rename:
            ds = ds.rename(rename)
        if var_name not in ds:
            raise KeyError(f"{var_name} no está en {f.name}")
        datasets.append(ds[[var_name]])
    ds = xr.concat(datasets, dim="time", combine_attrs="override")
    if "time" in ds.coords:
        ds = ds.sortby("time")
    return ds


def main():
    print("[INFO] Abriendo u10...")
    du = open_var("era5land_diario_guajira_10m_u_component_of_wind_*.nc", "u10")

    print("[INFO] Abriendo v10...")
    dv = open_var("era5land_diario_guajira_10m_v_component_of_wind_*.nc", "v10")

    print("[INFO] Abriendo t2m...")
    dt = open_var("era5land_diario_guajira_2m_temperature_*.nc", "t2m")

    print("[INFO] Abriendo sp...")
    dp = open_var("era5land_diario_guajira_surface_pressure_*.nc", "sp")

    # Alinea por tiempo
    print("[INFO] Alineando en tiempo...")
    du_a, dv_a, dt_a, dp_a = xr.align(du, dv, dt, dp, join="inner")
    ds = xr.Dataset()
    ds["u10"] = du_a["u10"]
    ds["v10"] = dv_a["v10"]
    ds["t2m"] = dt_a["t2m"]
    ds["sp"] = dp_a["sp"]

    # Calcula velocidad y dirección 10 m
    print("[INFO] Calculando wind10 y dir10...")
    ds["wind10"] = np.hypot(ds["u10"], ds["v10"])
    ds["dir10"] = np.arctan2(ds["u10"], ds["v10"])  # radianes, opcional

    # Chunk moderado en tiempo
    ds = ds.chunk({"time": 90})

    print(f"[INFO] Guardando {OUT_PATH} ...")
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    ds.to_netcdf(OUT_PATH)
    print("[OK] Listo.")


if __name__ == "__main__":
    main()
