"""Reconstrucción completa y protegida desde las fuentes oficiales."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reproducibilidad.config import CANONICAL_MODELS  # noqa: E402


COMMANDS = (
    [sys.executable, "scripts/download_era5.py"],
    [sys.executable, "Datos_Era5/unificar_era5_guajira.py"],
    [sys.executable, "Datos_Era5/era5_altura_densidad.py"],
    [sys.executable, "scripts/download_cmip6.py"],
    [sys.executable, "CMIP6_Guajira/bias_eval_cmip6.py"],
)


def _run(command: list[str]) -> None:
    print("[RUN]", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _derive_canonical_outputs() -> None:
    from CMIP6_Guajira import prepare_bias_corrected_inputs

    for model in CANONICAL_MODELS:
        quantiles = prepare_bias_corrected_inputs.load_quantiles(model)
        if quantiles is None:
            raise FileNotFoundError(f"No se generaron cuantiles para {model}")
        prepare_bias_corrected_inputs.process_model(model, quantiles)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstrucción completa ERA5-Land + CMIP6.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el plan sin ejecutarlo.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Autoriza reemplazar derivados NetCDF existentes; úselo sólo en un clon controlado.",
    )
    args = parser.parse_args()

    corrected = list((ROOT / "CMIP6_Guajira/corrected").glob("*.nc"))
    if corrected and not args.force and not args.dry_run:
        raise SystemExit(
            "Se detectaron derivados locales. Para protegerlos, el flujo se detuvo. "
            "Use un clon limpio o revise --force conscientemente."
        )

    plan = [
        *COMMANDS,
        ["Python", "derivar 48 series diarias corregidas canónicas"],
        [sys.executable, "scripts/run_analysis.py"],
        [sys.executable, "scripts/rebuild_figures.py", "--check-only"],
    ]
    if args.dry_run:
        print("Plan completo (requiere CDS, red, tiempo de cómputo y espacio en disco):")
        for command in plan:
            print("-", " ".join(command))
        return 0

    for command in COMMANDS:
        _run(command)
    _derive_canonical_outputs()
    _run([sys.executable, "scripts/run_analysis.py"])
    _run([sys.executable, "scripts/rebuild_figures.py", "--check-only"])
    print("[OK] Reconstrucción completa y validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
