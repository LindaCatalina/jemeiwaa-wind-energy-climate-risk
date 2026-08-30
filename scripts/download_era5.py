"""Descarga ERA5-Land diario de forma portable usando el manifiesto publico."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reproducibilidad.config import PROJECT_ROOT


MANIFEST = PROJECT_ROOT / "data" / "era5_request_manifest.csv"
MONTHS = [f"{month:02d}" for month in range(1, 13)]
DAYS = [f"{day:02d}" for day in range(1, 32)]


def _valid_netcdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100:
        return False
    with path.open("rb") as stream:
        header = stream.read(8)
    return header.startswith(b"CDF") or header.startswith(b"\x89HDF")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconstruye los archivos ERA5-Land 1981-2014 desde CDS."
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra el plan.")
    parser.add_argument("--max-retries", type=int, default=5)
    args = parser.parse_args()

    with MANIFEST.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    print(f"Solicitudes ERA5-Land: {len(rows)}")
    if args.dry_run:
        print(f"Primera salida: {rows[0]['target_file']}")
        print(f"Ultima salida:  {rows[-1]['target_file']}")
        return 0

    try:
        import cdsapi
    except ImportError as exc:
        raise SystemExit("Instale requirements-download.txt antes de descargar.") from exc

    client = cdsapi.Client()
    for index, row in enumerate(rows, start=1):
        target = PROJECT_ROOT / row["target_file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if _valid_netcdf(target):
            print(f"[{index}/{len(rows)}] ya existe: {target.name}")
            continue
        request = {
            "variable": [row["variable"]],
            "year": row["year"],
            "month": MONTHS,
            "day": DAYS,
            "daily_statistic": row["daily_statistic"],
            "time_zone": row["time_zone"],
            "frequency": row["frequency"],
            "area": [
                float(row["north"]),
                float(row["west"]),
                float(row["south"]),
                float(row["east"]),
            ],
            "data_format": "netcdf",
            "download_format": "unarchived",
        }
        for attempt in range(1, args.max_retries + 1):
            print(f"[{index}/{len(rows)}] {row['variable']} {row['year']} (intento {attempt})")
            try:
                client.retrieve(row["dataset_id"], request, str(target))
            except Exception as exc:
                print(f"  advertencia: {exc}")
            if _valid_netcdf(target):
                break
            if target.exists():
                target.unlink()
            if attempt < args.max_retries:
                time.sleep(30)
        else:
            raise RuntimeError(f"No se pudo descargar {target.name}")

    print("[OK] Descarga ERA5-Land completa.")
    print("Siguiente paso: python Datos_Era5/unificar_era5_guajira.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
