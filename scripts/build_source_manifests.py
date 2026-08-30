"""Construye manifiestos publicos a partir de insumos locales, sin copiarlos.

El manifiesto CMIP6 conserva el ``zstore`` exacto registrado en los atributos
de cada NetCDF usado por el ensamble canonico. El manifiesto ERA5-Land describe
las 136 solicitudes (4 variables x 34 anios) que reconstruyen la referencia.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reproducibilidad.config import CANONICAL_MODELS, PROJECT_ROOT


DATA_DIR = PROJECT_ROOT / "data"
CMIP6_DIR = PROJECT_ROOT / "CMIP6_Guajira"
ERA5_DATASET = "derived-era5-land-daily-statistics"
ERA5_DOI = "10.24381/cds.e9c9c792"
ERA5_VARIABLES = (
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
    "surface_pressure",
)
AREA = (12.125, -71.9583, 12.1166667, -71.95)


def _attr(dataset: Dataset, name: str) -> str:
    return str(dataset.getncattr(name)) if name in dataset.ncattrs() else ""


def build_cmip6_manifest() -> Path:
    rows: list[dict[str, object]] = []
    prefixes = tuple(f"{model}_" for model in CANONICAL_MODELS)
    for path in sorted(CMIP6_DIR.glob("*.nc")):
        if not path.name.startswith(prefixes):
            continue
        with Dataset(path, mode="r") as dataset:
            zstore = _attr(dataset, "intake_esm_attrs:zstore")
            if not zstore:
                activity = _attr(dataset, "activity_id")
                institution = _attr(dataset, "institution_id")
                source = _attr(dataset, "source_id")
                experiment = _attr(dataset, "experiment_id")
                member = _attr(dataset, "variant_label")
                table = _attr(dataset, "table_id")
                variable = _attr(dataset, "variable_id")
                grid = _attr(dataset, "grid_label")
                version = _attr(dataset, "version") or _attr(dataset, "version_id")
                version = version if version.startswith("v") else f"v{version}"
                zstore = (
                    "gs://cmip6/CMIP6/"
                    f"{activity}/{institution}/{source}/{experiment}/{member}/"
                    f"{table}/{variable}/{grid}/{version}/"
                )
            rows.append(
                {
                    "local_file": path.relative_to(PROJECT_ROOT).as_posix(),
                    "source_id": _attr(dataset, "intake_esm_attrs:source_id")
                    or _attr(dataset, "source_id"),
                    "institution_id": _attr(dataset, "intake_esm_attrs:institution_id")
                    or _attr(dataset, "institution_id"),
                    "activity_id": _attr(dataset, "intake_esm_attrs:activity_id")
                    or _attr(dataset, "activity_id"),
                    "experiment_id": _attr(dataset, "intake_esm_attrs:experiment_id")
                    or _attr(dataset, "experiment_id"),
                    "variable_id": _attr(dataset, "intake_esm_attrs:variable_id")
                    or _attr(dataset, "variable_id"),
                    "table_id": _attr(dataset, "intake_esm_attrs:table_id")
                    or _attr(dataset, "table_id"),
                    "member_id": _attr(dataset, "intake_esm_attrs:member_id")
                    or _attr(dataset, "variant_label"),
                    "grid_label": _attr(dataset, "intake_esm_attrs:grid_label")
                    or _attr(dataset, "grid_label"),
                    "version": _attr(dataset, "intake_esm_attrs:version")
                    or _attr(dataset, "version")
                    or _attr(dataset, "version_id"),
                    "zstore": zstore,
                    "license_from_source": _attr(dataset, "license"),
                }
            )
    if not rows:
        raise FileNotFoundError("No se encontraron NetCDF CMIP6 locales para crear el manifiesto.")
    output = DATA_DIR / "cmip6_source_manifest.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output


def build_era5_manifest() -> Path:
    rows = []
    north, west, south, east = AREA
    for variable in ERA5_VARIABLES:
        for year in range(1981, 2015):
            rows.append(
                {
                    "dataset_id": ERA5_DATASET,
                    "doi": ERA5_DOI,
                    "variable": variable,
                    "year": year,
                    "daily_statistic": "daily_mean",
                    "time_zone": "utc+00:00",
                    "frequency": "1_hourly",
                    "north": north,
                    "west": west,
                    "south": south,
                    "east": east,
                    "target_file": f"Datos_Era5/era5land_diario_guajira_{variable}_{year}.nc",
                }
            )
    output = DATA_DIR / "era5_request_manifest.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output


def main() -> None:
    cmip6 = build_cmip6_manifest()
    era5 = build_era5_manifest()
    print(f"[OK] {cmip6.relative_to(PROJECT_ROOT)}")
    print(f"[OK] {era5.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
