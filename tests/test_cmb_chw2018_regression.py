import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402


class TestCHW2018DistancePriorsRegression(unittest.TestCase):
    def test_lcdm_planck_like_is_within_1sigma_diag(self):
        # This regression is intentionally strict: it ensures our lightweight
        # E1 LCDM predictor does not carry a large systematic offset against
        # the strict CHW2018 distance priors (R, lA, omega_b_h2) when evaluated
        # at a Planck-like benchmark.
        try:
            import numpy as np  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        chw_csv = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        chw_cov = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
        ds = CMBPriorsDataset.from_csv(chw_csv, cov_path=chw_cov)

        pred = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            rs_star_calibration=float(_RS_STAR_CALIB_CHW2018),
        )

        import numpy as np

        keys = ds.keys
        mean = np.asarray(ds.values, dtype=float)
        cov = np.asarray(ds.cov, dtype=float)
        pred_v = np.asarray([float(pred[k]) for k in keys], dtype=float)
        res = pred_v - mean
        sig = np.sqrt(np.diag(cov))
        pulls = res / sig
        for k, pull in zip(keys, pulls.tolist()):
            self.assertLess(abs(float(pull)), 1.0, msg=f"{k} pull={pull}")

        chi2 = float(res.T @ np.linalg.solve(cov, res))
        self.assertLess(chi2, 3.0, msg=f"chi2_cmb={chi2}")


if __name__ == "__main__":
    unittest.main()
