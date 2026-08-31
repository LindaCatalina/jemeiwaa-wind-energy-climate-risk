"""Regenera y valida la galería pública usando únicamente los CSV versionados."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.image as mpimg
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reproducibilidad.config import RESULTS_DIR  # noqa: E402
from reproducibilidad.percentiles import regenerate_figures_from_tables  # noqa: E402


FIGURES = (
    "01_linea_base_historica.png",
    "02_cambio_cf_percentiles.png",
    "03_sensibilidad_metodologica.png",
    "04_estacionalidad_cf.png",
    "05_validacion_correccion_sesgo.png",
)
TABLES = {
    "linea_base_historica_por_modelo.csv": (
        {"method", "model", "cf_historical_mean", "energy_equivalent_mean_GWh"},
        24,
    ),
    "percentiles_cambio_cf.csv": (
        {"method", "scenario", "horizon", "n_models", "q10", "q50", "q90"},
        12,
    ),
    "percentiles_cf_mensual.csv": (
        {"method", "scenario", "horizon", "month", "q10", "q50", "q90"},
        168,
    ),
    "validacion_cuantiles_mensuales.csv": (
        {
            "source",
            "model",
            "correction_method",
            "month",
            "n_days",
            "q10",
            "q50",
            "q90",
        },
        300,
    ),
    "validacion_error_cuantiles_por_modelo.csv": (
        {
            "model",
            "n_month_quantiles",
            "rmse_raw_m_s",
            "rmse_corrected_m_s",
            "rmse_reduction_pct",
        },
        12,
    ),
}


def validate_tables() -> None:
    for name, (required, rows) in TABLES.items():
        path = RESULTS_DIR / "tables" / name
        frame = pd.read_csv(path)
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Faltan columnas en {path}: {sorted(missing)}")
        if len(frame) != rows:
            raise ValueError(f"Filas inesperadas en {path}: {len(frame)} != {rows}")

    baseline = pd.read_csv(RESULTS_DIR / "tables/linea_base_historica_por_modelo.csv")
    primary = baseline[baseline["method"] == "qm_sin_recentrado"]
    if len(primary) != 12 or not primary["cf_historical_mean"].between(0.0, 0.9).all():
        raise ValueError("La línea base histórica no contiene 12 modelos con CF físico")

    monthly = pd.read_csv(RESULTS_DIR / "tables/percentiles_cf_mensual.csv")
    if not monthly[["q10", "q50", "q90"]].apply(lambda column: column.between(0.0, 0.9)).all().all():
        raise ValueError("Los percentiles mensuales quedan fuera del rango físico [0, 0.9]")
    if not ((monthly["q10"] <= monthly["q50"]) & (monthly["q50"] <= monthly["q90"])).all():
        raise ValueError("Los percentiles mensuales no están ordenados")

    validation = pd.read_csv(RESULTS_DIR / "tables/validacion_cuantiles_mensuales.csv")
    expected_sources = {"era5", "cmip6_crudo", "cmip6_corregido"}
    if set(validation["source"]) != expected_sources:
        raise ValueError("Las fuentes del diagnóstico de sesgo están incompletas")
    if not ((validation["q10"] <= validation["q50"]) & (validation["q50"] <= validation["q90"])).all():
        raise ValueError("Los cuantiles de validación no están ordenados")

    errors = pd.read_csv(
        RESULTS_DIR / "tables/validacion_error_cuantiles_por_modelo.csv"
    )
    if errors["model"].nunique() != 12 or not (errors["n_month_quantiles"] == 36).all():
        raise ValueError("El diagnóstico de error no contiene 12 modelos × 36 cuantiles")
    if not (errors["rmse_corrected_m_s"] <= errors["rmse_raw_m_s"] + 1e-12).all():
        raise ValueError("La corrección aumenta el RMSE histórico en al menos un modelo")


def validate_figures() -> None:
    for name in FIGURES:
        path = RESULTS_DIR / "figures" / name
        if not path.is_file() or path.stat().st_size < 10_000:
            raise ValueError(f"Figura ausente o sospechosamente pequeña: {path}")
        image = mpimg.imread(path)
        if image.ndim not in (2, 3) or min(image.shape[:2]) < 500:
            raise ValueError(f"Dimensiones inválidas en {path}: {image.shape}")
        if float(image.std()) < 0.01:
            raise ValueError(f"Figura aparentemente vacía: {path}")
        print(f"[OK] {name}: {image.shape[1]}x{image.shape[0]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-only", action="store_true", help="Valida sin sobrescribir las figuras."
    )
    args = parser.parse_args()
    validate_tables()
    if not args.check_only:
        regenerate_figures_from_tables(RESULTS_DIR)
    validate_figures()
    print("[OK] Galería pública coherente con las tablas versionadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
