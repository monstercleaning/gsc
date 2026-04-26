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


class TestCmbE2ClosureRequirementsPlot(unittest.TestCase):
    def test_writes_outputs_and_manifest_is_portable(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        try:
            import matplotlib  # noqa: F401
        except Exception:
            self.skipTest("matplotlib not installed")

        import cmb_e2_closure_requirements_plot as ws13  # noqa: E402

        e24_csv = ROOT / "results/late_time_fit_cmb_e2_closure_diagnostic/scan/tables/cmb_e2_dm_rs_fit_scan.csv"
        if not e24_csv.exists():
            self.skipTest(f"missing required E2.4 CSV: {e24_csv}")

        base = ROOT / "results/diagnostic_cmb_e2_closure_requirements_test"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(base)) as td:
            out_dir = Path(td)
            self.assertTrue(str(out_dir.resolve()).startswith(str(REPO_ROOT.resolve())))

            ws13.run(
                e24_scan_csv=e24_csv,
                out_dir=out_dir,
                quantiles=[0.5],
                dm_targets_explicit=[0.9290939714464278],
                z_boost_starts=[5.0, 10.0],
                model="gsc_transition",
                H0_km_s_Mpc=67.4,
                Omega_m=0.315,
                Omega_L=0.685,
                gsc_p=0.6,
                gsc_ztrans=1.8,
                cmb_bridge_z=5.0,
                omega_b_h2=0.02237,
                omega_c_h2=0.1200,
                Neff=3.046,
                Tcmb_K=2.7255,
            )

            table = out_dir / "tables/A_required_vs_zstart.csv"
            summary = out_dir / "tables/A_required_summary.csv"
            fig = out_dir / "figures/A_required_vs_zstart.png"
            manifest = out_dir / "manifest.json"
            self.assertTrue(table.exists())
            self.assertTrue(summary.exists())
            self.assertTrue(fig.exists())
            self.assertTrue(manifest.exists())

            with table.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertGreaterEqual(len(rows), 2)

            obj = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(obj.get("kind"), "cmb_e2_closure_requirements")
            self.assertTrue(bool(obj.get("diagnostic_only")))

            def walk(x):
                if isinstance(x, dict):
                    for v in x.values():
                        yield from walk(v)
                elif isinstance(x, list):
                    for v in x:
                        yield from walk(v)
                elif isinstance(x, str):
                    yield x

            for s in walk(obj):
                self.assertNotIn("/Users/", s)
                self.assertNotIn(":\\\\", s)
                if s.startswith(str(REPO_ROOT)):
                    self.fail(f"unexpected absolute repo path in manifest: {s}")


if __name__ == "__main__":
    unittest.main()

