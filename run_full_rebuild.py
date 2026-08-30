"""Reconstruccion completa y protegida a partir de las fuentes oficiales.

Este flujo es deliberadamente separado de ``run_portfolio.py`` porque descarga
centenares de subconjuntos y genera alrededor de 5.7 GiB de derivados. Se niega
a reemplazar NetCDF existentes salvo que se indique ``--force``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from reproducibilidad.config import CANONICAL_MODELS, PROJECT_ROOT


COMMANDS = (
    [sys.executable, "scripts/download_era5.py"],
    [sys.executable, "Datos_Era5/unificar_era5_guajira.py"],
    [sys.executable, "Datos_Era5/era5_altura_densidad.py"],
    [sys.executable, "scripts/download_cmip6.py"],
    [sys.executable, "CMIP6_Guajira/bias_eval_cmip6.py"],
)


def _run(command: list[str]) -> None:
    print("[RUN]", " ".join(command), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def _derive_canonical_outputs() -> None:
    from CMIP6_Guajira import apply_bias_and_power, postproc_future_power

    for model in CANONICAL_MODELS:
        quantiles = apply_bias_and_power.load_quantiles(model)
        if quantiles is None:
            raise FileNotFoundError(f"No se generaron cuantiles para {model}")
        apply_bias_and_power.process_model(model, quantiles)
    postproc_future_power.MODELOS = list(CANONICAL_MODELS)
    postproc_future_power.main()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruccion completa ERA5-Land + CMIP6.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el plan sin ejecutarlo.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Autoriza reemplazar derivados NetCDF existentes. No es necesario en un clon limpio.",
    )
    args = parser.parse_args()

    corrected = list((PROJECT_ROOT / "CMIP6_Guajira/corrected").glob("*.nc"))
    synthetic = list((PROJECT_ROOT / "CMIP6_Guajira/synthetic_10min").glob("*.nc"))
    if (corrected or synthetic) and not args.force and not args.dry_run:
        raise SystemExit(
            "Se detectaron derivados locales. Para protegerlos, el flujo se detuvo. "
            "Use este comando en un clon limpio o revise --force conscientemente."
        )

    plan = [*COMMANDS, ["Python", "derivar 48 corregidos y 48 series 10-min canonicas"],
            [sys.executable, "run_reproducible.py"],
            [sys.executable, "run_portfolio.py", "--check-only"]]
    if args.dry_run:
        print("Plan de reconstruccion completa (requiere credenciales CDS y bastante tiempo/disco):")
        for command in plan:
            print("-", " ".join(command))
        return 0

    for command in COMMANDS:
        _run(command)
    _derive_canonical_outputs()
    _run([sys.executable, "run_reproducible.py"])
    _run([sys.executable, "run_portfolio.py", "--check-only"])
    print("[OK] Reconstruccion completa y validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
