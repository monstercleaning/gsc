import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402


class TestCMBDistancePriors(unittest.TestCase):
    def test_planck_like_sanity_ranges(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        p = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        self.assertTrue(900.0 < p["z_star"] < 1300.0)
        self.assertTrue(0.009 < p["theta_star"] < 0.0125)
        self.assertTrue(200.0 < p["lA"] < 400.0)
        self.assertTrue(1.0 < p["R"] < 2.5)
        self.assertTrue(120.0 < p["r_s_star_Mpc"] < 170.0)
        self.assertTrue(10000.0 < p["D_M_star_Mpc"] < 20000.0)
        self.assertTrue(130.0 < p["rd_Mpc"] < 170.0)

    def test_theta_star_changes_with_omega_m(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        p_lo = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.28,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        p_hi = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.35,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        self.assertNotAlmostEqual(p_lo["theta_star"], p_hi["theta_star"], places=8)


if __name__ == "__main__":
    unittest.main()
