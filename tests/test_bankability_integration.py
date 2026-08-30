from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from bankability.pipeline import run_preliminary_assessment


class BankabilityIntegrationTests(unittest.TestCase):
    def test_complete_synthetic_inputs_produce_ordered_preliminary_percentiles(self):
        """Ejercita la rama completa sin usar ni alterar datos del proyecto."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            timestamps = pd.date_range(
                "2000-01-01 00:00", "2009-12-31 23:50", freq="10min", tz="UTC"
            )
            phase = np.arange(len(timestamps), dtype=float)
            wind = pd.DataFrame(
                {
                    "timestamp_utc": timestamps,
                    "wind_speed_hub_m_s": 9.0 + 1.5 * np.sin(2 * np.pi * phase / 52596),
                    "wind_direction_deg": np.mod(45.0 + phase / 100, 360.0),
                    "air_density_kg_m3": 1.18 + 0.02 * np.cos(2 * np.pi * phase / 52596),
                }
            )
            wind_path = root / "wind.csv"
            wind.to_csv(wind_path, index=False)

            speeds = np.arange(0.0, 30.5, 0.5)
            power = np.where(
                speeds < 3.0,
                0.0,
                np.where(speeds < 12.0, 6800.0 * ((speeds - 3.0) / 9.0) ** 3, 6800.0),
            )
            power = np.where(speeds > 25.0, 0.0, power)
            curve_path = root / "curve.csv"
            pd.DataFrame({"wind_speed_m_s": speeds, "power_kw": power}).to_csv(
                curve_path, index=False
            )

            loss = lambda mean: {
                "mean_fraction": mean,
                "std_fraction": 0.002,
                "evidence": "Documento de prueba controlado",
            }
            config = {
                "project": {"turbine_count": 162, "rated_power_kw": 6800},
                "wind_resource": {
                    "time_series_csv": str(wind_path),
                    "source_document": "Campaña y MCP de prueba",
                    "measurement_campaign_months": 12,
                    "long_term_reference_years": 10,
                },
                "certified_power_curve": {
                    "csv": str(curve_path),
                    "certificate_document": "Certificado de prueba",
                    "reference_air_density_kg_m3": 1.225,
                },
                "losses": {
                    "wake": loss(0.07),
                    "availability": loss(0.03),
                    "electrical": loss(0.02),
                    "turbine_performance": loss(0.01),
                    "environmental": loss(0.005),
                    "curtailment": loss(0.01),
                },
                "uncertainties": {
                    "resource_measurement": 0.02,
                    "long_term_correction": 0.03,
                    "vertical_extrapolation": 0.02,
                    "power_curve_model": 0.02,
                },
                "simulation": {"n_samples": 10000, "seed": 1234},
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            output = root / "output"

            status = run_preliminary_assessment(config_path, output)
            summary = status["preliminary_summary"]
            self.assertTrue(status["financial_p90_calculated"])
            self.assertFalse(status["bankable"])
            self.assertLess(summary["P90_exceedance_GWh"], summary["P50_exceedance_GWh"])
            self.assertLess(summary["P50_exceedance_GWh"], summary["P10_exceedance_GWh"])
            self.assertTrue((output / "curva_excedencia_preliminar.png").is_file())
            self.assertTrue((output / "energia_bruta_anual_preliminar.csv").is_file())


if __name__ == "__main__":
    unittest.main()

