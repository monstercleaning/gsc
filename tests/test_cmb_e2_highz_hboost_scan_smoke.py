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


class TestCmbE2HighZHBoostScanSmoke(unittest.TestCase):
    def test_scan_writes_expected_artifacts_and_manifest_is_portable(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        try:
            import matplotlib  # noqa: F401
        except Exception:
            self.skipTest("matplotlib not installed")

        import cmb_e2_highz_hboost_repair_scan as scan  # noqa: E402

        cmb_csv = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        cmb_cov = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
        self.assertTrue(cmb_csv.exists())
        self.assertTrue(cmb_cov.exists())

        base_results = ROOT / "results/diagnostic_cmb_highz_hboost_repair"
        base_results.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=str(base_results)) as td:
            out_dir = Path(td)
            # Must be repo-relative for manifest hygiene checks.
            self.assertTrue(str(out_dir.resolve()).startswith(str(REPO_ROOT.resolve())))

            manifest = scan.run(
                cmb_csv=cmb_csv,
                cmb_cov=cmb_cov,
                out_dir=out_dir,
                p_late=0.6,
                z_transition=1.8,
                z_relax_start=5.0,
                relax_scale=0.5,
                p_target=1.5,
                z_bbn_clamp=1.0e7,
                z_boost_start_list=[5.0],
                A_min=1.00,
                A_max=1.00,
                A_step=0.1,
                transition_width=0.0,
                H0_km_s_Mpc=67.4,
                Omega_m=0.315,
                omega_b_h2=0.02237,
                omega_c_h2=0.1200,
                Neff=3.046,
                Tcmb_K=2.7255,
                n_D_M=512,
                n_r_s=512,
                rs_star_calibration=scan._RS_STAR_CALIB_CHW2018,
            )

            # Basic manifest sanity.
            man_path = out_dir / "manifest.json"
            self.assertTrue(man_path.exists())
            obj = json.loads(man_path.read_text(encoding="utf-8"))
            self.assertTrue(bool(obj.get("diagnostic_only")))
            self.assertEqual(obj.get("kind"), "cmb_e2_highz_hboost_repair_scan")

            # Required output files exist.
            table = out_dir / "tables/cmb_highz_hboost_scan.csv"
            fig1 = out_dir / "figures/chi2_vs_A_by_zbooststart.png"
            fig2 = out_dir / "figures/drift_vs_A.png"
            self.assertTrue(table.exists())
            self.assertTrue(fig1.exists())
            self.assertTrue(fig2.exists())

            # CSV has at least 1 data row.
            with table.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            self.assertGreaterEqual(len(rows), 1)

            # Portability: no machine-local absolute paths in the manifest.
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
                # Path-like values should be relative.
                if s.startswith(str(REPO_ROOT)):
                    self.fail(f"unexpected absolute repo path in manifest: {s}")

            # Ensure the returned manifest matches the file.
            self.assertEqual(manifest.get("kind"), obj.get("kind"))


if __name__ == "__main__":
    unittest.main()
