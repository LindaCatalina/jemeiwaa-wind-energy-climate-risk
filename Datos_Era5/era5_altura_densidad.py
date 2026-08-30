"""
Calcula viento a 150 m y densidad del aire para el píxel de La Guajira
a partir del archivo consolidado era5_guajira_daily_1981_2014.nc.

Salidas (nuevo NetCDF):
  - v10 (m/s)             : del archivo fuente
  - v150_log (m/s)        : extrapolado con ley logarítmica (z0 configurable)
  - v150_power (m/s)      : extrapolado con ley de potencia (alpha configurable)
  - rho (kg/m3)           : densidad del aire con sp/t2m

Ajusta z0 (rugosidad) según tu criterio costero/árido:
  z0 típico costero árido: 0.03–0.05 m. Se usa z0_default=0.04 m.
Alpha (ley de potencia) típica en costa: 0.12–0.16. Se usa alpha_default=0.14.
"""

from pathlib import Path
import xarray as xr
import numpy as np

# Configuración
DATA_DIR = Path(__file__).resolve().parent
IN_PATH = DATA_DIR / "era5_guajira_daily_1981_2014.nc"
OUT_PATH = DATA_DIR / "era5_guajira_daily_1981_2014_150m.nc"

z0_default = 0.04  # m, rugosidad costera/aridez La Guajira
alpha_default = 0.14
z_ref = 10.0
z_target = 150.0

# Constante de gas seco
RD = 287.05  # J/(kg*K)


def compute_v150_log(v10, z0=z0_default):
    """Extrapola con ley logarítmica."""
    factor = np.log(z_target / z0) / np.log(z_ref / z0)
    return v10 * factor


def compute_v150_power(v10, alpha=alpha_default):
    """Extrapola con ley de potencia."""
    factor = (z_target / z_ref) ** alpha
    return v10 * factor


def main():
    print(f"[INFO] Leyendo {IN_PATH} ...")
    ds = xr.open_dataset(IN_PATH)

    if "wind10" not in ds:
        # Si no existe, lo calculamos por seguridad
        ds["wind10"] = np.hypot(ds["u10"], ds["v10"])

    print("[INFO] Calculando v150 (log) y v150 (power)...")
    ds["v150_log"] = compute_v150_log(ds["wind10"])
    ds["v150_power"] = compute_v150_power(ds["wind10"])

    print("[INFO] Calculando densidad del aire (rho)...")
    # t2m ya viene en Kelvin en ERA5; sp en Pascales
    ds["rho"] = ds["sp"] / (RD * ds["t2m"])

    # Chunks moderados en tiempo
    ds = ds.chunk({"time": 90})

    print(f"[INFO] Guardando {OUT_PATH} ...")
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    ds.to_netcdf(OUT_PATH)
    print("[OK] Listo.")


if __name__ == "__main__":
    main()
