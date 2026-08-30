"""
Corrección de sesgo con Quantile Mapping mensual sobre las series crudas de
viento CMIP6 (sin corrección previa). Luego extrapola a 150 m, calcula densidad
y potencia/CF para la turbina V172 modo 6.8 MW.

Salida: corrected/{modelo}_{experimento}_wind_bc.nc con:
  - wind_bc  (viento 10 m corregido por QM)
  - v150     (viento 150 m corregido)
  - power_MW (potencia diaria por turbina)
  - power_planta_MW (potencia diaria de 162 turbinas = 1101.6 MW)
  - cf       (factor de planta diario)
  - rho      (densidad; si ps/tas disponibles)
"""

from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

# Rutas
ROOT = Path(__file__).resolve().parent
BIAS_DIR = ROOT / "bias_factors"
OUT_DIR = ROOT / "corrected"
OUT_DIR.mkdir(exist_ok=True)

EXPERIMENTS = ["historical", "ssp126", "ssp245", "ssp585"]

# Constantes
RD = 287.05
RHO_REF = 1.225
ALPHA_DEFAULT = 0.14
Z_REF = 10.0
Z_TARGET = 150.0
RATING_MW = 6.8
CUT_IN = 3.0
CUT_OUT = 25.0
LOSSES = 0.10
TURBINAS = 162  # 162 x 6.8 MW = 1101.6 MW
TOP_N = 14  # modelos a procesar


# -----------------------------------------------------------------------------#
# utilidades de apertura
# -----------------------------------------------------------------------------#
def open_ds_safe(path: Path) -> xr.Dataset:
    """Abre NetCDF tolerante a tiempos problemáticos."""
    try:
        return xr.open_dataset(path, use_cftime=True)
    except Exception:
        ds = xr.open_dataset(path, decode_times=False)
        ds = ds.drop_vars([v for v in ["time_bnds", "time_bounds"] if v in ds], errors="ignore")
        try:
            ds = xr.decode_cf(ds, use_cftime=True)
        except Exception:
            pass
        return ds


def open_and_decode(path: Path) -> xr.Dataset:
    """Abre un NetCDF decodificando tiempos y eliminando bounds molestos."""
    ds = xr.open_dataset(path, decode_times=False)
    ds = ds.drop_vars(
        [v for v in ["time_bnds", "time_bounds", "lat_bnds", "lon_bnds"] if v in ds],
        errors="ignore",
    )
    try:
        return xr.decode_cf(ds, use_cftime=True)
    except Exception:
        return ds


# -----------------------------------------------------------------------------#
# selección de modelos y lectura de cuantiles
# -----------------------------------------------------------------------------#
def list_models_ranked():
    rows = []
    for csv in BIAS_DIR.glob("*_bias_factors.csv"):
        model = csv.name.replace("_bias_factors.csv", "")
        df = pd.read_csv(csv, index_col=0)
        rmse = df["rmse_mean_allmonths"].iloc[0]
        rows.append((model, rmse))
    ranked = sorted(rows, key=lambda x: x[1])
    return [m for m, _ in ranked]


def load_quantiles(model):
    """Lee quantiles mensuales model/era5 y devuelve dict {month: (q_mod, q_era)}."""
    path = BIAS_DIR / f"{model}_quantiles.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    q_dict = {}
    probs = ["p5", "p10", "p25", "p50", "p75", "p90", "p95"]
    for m in range(1, 13):
        qm = df[(df["month"] == m) & (df["source"] == "model")]
        qe = df[(df["month"] == m) & (df["source"] == "era5")]
        if qm.empty or qe.empty:
            continue
        q_mod = qm[probs].iloc[0].to_numpy(dtype=float)
        q_era = qe[probs].iloc[0].to_numpy(dtype=float)
        q_dict[m] = (q_mod, q_era)
    return q_dict


