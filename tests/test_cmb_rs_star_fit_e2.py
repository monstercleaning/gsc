import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402

import cmb_rs_star_calibration_fit_e2 as fit  # noqa: E402


class TestCMBRsStarFitE2(unittest.TestCase):
    def test_lcdm_planck_like_rs_star_fit_is_near_unity(self):
        # Offline-safe diagnostic lock: at the Planck-like benchmark already used by the
        # strict CHW2018 regression, the additional rs* multiplier should be ~1.0 and
        # chi2_min should remain small.
        chw_csv = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        chw_cov = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
        ds = CMBPriorsDataset.from_csv(chw_csv, cov_path=chw_cov, name="cmb_chw2018")

        pred = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            rs_star_calibration=float(_RS_STAR_CALIB_CHW2018),
        )

        r = fit.fit_rs_star_calibration_multiplier(
            ds=ds,
            pred_base=pred,
            rs_star_calibration_base=float(_RS_STAR_CALIB_CHW2018),
            k_min=0.8,
            k_max=1.3,
        )

        self.assertLess(abs(float(r.rs_star_calibration_fit) - 1.0), 1e-3)
        self.assertLess(float(r.chi2_min), 3.0)
        self.assertLessEqual(float(r.chi2_min), float(r.chi2_base) + 1e-12)


if __name__ == "__main__":
    unittest.main()
