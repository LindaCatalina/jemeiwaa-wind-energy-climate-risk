"""Regenera y valida la galeria publica usando solo las tablas auditadas."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.image as mpimg
import pandas as pd

from reproducibilidad.config import PROJECT_ROOT
from reproducibilidad.percentiles import (
    plot_change_percentiles,
    plot_energy_exceedance,
    plot_monthly_percentiles,
)


RESULTS = PROJECT_ROOT / "resultados_reproducibles"
FIGURES = {
    "legado_cf": RESULTS / "legado/figuras/01_cambio_cf_percentiles.png",
    "sensibilidad_cf": RESULTS
    / "sensibilidad_sin_recentrado/figuras/01_cambio_cf_percentiles.png",
    "sensibilidad_energia": RESULTS
    / "sensibilidad_sin_recentrado/figuras/03_energia_p50_p90.png",
    "sensibilidad_mensual": RESULTS
    / "sensibilidad_sin_recentrado/figuras/04_cf_mensual_percentiles.png",
}


def _read(relative: str, required: set[str], expected_rows: int) -> pd.DataFrame:
    path = RESULTS / relative
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Faltan columnas en {path}: {sorted(missing)}")
    if len(frame) != expected_rows:
        raise ValueError(f"Filas inesperadas en {path}: {len(frame)} != {expected_rows}")
    return frame


def load_tables() -> dict[str, pd.DataFrame]:
    change_columns = {"scenario", "horizon", "n_models", "q10", "q50", "q90"}
    return {
        "legacy_change": _read(
            "legado/tablas/percentiles_cambio_cf_ensemble.csv", change_columns, 6
        ),
        "sensitivity_change": _read(
            "sensibilidad_sin_recentrado/tablas/percentiles_cambio_cf_ensemble.csv",
            change_columns,
            6,
        ),
        "sensitivity_energy": _read(
            "sensibilidad_sin_recentrado/tablas/percentiles_energia_ensemble.csv",
            {"scenario", "horizon", "P90_exceedance_GWh", "P50_exceedance_GWh"},
            7,
        ),
        "sensitivity_monthly": _read(
            "sensibilidad_sin_recentrado/tablas/percentiles_cf_mensual_ensemble.csv",
            {"scenario", "horizon", "month", "q10", "q50", "q90"},
            84,
        ),
    }


def regenerate(tables: dict[str, pd.DataFrame]) -> None:
    plot_change_percentiles(
        tables["legacy_change"], FIGURES["legado_cf"],
        "resultado legado reproducido; barras P10-P90 entre modelos",
    )
    plot_change_percentiles(
        tables["sensitivity_change"], FIGURES["sensibilidad_cf"],
        "sensibilidad sin recentrado futuro; barras P10-P90 entre modelos",
    )
    plot_energy_exceedance(
        tables["sensitivity_energy"], FIGURES["sensibilidad_energia"],
        "percentiles academicos; no constituyen un P90 financiero",
    )
    plot_monthly_percentiles(
        tables["sensitivity_monthly"], FIGURES["sensibilidad_mensual"],
        "sensibilidad sin recentrado futuro",
    )


def validate_figures() -> None:
    for label, path in FIGURES.items():
        if not path.is_file() or path.stat().st_size < 10_000:
            raise ValueError(f"Figura ausente o sospechosamente pequena: {path}")
        image = mpimg.imread(path)
        if image.ndim not in (2, 3) or min(image.shape[:2]) < 500:
            raise ValueError(f"Dimensiones invalidas en {path}: {image.shape}")
        if float(image.std()) < 0.01:
            raise ValueError(f"Figura aparentemente vacia: {path}")
        print(f"[OK] {label}: {image.shape[1]}x{image.shape[0]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-only", action="store_true", help="Valida sin sobrescribir las figuras."
    )
    args = parser.parse_args()
    tables = load_tables()
    if not args.check_only:
        regenerate(tables)
    validate_figures()
    print("[OK] Galeria publica coherente con las tablas auditadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
