"""CLI separado para el control de P50/P90 pre-bancable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bankability.pipeline import run_preliminary_assessment


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Valida insumos bancables y sólo calcula percentiles preliminares si todos pasan."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "bankability" / "config.example.json",
        help="Configuración JSON; copie el ejemplo y complete referencias privadas.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Directorio de salida. El ejemplo público usa resultados_reproducibles/bancabilidad; "
            "una configuración local usa bankability/private_outputs."
        ),
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Genera el diagnóstico y retorna éxito aunque existan bloqueos esperados.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    if args.output is not None:
        output = args.output
    elif config_path.name == "config.example.json":
        output = PROJECT_ROOT / "resultados_reproducibles" / "bancabilidad"
    else:
        output = PROJECT_ROOT / "bankability" / "private_outputs"
    status = run_preliminary_assessment(config_path, output)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if status["ready_for_preliminary_p90"]:
        print("[OK] Cálculo preliminar generado; todavía requiere revisión independiente.")
        return 0
    print("[BLOQUEADO] No se calculó un P90 financiero: faltan insumos obligatorios.")
    return 0 if args.status_only else 2


if __name__ == "__main__":
    raise SystemExit(main())
