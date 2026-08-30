"""Valida exactamente lo que entraria al primer commit de GitHub."""

from __future__ import annotations

import hashlib
import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import matplotlib.image as mpimg


ROOT = Path(__file__).resolve().parents[1]
MAX_PUBLIC_FILE = 10 * 1024 * 1024
RAW_SUFFIXES = {".nc", ".nc4", ".grib", ".grb", ".zip", ".7z", ".tar", ".gz", ".tgz"}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REQUIRED_FIGURES = (
    "resultados_reproducibles/legado/figuras/01_cambio_cf_percentiles.png",
    "resultados_reproducibles/sensibilidad_sin_recentrado/figuras/01_cambio_cf_percentiles.png",
    "resultados_reproducibles/sensibilidad_sin_recentrado/figuras/03_energia_p50_p90.png",
    "resultados_reproducibles/sensibilidad_sin_recentrado/figuras/04_cf_mensual_percentiles.png",
)
FORBIDDEN_FIGURES = {
    "CMIP6_Guajira/metrics_future/plots/delta_cf_models.png",
    "CMIP6_Guajira/metrics_future/plots/delta_energy_models.png",
}
REQUIRED_PUBLIC_FILES = {
    "README.md",
    "data/cmip6_source_manifest.csv",
    "data/era5_request_manifest.csv",
    "docs/GITHUB_PUBLICACION.md",
    "run_portfolio.py",
    *REQUIRED_FIGURES,
}


def candidate_paths() -> list[Path]:
    command = [
        "git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files",
        "--cached", "--others", "--exclude-standard", "-z",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=True)
    names = [name for name in result.stdout.decode("utf-8").split("\0") if name]
    return [ROOT / name for name in names if (ROOT / name).is_file()]


def main() -> int:
    paths = candidate_paths()
    relative = {path.relative_to(ROOT).as_posix() for path in paths}
    failures: list[str] = []
    missing = REQUIRED_PUBLIC_FILES - relative
    failures.extend(f"Falta en la publicacion: {name}" for name in sorted(missing))
    failures.extend(f"Figura prohibida incluida: {name}" for name in sorted(FORBIDDEN_FIGURES & relative))

    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in RAW_SUFFIXES or ".zarr/" in name:
            failures.append(f"Dato crudo incluido: {name}")
        if path.stat().st_size > MAX_PUBLIC_FILE:
            failures.append(f"Archivo >10 MiB: {name}")

    public_figures = [path for path in paths if path.suffix.lower() == ".png"]
    for path in public_figures:
        name = path.relative_to(ROOT).as_posix()
        image = mpimg.imread(path)
        if min(image.shape[:2]) < 500 or float(image.std()) < 0.01:
            failures.append(f"Figura vacia o danada: {name}")

    for path in paths:
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            clean = target.split("#", 1)[0].strip().strip("<>")
            if not clean or "://" in clean or clean.startswith(("mailto:", "#")):
                continue
            resolved = (path.parent / clean).resolve()
            if not resolved.exists():
                failures.append(
                    f"Enlace relativo roto en {path.relative_to(ROOT).as_posix()}: {target}"
                )

    manifest_counts = {
        "data/era5_request_manifest.csv": 136,
        "data/cmip6_source_manifest.csv": 215,
    }
    for name, expected in manifest_counts.items():
        with (ROOT / name).open(encoding="utf-8", newline="") as stream:
            count = sum(1 for _ in csv.DictReader(stream))
        if count != expected:
            failures.append(f"Manifiesto incompleto {name}: {count} != {expected}")

    hashes: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        if path.stat().st_size < 1024:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[digest].append(path.relative_to(ROOT).as_posix())
    duplicates = [names for names in hashes.values() if len(names) > 1]
    for names in duplicates:
        failures.append("Contenido duplicado: " + " | ".join(sorted(names)))

    result = {
        "status": "PASS" if not failures else "FAIL",
        "public_files": len(paths),
        "public_size_MiB": round(sum(path.stat().st_size for path in paths) / 1024**2, 2),
        "raw_data_files": sum(path.suffix.lower() in RAW_SUFFIXES for path in paths),
        "figures_validated": len(public_figures),
        "failures": failures,
        "duplicate_content_groups": len(duplicates),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
