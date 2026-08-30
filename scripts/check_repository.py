"""Comprobaciones no destructivas de codigo, estructura y datos locales."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "private_data", "private_documents"}
REQUIRED = (
    "README.md",
    "INFORME_AUDITORIA.md",
    "requirements.txt",
    "requirements-download.txt",
    "environment.yml",
    "run_portfolio.py",
    "run_full_rebuild.py",
    "run_reproducible.py",
    "run_bankability.py",
    "reproducibilidad/config.py",
    "bankability/config.example.json",
    "data/cmip6_source_manifest.csv",
    "data/era5_request_manifest.csv",
    "data/README.md",
    "resultados_reproducibles/RESUMEN_EJECUCION.md",
    "resultados_reproducibles/bancabilidad/estado_bancabilidad.json",
    ".gitattributes",
    ".gitignore",
    "CITATION.cff",
)

SECRET_PATTERNS = {
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
ABSOLUTE_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\(?:Users|Documents)\\", re.IGNORECASE)
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".cff", ".gitignore", ".gitattributes"}


def _iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts):
            continue
        yield path


def _netcdf_is_ignored() -> bool:
    command = [
        "git", "-c", f"safe.directory={ROOT.as_posix()}", "check-ignore", "--no-index",
        "CMIP6_Guajira/example.nc",
    ]
    return subprocess.run(command, cwd=ROOT, capture_output=True, check=False).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true", help="No exige datos crudos locales.")
    parser.add_argument("--require-data", action="store_true", help="Exige los datos cientificos locales.")
    args = parser.parse_args()

    failures: list[str] = []
    warnings: list[str] = []
    files = list(_iter_files())

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            failures.append(f"Falta archivo obligatorio: {relative}")

    python_files = [path for path in files if path.suffix == ".py"]
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            failures.append(f"Python invalido {path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")

    netcdf_ignored = _netcdf_is_ignored()
    if not netcdf_ignored:
        failures.append("La regla *.nc no esta activa en .gitignore.")

    large_files = [path for path in files if path.stat().st_size > 100 * 1024 * 1024]
    unexpected_large = [path for path in large_files if path.suffix.lower() != ".nc"]
    for path in unexpected_large:
        failures.append(f"Archivo local >100 MiB no cubierto por la politica: {path.relative_to(ROOT)}")

    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", ".gitattributes"}:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(source):
                failures.append(f"Posible {name} en {path.relative_to(ROOT)}")
        if ABSOLUTE_WINDOWS_PATH.search(source):
            warnings.append(f"Ruta absoluta legada en {path.relative_to(ROOT)}; no la usa el flujo canonico")

    if args.require_data:
        era5 = ROOT / "Datos_Era5" / "era5_guajira_daily_1981_2014.nc"
        synthetic = list((ROOT / "CMIP6_Guajira" / "synthetic_10min").glob("*.nc"))
        if not era5.is_file() or era5.stat().st_size < 1024:
            failures.append("Falta ERA5 materializado; ejecute scripts/download_era5.py y unifique.")
        if len(synthetic) != 48 or any(path.stat().st_size < 1024 for path in synthetic):
            failures.append(f"Se esperaban 48 series sinteticas NetCDF; encontradas={len(synthetic)}")

    result = {
        "status": "PASS" if not failures else "FAIL",
        "files_checked": len(files),
        "python_files_parsed": len(python_files),
        "large_local_files_over_100_MiB": len(large_files),
        "netcdf_ignored_for_github": netcdf_ignored,
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
        "ci_mode": args.ci,
        "data_required": args.require_data,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
