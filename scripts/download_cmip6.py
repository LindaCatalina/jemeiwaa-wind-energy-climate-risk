"""Reconstruye subconjuntos CMIP6 desde los zstores exactos del manifiesto."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reproducibilidad.config import PROJECT_ROOT


MANIFEST = PROJECT_ROOT / "data" / "cmip6_source_manifest.csv"
LATITUDE = (12.125 + 12.1166667) / 2
LONGITUDE = (-71.9583 + -71.95) / 2


def _point_subset(dataset: xr.Dataset) -> xr.Dataset:
    if "lat" not in dataset.coords or "lon" not in dataset.coords:
        raise ValueError("El zstore no contiene coordenadas lat/lon.")
    lon = dataset["lon"]
    target_lon = LONGITUDE % 360 if float(lon.min()) >= 0 and LONGITUDE < 0 else LONGITUDE
    if dataset["lat"].ndim != 1 or dataset["lon"].ndim != 1:
        raise ValueError("Este flujo reproduce solo rejillas atmosfericas lat/lon 1D.")
    i_lat = int(np.abs(dataset["lat"].values - LATITUDE).argmin())
    i_lon = int(np.abs(dataset["lon"].values - target_lon).argmin())
    return dataset.isel(lat=i_lat, lon=i_lon)


def _time_subset(dataset: xr.Dataset, experiment: str) -> xr.Dataset:
    start, end = (
        ("1981-01-01", "2014-12-31")
        if experiment == "historical"
        else ("2015-01-01", "2100-12-31")
    )
    return dataset.sel(time=slice(start, end))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga el ensamble CMIP6 exacto registrado en data/."
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra el plan.")
    parser.add_argument("--limit", type=int, help="Maximo de archivos; util para pruebas.")
    args = parser.parse_args()

    with MANIFEST.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if args.limit is not None:
        rows = rows[: args.limit]
    print(f"Subconjuntos CMIP6 por reconstruir: {len(rows)}")
    if args.dry_run:
        for row in rows[:5]:
            print(f"- {row['local_file']} <- {row['zstore']}")
        return 0

    for index, row in enumerate(rows, start=1):
        target = PROJECT_ROOT / row["local_file"]
        if target.is_file() and target.stat().st_size > 100:
            print(f"[{index}/{len(rows)}] ya existe: {target.name}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{index}/{len(rows)}] {target.name}")
        dataset = xr.open_zarr(
            row["zstore"],
            consolidated=True,
            chunks={},
            storage_options={"token": "anon"},
        )
        subset = _time_subset(_point_subset(dataset), row["experiment_id"])
        variable = row["variable_id"]
        if variable not in subset:
            raise KeyError(f"{variable} no esta disponible en {row['zstore']}")
        subset[[variable]].to_netcdf(target)
        dataset.close()

    print("[OK] Descarga CMIP6 completa.")
    print("Siguiente paso: python run_reproducible.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
