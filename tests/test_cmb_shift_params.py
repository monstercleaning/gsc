import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402
from gsc.early_time.cmb_shift_params import compute_lcdm_shift_params  # noqa: E402


class TestCMBShiftParams(unittest.TestCase):
    def test_planck_like_sanity_ranges(self):
        p = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        for key in ("theta_star", "lA", "R", "z_star", "r_s_star_Mpc", "D_M_star_Mpc"):
            self.assertIn(key, p)

        self.assertTrue(900.0 < p["z_star"] < 1300.0)
        self.assertTrue(0.009 < p["theta_star"] < 0.0125)
        self.assertTrue(200.0 < p["lA"] < 400.0)
        self.assertTrue(1.0 < p["R"] < 2.5)
        self.assertTrue(120.0 < p["r_s_star_Mpc"] < 170.0)
        self.assertTrue(10000.0 < p["D_M_star_Mpc"] < 20000.0)

    def test_theta_star_responds_to_omega_m(self):
        p_lo = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.28,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        p_hi = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.35,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        self.assertNotAlmostEqual(p_lo["theta_star"], p_hi["theta_star"], places=8)

    def test_new_api_matches_legacy_distance_prior_function(self):
        legacy = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        new_api = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        for key in ("theta_star", "lA", "R", "z_star", "r_s_star_Mpc", "D_M_star_Mpc", "rd_Mpc"):
            self.assertAlmostEqual(float(new_api[key]), float(legacy[key]), places=12)


if __name__ == "__main__":
    unittest.main()
