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


class TestCmbE2DriftConstrainedClosureBound(unittest.TestCase):
    def test_scan_outputs_manifest_and_pareto_files(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        try:
            import matplotlib  # noqa: F401
        except Exception:
            self.skipTest("matplotlib not installed")

        import cmb_e2_drift_constrained_closure_bound as bound  # noqa: E402

        cmb_csv = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        cmb_cov = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
        self.assertTrue(cmb_csv.exists())
        self.assertTrue(cmb_cov.exists())

        base = ROOT / "results/diagnostic_cmb_drift_constrained_bound_test"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(base)) as td:
            out_dir = Path(td)
            self.assertTrue(str(out_dir.resolve()).startswith(str(REPO_ROOT.resolve())))

            manifest = bound.run(
                cmb_csv=cmb_csv,
                cmb_cov=cmb_cov,
                out_dir=out_dir,
                p_late=0.6,
                z_transition=1.8,
                H0_km_s_Mpc=67.4,
                Omega_m=0.315,
                omega_b_h2=0.02237,
                omega_c_h2=0.1200,
                Neff=3.046,
                Tcmb_K=2.7255,
                z_window_min=2.0,
                z_window_max=5.0,
                z_handoff=5.0,
                epsilon_cap=1.0e-6,
                s_values=[0.0, 0.5, 0.99],
                n_D_M=512,
                n_r_s=512,
                rs_star_calibration=bound._RS_STAR_CALIB_CHW2018,
            )

            table = out_dir / "tables/cmb_drift_constrained_bound_scan.csv"
            fig1 = out_dir / "figures/chi2_cmb_vs_dv_z4.png"
            fig2 = out_dir / "figures/pulls_vs_dv_z4.png"
            fig3 = out_dir / "figures/DM_star_vs_s.png"
            man_path = out_dir / "manifest.json"

            self.assertTrue(table.exists())
            self.assertTrue(fig1.exists())
            self.assertTrue(fig2.exists())
            self.assertTrue(fig3.exists())
            self.assertTrue(man_path.exists())
            self.assertEqual(manifest.get("kind"), "cmb_e2_drift_constrained_closure_bound")

            with table.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)

            # Drift amplitude should move monotonically toward zero as s increases.
            rows_sorted = sorted(rows, key=lambda r: float(r["s"]))
            dv4 = [float(r["dv_z4_cm_s_10y"]) for r in rows_sorted]
            self.assertGreater(dv4[0], dv4[-1])

            obj = json.loads(man_path.read_text(encoding="utf-8"))
            self.assertEqual(obj.get("kind"), "cmb_e2_drift_constrained_closure_bound")
            self.assertTrue(bool(obj.get("diagnostic_only")))

            # Portability: no machine-local paths.
            blob = json.dumps(obj, sort_keys=True)
            self.assertNotIn("/Users/", blob)
            self.assertNotIn(":\\\\", blob)


if __name__ == "__main__":
    unittest.main()
