"""Recalcula las tablas y figuras públicas sin sobrescribir datos científicos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reproducibilidad.config import RESULTS_DIR  # noqa: E402
from reproducibilidad.percentiles import write_results  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recalcula CF, energía académica, percentiles y figuras desde los NetCDF locales."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_DIR,
        help="Directorio de salida (predeterminado: results).",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Datos originales: {ROOT}")
    print(f"[INFO] Salida pública no destructiva: {output}")
    generated = write_results(output)
    for label, path in generated.items():
        print(f"[OK] {label}: {path}")
    print("[OK] Resultados coherentes generados con conservación exacta de la media diaria.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