# -----------------------------------------------------------------------------#
# carga de variables de viento/ps/tas
# -----------------------------------------------------------------------------#
def get_wind_var(model, exp):
    """Devuelve viento (sfcWind o uas/vas) y ps/tas."""
    wind = None
    files = list(ROOT.glob(f"{model}_{exp}_sfcWind_*_guajira.nc"))
    if files:
        ds = open_ds_safe(files[0])
        wind = ds["sfcWind"]
    else:
        ua = list(ROOT.glob(f"{model}_{exp}_uas_*_guajira.nc"))
        va = list(ROOT.glob(f"{model}_{exp}_vas_*_guajira.nc"))
        if ua and va:
            dsu = open_ds_safe(ua[0])
            dsv = open_ds_safe(va[0])
            wind = np.hypot(dsu["uas"], dsv["vas"])

    tas_files = list(ROOT.glob(f"{model}_{exp}_tas_*_guajira.nc"))
    ps_files = list(ROOT.glob(f"{model}_{exp}_ps_*_guajira.nc"))
    tas = open_and_decode(tas_files[0])["tas"] if tas_files else None
    ps = open_and_decode(ps_files[0])["ps"] if ps_files else None
    return wind, tas, ps


# -----------------------------------------------------------------------------#
# Quantile Mapping mensual
# -----------------------------------------------------------------------------#
def quantile_map(w: xr.DataArray, q_mod: np.ndarray, q_era: np.ndarray, probs: np.ndarray) -> xr.DataArray:
    """Mapea valores de w usando quantile mapping (interp de percentiles)."""
    # asegurar monotonicidad
    q_mod = np.maximum.accumulate(q_mod)
    q_era = np.maximum.accumulate(q_era)

    def _map(x):
        p = np.interp(x, q_mod, probs, left=probs[0], right=probs[-1])
        return np.interp(p, probs, q_era)

    return xr.apply_ufunc(
        _map,
        w,
        dask="parallelized",
        vectorize=True,
        output_dtypes=[float],
    )


