import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))


class TestE2DriftBoundAnalytic(unittest.TestCase):
    def test_formula_lock(self):
        import e2_drift_bound_analytic as m  # noqa: E402

        got = m.delta_chi_min_mpc(H0_km_s_Mpc=67.4, z1=2.0, z2=5.0)
        expected = (299792.458 / 67.4) * math.log(2.0)
        self.assertAlmostEqual(got, expected, places=12)

    def test_run_writes_outputs_and_manifest(self):
        import e2_drift_bound_analytic as m  # noqa: E402

        base = ROOT / "results/diagnostic_e2_drift_bound_analytic_test"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(base)) as td:
            out = Path(td)
            self.assertTrue(str(out.resolve()).startswith(str(REPO_ROOT.resolve())))

            manifest = m.run(
                out_dir=out,
                z1=2.0,
                z2=5.0,
                h0_values=[60.0, 67.4, 75.0],
                reference_h0=67.4,
            )
            self.assertEqual(manifest.get("kind"), "e2_drift_bound_analytic")

            csv_path = out / "tables/drift_bound_analytic_h0_scan.csv"
            txt_path = out / "tables/summary.txt"
            man_path = out / "manifest.json"
            self.assertTrue(csv_path.exists())
            self.assertTrue(txt_path.exists())
            self.assertTrue(man_path.exists())

            with csv_path.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)

            vals = [float(r["delta_chi_min_Mpc"]) for r in rows]
            # Bound must decrease with increasing H0.
            self.assertGreater(vals[0], vals[-1])

            obj = json.loads(man_path.read_text(encoding="utf-8"))
            blob = json.dumps(obj, sort_keys=True)
            self.assertNotIn("/Users/", blob)
            self.assertNotIn(":\\\\", blob)


if __name__ == "__main__":
    unittest.main()
