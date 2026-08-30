from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
import xarray as xr

from reproducibilidad.config import CANONICAL_MODELS, ERA5_DIR, LEGACY_SPLIT_TABLE
from reproducibilidad.core import cf_from_wind_reference_density, extrapolate_to_hub
from reproducibilidad.percentiles import summarize_energy


class ReproducibilityTests(unittest.TestCase):
    def test_era5_time_and_formulas(self):
        ds = xr.open_dataset(ERA5_DIR / "era5_guajira_daily_1981_2014.nc")
        alt = xr.open_dataset(ERA5_DIR / "era5_guajira_daily_1981_2014_150m.nc")
        try:
            self.assertEqual(ds.sizes["time"], 12418)
            self.assertEqual(float(abs(np.hypot(ds.u10, ds.v10) - ds.wind10).max()), 0.0)
            self.assertEqual(float(abs(extrapolate_to_hub(ds.wind10) - alt.v150_power).max()), 0.0)
        finally:
            ds.close()
            alt.close()

    def test_power_curve_physical_bounds(self):
        v10 = xr.DataArray(np.linspace(0, 30, 301), dims="time", coords={"time": np.arange(301)})
        cf = cf_from_wind_reference_density(v10)
        self.assertGreaterEqual(float(cf.min()), 0.0)
        self.assertLessEqual(float(cf.max()), 0.9 + 1e-12)

    def test_legacy_table_has_12_models_and_future_pairs(self):
        df = pd.read_csv(LEGACY_SPLIT_TABLE)
        self.assertEqual(set(df.model), set(CANONICAL_MODELS))
        hist = df[(df.exp == "historical") & (df.horizon == "hist")][["model", "cf_mean"]]
        fut = df[(df.exp != "historical") & (df.horizon != "hist")]
        paired = fut.merge(hist, on="model")
        self.assertEqual(len(paired), 72)

    def test_p90_exceedance_is_q10(self):
        rows = []
        for model_index, model in enumerate(CANONICAL_MODELS):
            for year in range(2000, 2003):
                rows.append(
                    {
                        "model": model,
                        "scenario": "historical",
                        "horizon": "historico",
                        "year": year,
                        "energy_plant_GWh": 1000 + 10 * model_index + year - 2000,
                    }
                )
        ensemble, interannual = summarize_energy(pd.DataFrame(rows))
        self.assertAlmostEqual(
            float(ensemble.loc[0, "P90_exceedance_GWh"]), float(ensemble.loc[0, "q10"])
        )
        self.assertTrue((interannual["P90_exceedance_GWh"] <= interannual["P50_exceedance_GWh"]).all())


if __name__ == "__main__":
    unittest.main()

