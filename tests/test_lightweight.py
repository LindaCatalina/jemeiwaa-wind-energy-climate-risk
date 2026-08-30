from __future__ import annotations

import csv
import unittest
from pathlib import Path

import numpy as np
import xarray as xr

from bankability.pipeline import evaluate_readiness
from reproducibilidad.core import cf_from_wind_reference_density
from run_portfolio import load_tables, validate_figures


ROOT = Path(__file__).resolve().parents[1]


class LightweightTests(unittest.TestCase):
    def test_proxy_curve_stays_within_legacy_physical_bounds(self):
        wind = xr.DataArray(np.linspace(0, 30, 301), dims="time")
        cf = cf_from_wind_reference_density(wind)
        self.assertGreaterEqual(float(cf.min()), 0.0)
        self.assertLessEqual(float(cf.max()), 0.9 + 1e-12)

    def test_public_bankability_config_refuses_financial_p90(self):
        _, status = evaluate_readiness(ROOT / "bankability" / "config.example.json")
        self.assertFalse(status["ready_for_preliminary_p90"])
        self.assertFalse(status["financial_p90_calculated"])
        self.assertFalse(status["bankable"])
        blocker_ids = {item["id"] for item in status["blockers"]}
        self.assertIn("wind.file_exists", blocker_ids)
        self.assertIn("curve.certificate_documented", blocker_ids)
        self.assertIn("loss.wake.values", blocker_ids)
        self.assertIn("loss.availability.values", blocker_ids)
        self.assertIn("loss.electrical.values", blocker_ids)

    def test_public_source_manifests_are_complete(self):
        expected = {
            "data/era5_request_manifest.csv": 136,
            "data/cmip6_source_manifest.csv": 215,
        }
        for relative, count in expected.items():
            with (ROOT / relative).open(encoding="utf-8", newline="") as stream:
                self.assertEqual(sum(1 for _ in csv.DictReader(stream)), count)

    def test_portfolio_tables_and_figures_are_valid(self):
        tables = load_tables()
        self.assertEqual(len(tables["legacy_change"]), 6)
        self.assertEqual(len(tables["sensitivity_monthly"]), 84)
        validate_figures()


if __name__ == "__main__":
    unittest.main()
