import json
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402

import cmb_dm_rs_star_fit_diagnostic as diag  # noqa: E402


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


class TestCMBDmRsFitDiagnostic(unittest.TestCase):
    def setUp(self) -> None:
        self.chw_csv = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        self.chw_cov = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
        self.ds = CMBPriorsDataset.from_csv(self.chw_csv, cov_path=self.chw_cov, name="cmb_chw2018")

    def test_joint_fit_is_deterministic_and_improves_chi2(self):
        pred_raw = diag._compute_pred_raw(
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

        r1, _ = diag.joint_fit_dm_rs_star_calibration(
            ds=self.ds,
            pred_raw=pred_raw,
            rs_min=0.95,
            rs_max=1.15,
            rs_step=0.001,
        )
        r2, _ = diag.joint_fit_dm_rs_star_calibration(
            ds=self.ds,
            pred_raw=pred_raw,
            rs_min=0.95,
            rs_max=1.15,
            rs_step=0.001,
        )

        self.assertAlmostEqual(r1.dm_star_calibration_fit, r2.dm_star_calibration_fit, places=15)
        self.assertAlmostEqual(r1.rs_star_calibration_fit, r2.rs_star_calibration_fit, places=15)
        self.assertAlmostEqual(r1.chi2_min, r2.chi2_min, places=12)

        self.assertLessEqual(float(r1.chi2_min), float(r1.chi2_base) + 1e-12)
        self.assertGreater(float(r1.dm_star_calibration_fit), 0.0)
        self.assertGreater(float(r1.rs_star_calibration_fit), 0.0)

        # omega_b_h2 is unaffected by dm/rs (by construction); its diag pull should not move.
        self.assertAlmostEqual(
            float(r1.pulls_base.get("omega_b_h2", float("nan"))),
            float(r1.pulls_fit.get("omega_b_h2", float("nan"))),
            places=12,
        )

    def test_manifest_has_required_keys_and_repo_relative_paths(self):
        pred_raw = diag._compute_pred_raw(
            model="lcdm",
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
        r, grid = diag.joint_fit_dm_rs_star_calibration(
            ds=self.ds,
            pred_raw=pred_raw,
            rs_min=0.99,
            rs_max=1.01,
            rs_step=0.0005,
        )
        # Minimal fake output paths under the repo to ensure repo-relative serialization.
        out_dir = ROOT / "results" / "diagnostic_cmb_e2_dm_rs_star_fit"
        grid_csv = out_dir / "tables" / "cmb_e2_dm_rs_fit_grid.csv"
        plot_path = out_dir / "figures" / "chi2_vs_rs_star_calibration.png"

        manifest = diag._manifest_obj(
            cmb_csv=self.chw_csv,
            cmb_cov=self.chw_cov,
            model_cfg={"model": "lcdm"},
            baseline_cfg={"dm_star_calibration": 1.0, "rs_star_calibration": float(diag._RS_STAR_CALIB_CHW2018)},
            fit_cfg={"rs_grid": {"min": 0.99, "max": 1.01, "step": 0.0005}},
            result=r,
            out_dir=out_dir,
            grid_csv=grid_csv,
            plot_path=plot_path,
        )

        # Required top-level keys.
        self.assertTrue(bool(manifest.get("diagnostic_only")))
        self.assertTrue(bool(manifest.get("cmb_e2_dm_rs_fit_applied")))
        self.assertIn("inputs", manifest)
        self.assertIn("results", manifest)

        # Required results keys.
        res = manifest["results"]
        self.assertIn("dm_star_calibration_fit", res)
        self.assertIn("rs_star_calibration_fit", res)
        self.assertIn("chi2_base", res)
        self.assertIn("chi2_min", res)

        # Portability: no machine-local paths.
        s = json.dumps(manifest, sort_keys=True)
        self.assertNotIn("/Users/", s)
        self.assertNotIn("C:\\\\", s)

        # Inputs should be repo-relative.
        self.assertTrue(str(manifest["inputs"]["cmb_csv"]).startswith("v11.0.0/"))
        self.assertTrue(str(manifest["inputs"]["cmb_cov"]).startswith("v11.0.0/"))

        # Walk all strings to catch other accidental absolute paths.
        for v in _walk_strings(manifest):
            self.assertNotIn("/Users/", v)
            self.assertNotIn("C:\\\\", v)


if __name__ == "__main__":
    unittest.main()
