"""AuditorÃ­a no destructiva del flujo cientÃ­fico vigente."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from netCDF4 import Dataset as NetCDF4Dataset

from .config import (
    CANONICAL_MODELS,
    CORRECTED_DIR,
    ERA5_DIR,
    EXPERIMENTS,
    PROJECT_ROOT,
    RESULTS_DIR,
)
from .core import (
    as_time_series,
    deterministic_weibull_multipliers,
    extrapolate_to_hub,
    open_netcdf_robust,
    raw_wind_path,
    year_values,
)


IGNORED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "_archivo_interno",
    "synthetic_10min",
}


def _project_files(pattern: str = "*") -> list[Path]:
    """Lista archivos del proyecto sin cachÃ©s ni material legado local."""
    return [
        path
        for path in PROJECT_ROOT.rglob(pattern)
        if path.is_file()
        and not any(part in IGNORED_PARTS for part in path.relative_to(PROJECT_ROOT).parts)
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_inventory(output_root: Path, deep: bool = False) -> pd.DataFrame:
    """Construye un inventario; los NetCDF solo se hashean con ``deep``."""
    rows: list[dict] = []
    output_resolved = output_root.resolve()
    for path in sorted(_project_files()):
        try:
            path.resolve().relative_to(output_resolved)
            continue
        except ValueError:
            pass
        should_hash = deep or path.suffix.lower() not in {".nc", ".pyc"}
        rows.append(
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "extension": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path) if should_hash else "",
            }
        )
    return pd.DataFrame(rows)


def audit_netcdf_headers() -> pd.DataFrame:
    """Verifica que todos los NetCDF locales puedan abrir su cabecera."""
    rows: list[dict] = []
    for path in sorted(_project_files("*.nc")):
        row = {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "open_ok": False,
            "error": "",
        }
        try:
            with NetCDF4Dataset(path, mode="r") as dataset:
                row["open_ok"] = True
                row["dimensions"] = ";".join(
                    f"{name}:{len(dimension)}"
                    for name, dimension in dataset.dimensions.items()
                )
        except Exception as exc:  # pragma: no cover - solo con datos daÃ±ados
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return pd.DataFrame(rows)


def audit_era5() -> dict:
    """Comprueba cobertura y fÃ³rmulas de los productos ERA5 locales."""
    source = ERA5_DIR / "era5_guajira_daily_1981_2014.nc"
    derived = ERA5_DIR / "era5_guajira_daily_1981_2014_150m.nc"
    with xr.open_dataset(source) as base, xr.open_dataset(derived) as hub:
        wind_diff = float(abs(np.hypot(base["u10"], base["v10"]) - base["wind10"]).max())
        v150_diff = float(abs(extrapolate_to_hub(base["wind10"]) - hub["v150_power"]).max())
        rho_diff = float(abs(base["sp"] / (287.05 * base["t2m"]) - hub["rho"]).max())
        time = pd.to_datetime(base["time"].values)
        steps = np.diff(time.values).astype("timedelta64[D]").astype(int)
        passed = (
            base.sizes["time"] == 12418
            and wind_diff == 0.0
            and v150_diff == 0.0
            and rho_diff == 0.0
            and set(steps) == {1}
        )
        return {
            "n_days": int(base.sizes["time"]),
            "start": str(time[0].date()),
            "end": str(time[-1].date()),
            "wind_formula_max_abs_diff": wind_diff,
            "v150_formula_max_abs_diff": v150_diff,
            "rho_formula_max_abs_diff": rho_diff,
            "pass": bool(passed),
        }


def audit_raw_canonical() -> pd.DataFrame:
    """Revisa cobertura temporal y faltantes del ensamble canÃ³nico."""
    rows: list[dict] = []
    for model in CANONICAL_MODELS:
        for experiment in EXPERIMENTS:
            path = raw_wind_path(model, experiment)
            with open_netcdf_robust(path) as dataset:
                wind = as_time_series(dataset["sfcWind"])
                years = year_values(wind)
                expected = (
                    years.min() == 1981 and years.max() == 2014
                    if experiment == "historical"
                    else years.min() == 2015 and years.max() >= 2099
                )
                rows.append(
                    {
                        "model": model,
                        "experiment": experiment,
                        "n_time": int(wind.sizes["time"]),
                        "start_year": int(years.min()),
                        "end_year": int(years.max()),
                        "nan_count": int(wind.isnull().sum()),
                        "coverage_ok": bool(expected),
                    }
                )
    return pd.DataFrame(rows)


def audit_corrected_inputs() -> pd.DataFrame:
    """Valida los 48 insumos diarios que consume el anÃ¡lisis final."""
    rows: list[dict] = []
    for model in CANONICAL_MODELS:
        for experiment in EXPERIMENTS:
            path = CORRECTED_DIR / f"{model}_{experiment}_wind_bc.nc"
            with xr.open_dataset(path) as dataset:
                wind = as_time_series(dataset["wind_bc"])
                years = year_values(wind)
                rows.append(
                    {
                        "model": model,
                        "experiment": experiment,
                        "n_time": int(wind.sizes["time"]),
                        "start_year": int(years.min()),
                        "end_year": int(years.max()),
                        "nan_wind": int(wind.isnull().sum()),
                        "negative_wind": int((wind < 0).sum()),
                        "rho_available": "rho" in dataset,
                    }
                )
    return pd.DataFrame(rows)


def audit_subdaily_method() -> dict:
    """Demuestra la conservaciÃ³n exacta de la media diaria vigente."""
    multipliers = deterministic_weibull_multipliers()
    return {
        "method": "deterministic Weibull midpoint quadrature",
        "states_per_day": int(len(multipliers)),
        "multiplier_mean": float(multipliers.mean()),
        "daily_mean_is_conserved": bool(abs(float(multipliers.mean()) - 1.0) < 1e-12),
    }


def audit_public_results() -> dict:
    """Comprueba presencia y rango fÃ­sico de las tablas/figuras finales."""
    annual = pd.read_csv(RESULTS_DIR / "tables" / "metricas_anuales.csv")
    baseline = pd.read_csv(RESULTS_DIR / "tables" / "linea_base_historica_por_modelo.csv")
    figures = sorted((RESULTS_DIR / "figures").glob("*.png"))
    cf_columns = [column for column in annual.columns if column.startswith("cf_")]
    cf_valid = all(annual[column].between(0, 0.9).all() for column in cf_columns)
    passed = len(figures) == 5 and baseline["model"].nunique() == 12 and cf_valid
    return {
        "annual_rows": int(len(annual)),
        "baseline_models": int(baseline["model"].nunique()),
        "figures": int(len(figures)),
        "cf_in_physical_range": bool(cf_valid),
        "pass": bool(passed),
    }


def run_audit(output_root: Path, deep: bool = False) -> dict:
    """Ejecuta la auditorÃ­a y escribe reportes CSV/JSON en ``output_root``."""
    audit_dir = output_root / "auditoria"
    audit_dir.mkdir(parents=True, exist_ok=True)

    inventory = build_inventory(output_root, deep)
    inventory.to_csv(audit_dir / "inventario_archivos.csv", index=False)
    headers = audit_netcdf_headers()
    headers.to_csv(audit_dir / "auditoria_cabeceras_netcdf.csv", index=False)
    raw = audit_raw_canonical()
    raw.to_csv(audit_dir / "auditoria_cmip6_canonico.csv", index=False)
    corrected = audit_corrected_inputs()
    corrected.to_csv(audit_dir / "auditoria_series_corregidas.csv", index=False)

    era5 = audit_era5()
    subdaily = audit_subdaily_method()
    public = audit_public_results()
    result = {
        "inventory": {
            "files": int(len(inventory)),
            "size_GiB": float(inventory["size_bytes"].sum() / 2**30),
        },
        "netcdf": {
            "files": int(len(headers)),
            "open_errors": int((~headers["open_ok"]).sum()),
        },
        "era5": era5,
        "raw_canonical": {
            "series": int(len(raw)),
            "coverage_failures": int((~raw["coverage_ok"]).sum()),
            "nan_total": int(raw["nan_count"].sum()),
        },
        "corrected_inputs": {
            "series": int(len(corrected)),
            "nan_total": int(corrected["nan_wind"].sum()),
        },
        "subdaily_integration": subdaily,
        "public_results": public,
    }
    result["fatal_integrity_failures"] = int(
        (not era5["pass"])
        + result["netcdf"]["open_errors"]
        + result["raw_canonical"]["coverage_failures"]
        + result["raw_canonical"]["nan_total"]
        + result["corrected_inputs"]["nan_total"]
        + (not subdaily["daily_mean_is_conserved"])
        + (not public["pass"])
    )
    with (audit_dir / "resumen_auditoria.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    return result