def bias_correct_qm(wind_da: xr.DataArray, q_dict: dict) -> xr.DataArray:
    """Aplica QM mensual a toda la serie cruda y corrige mediana mensual residuo."""
    probs = np.array([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    wind_da = wind_da.sortby("time")
    month = wind_da["time"].dt.month
    corrected = []
    for m in range(1, 13):
        mask = month == m
        if m not in q_dict:
            corrected.append(wind_da.where(mask, drop=True))
            continue
        q_mod, q_era = q_dict[m]
        w_m = wind_da.where(mask, drop=True)
        corr_m = quantile_map(w_m, q_mod, q_era, probs)
        corrected.append(corr_m)

    bc = xr.concat(corrected, dim="time").sortby("time")

    # Ajuste adicional de mediana mensual post-QM para cerrar sesgo de nivel
    med_model = bc.groupby("time.month").median("time")
    med_ref_vals = []
    for m in range(1, 13):
        if m in q_dict:
            # índice 3 corresponde al percentil 0.50 en probs
            med_ref_vals.append(float(q_dict[m][1][3]))
        else:
            med_ref_vals.append(np.nan)
    med_ref = xr.DataArray(
        med_ref_vals,
        coords={"month": np.arange(1, 13)},
        dims=["month"],
    )
    bias_m = med_ref - med_model
    bc = bc + bias_m.sel(month=bc["time.month"])

    bc.name = "wind_bc"
    return bc


# -----------------------------------------------------------------------------#
# Extrapolación, densidad, potencia
# -----------------------------------------------------------------------------#
def extrapolate_power(wind10, alpha=ALPHA_DEFAULT):
    factor = (Z_TARGET / Z_REF) ** alpha
    return (wind10 * factor).rename("v150")


def compute_density(ps, tas):
    if ps is None or tas is None:
        return None
    return (ps / (RD * tas)).rename("rho")


def interp_ps_tas(ps, tas, target_time):
    try:
        ps_i = ps.interp(time=target_time)
        tas_i = tas.interp(time=target_time)
        return ps_i, tas_i
    except Exception as e:
        print(f"[WARN] No se pudo interpolar ps/tas al tiempo del viento: {e}")
        return None, None


def power_curve(v, rho, rho_ref=RHO_REF):
    """
    Potencia por turbina usando curva tabulada V164-8.0 MW escalada a 6.8 MW.
    - Tabla m/s -> kW real (offshore, 8 MW) escalada por 6.8/8=0.85.
    - Compresión suave del eje de velocidades para que el plateau arranque ~12 m/s (más típico onshore).
    - Corte en 3 m/s y 25 m/s ya implícitos en la tabla.
    """
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
    scale = RATING_MW / 8.0  # escalar de 8 MW a 6.8 MW
    p_tab_mw = (p_tab_kw / 1000.0) * scale
    # comprimir eje de velocidades para que el plateau (~13 m/s original) arranque ~12 m/s
    v_tab_comp = v_tab * (12.0 / 13.0)
    v_tab_comp[0] = CUT_IN  # asegurar cut-in exacto
    p_interp = np.interp(v, v_tab_comp, p_tab_mw, left=0.0, right=0.0)
    p = xr.apply_ufunc(lambda x: x, v) * 0  # solo para mantener dims
    p = p + p_interp
    p = p.where((v >= CUT_IN) & (v <= CUT_OUT), 0.0)
    if rho is not None:
        p = p * (rho / rho_ref)
    p = p * (1 - LOSSES)
    return p.rename("power_MW")


# -----------------------------------------------------------------------------#
# Procesamiento por modelo
# -----------------------------------------------------------------------------#
def process_model(model, quant_dict):
    for exp in EXPERIMENTS:
        print(f"[INFO] {model} {exp}: aplicando QM y potencia...")
        wind, tas, ps = get_wind_var(model, exp)
        if wind is None:
            print(f"[WARN] No hay viento para {model} {exp}, se omite.")
            continue
        wind_bc = bias_correct_qm(wind, quant_dict).sortby("time")
        wind_bc = wind_bc.drop_vars("month", errors="ignore")
        v150 = extrapolate_power(wind_bc).drop_vars("month", errors="ignore")

        rho = None
        if ps is not None and tas is not None:
            ps_i, tas_i = interp_ps_tas(ps, tas, wind_bc.time)
            if ps_i is not None and tas_i is not None:
                rho = compute_density(ps_i, tas_i)
                if rho.notnull().sum() == 0:
                    rho = None
                else:
                    rho = rho.fillna(RHO_REF)

        power = power_curve(v150, rho).drop_vars("month", errors="ignore")
        cf = (power / RATING_MW).rename("cf").drop_vars("month", errors="ignore")
        power_planta = (power * TURBINAS).rename("power_planta_MW").drop_vars("month", errors="ignore")

        out = xr.Dataset({"wind_bc": wind_bc, "v150": v150, "power_MW": power, "power_planta_MW": power_planta, "cf": cf})
        if rho is not None:
            out["rho"] = rho
        out = out.sortby("time").chunk({"time": 90})
        try:
            out = out.assign_coords(time=pd.to_datetime(out.time.values))
        except Exception:
            pass
        fname = OUT_DIR / f"{model}_{exp}_wind_bc.nc"
        if fname.exists():
            try:
                fname.unlink()
            except PermissionError:
                print(f"[WARN] No se pudo borrar {fname} (bloqueado). Se escribirá con otro nombre.")
                fname = fname.with_name(fname.stem + "_new.nc")
        out.to_netcdf(fname, mode="w")
        print(f"[OK] Guardado {fname.name}")


# -----------------------------------------------------------------------------#
# main
# -----------------------------------------------------------------------------#
def main():
    models = list_models_ranked()
    if not models:
        print("[ERROR] No hay modelos con bias_factors.")
        return
    selected = models[:TOP_N] if len(models) >= TOP_N else models
    print(f"[INFO] Modelos seleccionados (top {len(selected)} por RMSE): {selected}")
    for m in selected:
        quant_dict = load_quantiles(m)
        if quant_dict is None:
            print(f"[WARN] Sin quantiles para {m}, se omite.")
            continue
        process_model(m, quant_dict)
    print("[FIN] Corrección y potencia completadas.")


if __name__ == "__main__":
    main()
