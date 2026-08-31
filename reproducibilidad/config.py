"""Configuración central del análisis reproducible."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ERA5_DIR = PROJECT_ROOT / "Datos_Era5"
CMIP6_DIR = PROJECT_ROOT / "CMIP6_Guajira"
CORRECTED_DIR = CMIP6_DIR / "corrected"
RESULTS_DIR = PROJECT_ROOT / "results"

# Es el conjunto de 12 modelos utilizado en las figuras y conclusiones de la
# presentación. Se fija explícitamente para evitar que un ranking cambie el
# ensamble de forma silenciosa al agregar o quitar archivos.
CANONICAL_MODELS = (
    "ACCESS-CM2",
    "CanESM5",
    "CESM2",
    "CESM2-WACCM",
    "CMCC-CM2-SR5",
    "CMCC-ESM2",
    "EC-Earth3",
    "IPSL-CM6A-LR",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MPI-ESM1-2-LR",
    "NorESM2-MM",
)

SCENARIOS = ("ssp126", "ssp245", "ssp585")
EXPERIMENTS = ("historical",) + SCENARIOS
HORIZONS = {
    "historico": (1981, 2014),
    "medio": (2040, 2069),
    "lejano": (2070, 2099),
}

RATING_MW = 6.8
N_TURBINES = 162
PLANT_CAPACITY_MW = RATING_MW * N_TURBINES
ALPHA = 0.14
Z_REF_M = 10.0
Z_HUB_M = 150.0
LOSSES = 0.10
RHO_REF = 1.225
