import csv
import json
import unittest
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import drift_forecast_fisher as dff  # noqa: E402


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            yield from _walk_strings(x)


class TestDriftForecastFisher(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import matplotlib  # noqa: F401
        except Exception:
            self.skipTest("matplotlib not installed")

    def test_writes_outputs_and_is_monotonic_in_years(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            manifest = dff.run(
                out_dir=out_dir,
                z_targets=[2.0, 3.0],
                years_list=[5.0, 10.0],
                sigma_stat_cm_s=1.0,
                sigma_sys_cm_s_list=[0.0, 1.0],
                model_a="lcdm",
                model_b="gsc_powerlaw",
                H0_km_s_Mpc=67.4,
                Omega_m=0.315,
                p=0.6,
                z_transition=1.8,
            )

            self.assertEqual(manifest.get("kind"), "drift_forecast_fisher")
            self.assertTrue((out_dir / "manifest.json").is_file())
            self.assertTrue((out_dir / "tables" / "significance_vs_years.csv").is_file())
            self.assertTrue((out_dir / "figures" / "significance_vs_years.png").is_file())

            obj = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            s = json.dumps(obj, sort_keys=True)
            self.assertNotIn("/Users/", s)
            self.assertNotIn("C:\\\\", s)
            for v in _walk_strings(obj):
                self.assertNotIn("/Users/", v)
                self.assertNotIn("C:\\\\", v)

            # Monotonic: significance(10y) > significance(5y) for each scenario.
            by_scenario = {}
            with (out_dir / "tables" / "significance_vs_years.csv").open("r", encoding="utf-8", newline="") as f:
                r = csv.DictReader(f)
                for row in r:
                    scen = row["scenario"]
                    years = float(row["years"])
                    sig = float(row["significance_sigma"])
                    by_scenario.setdefault(scen, {})[years] = sig

            self.assertGreater(len(by_scenario), 0)
            for scen, m in by_scenario.items():
                self.assertIn(5.0, m, msg=scen)
                self.assertIn(10.0, m, msg=scen)
                self.assertGreater(m[10.0], m[5.0], msg=scen)


if __name__ == "__main__":
    unittest.main()

