from __future__ import annotations

import csv
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from reproducibilidad.config import PLANT_CAPACITY_MW, RESULTS_DIR
from reproducibilidad.core import (
    daily_cf_from_mean_hub_wind,
    deterministic_weibull_multipliers,
)
from scripts.rebuild_figures import validate_figures, validate_tables


ROOT = Path(__file__).resolve().parents[1]


class LightweightTests(unittest.TestCase):
    def test_subdaily_states_conserve_daily_mean_exactly(self):
        multipliers = deterministic_weibull_multipliers()
        self.assertEqual(len(multipliers), 144)
        self.assertAlmostEqual(float(multipliers.mean()), 1.0, places=14)
        daily_means = np.array([3.0, 7.5, 12.0])
        reconstructed = daily_means[:, None] * multipliers[None, :]
        np.testing.assert_allclose(reconstructed.mean(axis=1), daily_means, rtol=1e-14)

    def test_integrated_cf_has_physical_bounds(self):
        wind_hub = xr.DataArray(np.linspace(0, 30, 301), dims="time")
        cf = daily_cf_from_mean_hub_wind(wind_hub)
        self.assertGreaterEqual(float(cf.min()), 0.0)
        self.assertLessEqual(float(cf.max()), 0.9 + 1e-12)

    def test_public_source_manifests_are_complete(self):
        expected = {
            "data/era5_request_manifest.csv": 136,
            "data/cmip6_source_manifest.csv": 215,
        }
        for relative, count in expected.items():
            with (ROOT / relative).open(encoding="utf-8", newline="") as stream:
                self.assertEqual(sum(1 for _ in csv.DictReader(stream)), count)

    def test_energy_is_consistent_with_cf(self):
        annual = pd.read_csv(RESULTS_DIR / "tables/metricas_anuales.csv")
        expected = annual["cf_annual"] * PLANT_CAPACITY_MW * 8760.0 / 1000.0
        np.testing.assert_allclose(annual["energy_equivalent_GWh"], expected, rtol=1e-12)

    def test_public_tables_and_figures_are_valid(self):
        validate_tables()
        validate_figures()


if __name__ == "__main__":
    unittest.main()
