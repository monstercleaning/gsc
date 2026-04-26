import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


class TestCmbE2ClosureToPhysicalKnobs(unittest.TestCase):
    def test_translates_A_to_deltaG_and_writes_outputs(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        try:
            import matplotlib  # noqa: F401
        except Exception:
            self.skipTest("matplotlib not installed")

        import cmb_e2_closure_to_physical_knobs as tr  # noqa: E402

        base = ROOT / "results/diagnostic_cmb_e2_closure_to_physical_knobs_test"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(base)) as td:
            td_path = Path(td)
            ws13_table = td_path / "A_required_vs_zstart.csv"
            with ws13_table.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=[
                        "target_label",
                        "target_source",
                        "dm_target",
                        "z_boost_start",
                        "A_required_const",
                        "deltaH_over_H",
                        "bridge_z_used",
                        "z_star",
                    ],
                )
                w.writeheader()
                w.writerow(
                    {
                        "target_label": "q50",
                        "target_source": "e2.4_quantile",
                        "dm_target": "0.9438",
                        "z_boost_start": "5",
                        "A_required_const": "1.2",
                        "deltaH_over_H": "0.2",
                        "bridge_z_used": "5",
                        "z_star": "1090",
                    }
                )
                w.writerow(
                    {
                        "target_label": "q50",
                        "target_source": "e2.4_quantile",
                        "dm_target": "0.9438",
                        "z_boost_start": "10",
                        "A_required_const": "1.33",
                        "deltaH_over_H": "0.33",
                        "bridge_z_used": "5",
                        "z_star": "1090",
                    }
                )

            out_dir = td_path / "out"
            self.assertTrue(str(out_dir.resolve()).startswith(str(REPO_ROOT.resolve())))
            tr.run(ws13_table_csv=ws13_table, out_dir=out_dir)

            table = out_dir / "tables/closure_to_knobs_summary.csv"
            piv = out_dir / "tables/closure_to_knobs_by_zstart.csv"
            fig1 = out_dir / "figures/deltaG_required_vs_dm_target.png"
            fig2 = out_dir / "figures/deltaG_required_vs_z_start.png"
            man_path = out_dir / "manifest.json"
            self.assertTrue(table.exists())
            self.assertTrue(piv.exists())
            self.assertTrue(fig1.exists())
            self.assertTrue(fig2.exists())
            self.assertTrue(man_path.exists())

            with table.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)

            # Formula lock: deltaG = A^2 - 1.
            a0 = float(rows[0]["A_required_const"])
            dg0 = float(rows[0]["deltaG_required"])
            self.assertAlmostEqual(dg0, a0 * a0 - 1.0, places=12)

            obj = json.loads(man_path.read_text(encoding="utf-8"))
            self.assertEqual(obj.get("kind"), "cmb_e2_closure_to_physical_knobs")
            self.assertTrue(bool(obj.get("diagnostic_only")))

            s = json.dumps(obj, sort_keys=True)
            self.assertNotIn("/Users/", s)
            self.assertNotIn(":\\\\", s)


if __name__ == "__main__":
    unittest.main()
