"""Auditoría automática, no destructiva, de datos y resultados existentes."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from netCDF4 import Dataset as NetCDF4Dataset

from .config import (
    CANONICAL_MODELS,
    CMIP6_DIR,
    CORRECTED_DIR,
    ERA5_DIR,
    EXPERIMENTS,
    LEGACY_SPLIT_TABLE,
    PROJECT_ROOT,
    RATING_MW,
    SYNTHETIC_DIR,
)
from .core import (
    as_time_series,
    extrapolate_to_hub,
    load_quantiles,
    open_netcdf_robust,
    proxy_power_curve_mw,
    raw_wind_path,
    year_values,
)


IGNORED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def _project_files(pattern: str = "*") -> list[Path]:
    """Lista archivos científicos sin incluir metadatos locales o cachés.

    Excluir `.git` evita que el manifiesto cambie por cada commit y que una
    auditoría profunda intente hashear objetos internos del repositorio.
    """
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


def build_inventory(output_root: Path, deep: bool) -> pd.DataFrame:
    rows = []
    output_resolved = output_root.resolve()
    files = _project_files()
    for index, path in enumerate(sorted(files)):
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
        if deep and (index + 1) % 100 == 0:
            print(f"[AUDIT] Hash {index + 1}/{len(files)}")
    return pd.DataFrame(rows)


def audit_netcdf_headers() -> pd.DataFrame:
    rows = []
    files = sorted(_project_files("*.nc"))
    for index, path in enumerate(files):
        row = {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "open_ok": False,
            "error": "",
        }
        try:
            # netCDF4 inspecciona únicamente la cabecera. Es mucho más rápido
            # que construir 575 objetos xarray y no materializa coordenadas de
            # millones de timestamps en las series subdiarias.
            with NetCDF4Dataset(path, mode="r") as ds:
                row["open_ok"] = True
                row["dimensions"] = ";".join(
                    f"{name}:{len(dimension)}" for name, dimension in ds.dimensions.items()
                )
                coord_names = set(ds.dimensions)
                row["data_variables"] = "|".join(
                    name for name in ds.variables if name not in coord_names
                )
                row["time_size"] = int(len(ds.dimensions["time"])) if "time" in ds.dimensions else 0
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        if (index + 1) % 100 == 0:
            print(f"[AUDIT] Cabeceras NetCDF {index + 1}/{len(files)}")
    return pd.DataFrame(rows)


def audit_era5() -> dict:
    source = ERA5_DIR / "era5_guajira_daily_1981_2014.nc"
    derived = ERA5_DIR / "era5_guajira_daily_1981_2014_150m.nc"
    ds = xr.open_dataset(source)
    alt = xr.open_dataset(derived)
    try:
        wind_diff = float(abs(np.hypot(ds["u10"], ds["v10"]) - ds["wind10"]).max())
        v150_diff = float(abs(extrapolate_to_hub(ds["wind10"]) - alt["v150_power"]).max())
        rho_diff = float(abs(ds["sp"] / (287.05 * ds["t2m"]) - alt["rho"]).max())
        time = pd.to_datetime(ds["time"].values)
        steps = np.diff(time.values).astype("timedelta64[D]").astype(int)
        return {
            "n_days": int(ds.sizes["time"]),
            "start": str(time[0].date()),
            "end": str(time[-1].date()),
            "unique_day_steps": sorted(set(map(int, steps))),
            "nan_total": int(ds.to_array().isnull().sum()),
            "wind_formula_max_abs_diff": wind_diff,
            "v150_formula_max_abs_diff": v150_diff,
            "rho_formula_max_abs_diff": rho_diff,
            "pass": (
                ds.sizes["time"] == 12418
                and wind_diff == 0.0
                and v150_diff == 0.0
                and rho_diff == 0.0
                and set(steps) == {1}
            ),
        }
    finally:
        ds.close()
        alt.close()


def audit_raw_canonical() -> pd.DataFrame:
    rows = []
    for model in CANONICAL_MODELS:
        for experiment in EXPERIMENTS:
            path = raw_wind_path(model, experiment)
            ds = open_netcdf_robust(path)
            try:
                wind = as_time_series(ds["sfcWind"])
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
                        "path": path.relative_to(PROJECT_ROOT).as_posix(),
                        "n_time": int(wind.sizes["time"]),
                        "start_year": int(years.min()),
                        "end_year": int(years.max()),
                        "nan_count": int(wind.isnull().sum()),
                        "coverage_ok": bool(expected),
                    }
                )
            finally:
                ds.close()
    return pd.DataFrame(rows)


def audit_corrected() -> tuple[pd.DataFrame, dict]:
    rows = []
    density_missing = []
    median_recentering_max_diff = 0.0
    for model in CANONICAL_MODELS:
        qtable = load_quantiles(model)
        ref_median = qtable[qtable["source"] == "era5"].set_index("month")["p50"]
        for experiment in EXPERIMENTS:
            path = CORRECTED_DIR / f"{model}_{experiment}_wind_bc.nc"
            ds = xr.open_dataset(path)
            try:
                wind = as_time_series(ds["wind_bc"])
                v150 = as_time_series(ds["v150"])
                power = as_time_series(ds["power_MW"])
                cf = as_time_series(ds["cf"])
                plant = as_time_series(ds["power_planta_MW"])
                rho = as_time_series(ds["rho"]) if "rho" in ds else None
                if rho is None:
                    density_missing.append(f"{model}:{experiment}")
                calc_v150 = extrapolate_to_hub(wind)
                calc_power = proxy_power_curve_mw(calc_v150, rho if rho is not None else 1.225)
                diffs = {
                    "v150_diff": float(abs(calc_v150 - v150).max()),
                    "power_diff": float(abs(calc_power - power).max()),
                    "cf_diff": float(abs(power / RATING_MW - cf).max()),
                    "plant_diff": float(abs(power * 162 - plant).max()),
                }
                years = year_values(wind)
                if experiment != "historical":
                    med = wind.groupby("time.month").median("time").to_series()
                    diff = float((med.reindex(range(1, 13)) - ref_median.reindex(range(1, 13))).abs().max())
                    median_recentering_max_diff = max(median_recentering_max_diff, diff)
                rows.append(
                    {
                        "model": model,
                        "experiment": experiment,
                        "n_time": int(wind.sizes["time"]),
                        "start_year": int(years.min()),
                        "end_year": int(years.max()),
                        "nan_wind": int(wind.isnull().sum()),
                        "nan_power": int(power.isnull().sum()),
                        "wind_min": float(wind.min()),
                        "wind_max": float(wind.max()),
                        "negative_wind_count": int((wind < 0).sum()),
                        "cf_min": float(cf.min()),
                        "cf_max": float(cf.max()),
                        "rho_available": rho is not None,
                        **diffs,
                        "formula_ok": all(value < 1e-10 for value in diffs.values()),
                    }
                )
            finally:
                ds.close()
    frame = pd.DataFrame(rows)
    summary = {
        "n_series": int(len(frame)),
        "n_models": int(frame["model"].nunique()),
        "all_formulas_reproduce": bool(frame["formula_ok"].all()),
        "total_nan_wind": int(frame["nan_wind"].sum()),
        "total_nan_power": int(frame["nan_power"].sum()),
        "series_with_negative_corrected_wind": int((frame["negative_wind_count"] > 0).sum()),
        "density_missing_count": len(density_missing),
        "density_missing": density_missing,
        "future_monthly_median_vs_era5_p50_max_abs_diff": median_recentering_max_diff,
    }
    return frame, summary


def audit_legacy_table() -> dict:
    table = pd.read_csv(LEGACY_SPLIT_TABLE)
    hist = table[(table["exp"] == "historical") & (table["horizon"] == "hist")]
    future = table[(table["exp"] != "historical") & (table["horizon"] != "hist")]
    valid_pairs = future.merge(hist[["model", "cf_mean"]], on="model", how="inner")
    # Reproduce el pivot defectuoso del script original: exp forma parte del
    # índice, así que historical nunca se empareja con SSP.
    broken_pairs = 0
    for horizon in ("mid", "late"):
        part = table[table["horizon"].isin(["hist", horizon])]
        pivot = part.pivot_table(index=["model", "exp"], columns="horizon", values="cf_mean").dropna()
        broken_pairs += len(pivot)
    return {
        "rows": int(len(table)),
        "models": int(table["model"].nunique()),
        "expected_future_baseline_pairs": int(len(valid_pairs)),
        "pairs_created_by_legacy_plot_code": int(broken_pairs),
        "legacy_delta_plots_are_empty": broken_pairs == 0,
    }


def audit_synthetic(deep: bool) -> tuple[pd.DataFrame, dict]:
    rows = []
    files = sorted(SYNTHETIC_DIR.glob("*_subdaily.nc"))
    for index, path in enumerate(files):
        ds = xr.open_dataset(path)
        row = {
            "file": path.name,
            "n_time": int(ds.sizes.get("time", 0)),
            "variables_ok": set(("v150_10min", "power_10min", "cf_10min")).issubset(ds.data_vars),
        }
        if deep:
            for variable in ("v150_10min", "power_10min", "cf_10min"):
                da = ds[variable]
                row[f"{variable}_nan"] = int(da.isnull().sum())
                row[f"{variable}_min"] = float(da.min())
                row[f"{variable}_max"] = float(da.max())
        ds.close()
        rows.append(row)
        if deep and (index + 1) % 8 == 0:
            print(f"[AUDIT] Series sintéticas {index + 1}/{len(files)}")

    # Comprobación empírica y teórica de conservación de la media diaria.
    model = "NorESM2-MM"
    corrected = xr.open_dataset(CORRECTED_DIR / f"{model}_historical_wind_bc.nc")
    synthetic = xr.open_dataset(SYNTHETIC_DIR / f"{model}_historical_subdaily.nc")
    try:
        daily = np.asarray(as_time_series(corrected["v150"]).values, dtype=float)
        sub = np.asarray(synthetic["v150_10min"].values, dtype=float).reshape(-1, 144).mean(axis=1)
        n = min(len(daily), len(sub))
        observed_ratio = float(np.mean(sub[:n] / daily[:n]))
    finally:
        corrected.close()
        synthetic.close()
    theoretical_ratio = float(math.gamma(1.5) / math.sqrt(2.0))
    summary = {
        "n_files": len(files),
        "observed_daily_mean_ratio_sample": observed_ratio,
        "theoretical_daily_mean_ratio_current_weibull": theoretical_ratio,
        "daily_mean_is_conserved": abs(observed_ratio - 1.0) < 0.01,
    }
    return pd.DataFrame(rows), summary


def run_audit(output_root: Path, deep: bool = False) -> dict:
    audit_dir = output_root / "auditoria"
    audit_dir.mkdir(parents=True, exist_ok=True)

    print("[AUDIT] Inventario de archivos")
    inventory = build_inventory(output_root, deep)
    inventory.to_csv(audit_dir / "inventario_archivos.csv", index=False)

    print("[AUDIT] Cabeceras NetCDF")
    headers = audit_netcdf_headers()
    headers.to_csv(audit_dir / "auditoria_cabeceras_netcdf.csv", index=False)

    print("[AUDIT] ERA5")
    era5 = audit_era5()
    raw = audit_raw_canonical()
    raw.to_csv(audit_dir / "auditoria_cmip6_sfcwind_canonico.csv", index=False)

    print("[AUDIT] Productos corregidos")
    corrected, corrected_summary = audit_corrected()
    corrected.to_csv(audit_dir / "auditoria_series_corregidas.csv", index=False)

    print("[AUDIT] Productos sintéticos")
    synthetic, synthetic_summary = audit_synthetic(deep)
    synthetic.to_csv(audit_dir / "auditoria_series_sinteticas.csv", index=False)

    legacy_table = audit_legacy_table()
    result = {
        "inventory": {
            "files": int(len(inventory)),
            "size_GiB": float(inventory["size_bytes"].sum() / 2**30),
            "sha256_complete": bool((inventory["sha256"] != "").all()),
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
        "corrected": corrected_summary,
        "synthetic": synthetic_summary,
        "legacy_table_and_figures": legacy_table,
    }
    result["fatal_integrity_failures"] = int(
        (not era5["pass"])
        + result["netcdf"]["open_errors"]
        + result["raw_canonical"]["coverage_failures"]
        + (not corrected_summary["all_formulas_reproduce"])
        + corrected_summary["total_nan_wind"]
        + corrected_summary["total_nan_power"]
    )
    with (audit_dir / "resumen_auditoria.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    return result
