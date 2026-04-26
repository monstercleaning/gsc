import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.rd import compute_rd_Mpc  # noqa: E402
import gsc.early_time.cmb_distance_priors as cmb  # noqa: E402


class TestRsStarCalibrationNoLeakage(unittest.TestCase):
    def test_compute_rd_mpc_is_independent_of_rs_star_calibration_constant(self):
        # Guardrail: E0 r_d (BAO) must not depend on the CHW2018 r_s(z*) stopgap
        # calibration constant.
        rd0 = compute_rd_Mpc(
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            method="eisenstein_hu_1998",
        )

        old = float(cmb._RS_STAR_CALIB_CHW2018)
        try:
            cmb._RS_STAR_CALIB_CHW2018 = 9.0
            rd1 = compute_rd_Mpc(
                omega_b_h2=0.02237,
                omega_c_h2=0.1200,
                N_eff=3.046,
                Tcmb_K=2.7255,
                method="eisenstein_hu_1998",
            )
        finally:
            cmb._RS_STAR_CALIB_CHW2018 = old

        self.assertAlmostEqual(rd0, rd1, places=12)

    def test_sound_horizon_integral_does_not_apply_rs_star_calibration_constant(self):
        # Guardrail: the generic sound-horizon integral must remain uncalibrated;
        # calibration is only applied explicitly to r_s(z*) in the CHW2018 strict
        # distance-priors prediction path.
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        H0_km_s_Mpc = 67.4
        h = H0_km_s_Mpc / 100.0
        omega_b_h2 = 0.02237
        omega_c_h2 = 0.1200
        N_eff = 3.046
        Tcmb_K = 2.7255

        H0_si = cmb.H0_to_SI(H0_km_s_Mpc)
        omega_g_h2 = cmb.omega_gamma_h2_from_Tcmb(Tcmb_K)
        omega_r_h2_val = cmb.omega_r_h2(Tcmb_K=Tcmb_K, N_eff=N_eff)
        Omega_r = float(omega_r_h2_val) / (h * h)
        Omega_m = 0.315
        Omega_lambda = 1.0 - Omega_m - Omega_r

        z_star = cmb.z_star_hu_sugiyama(omega_b_h2=omega_b_h2, omega_m_h2=omega_b_h2 + omega_c_h2)

        rs0 = cmb._sound_horizon_from_z_m(
            z=z_star,
            H0_si=H0_si,
            omega_b_h2=omega_b_h2,
            omega_gamma_h2=omega_g_h2,
            omega_m=Omega_m,
            omega_r=Omega_r,
            omega_lambda=Omega_lambda,
            n=2048,
        )

        old = float(cmb._RS_STAR_CALIB_CHW2018)
        try:
            cmb._RS_STAR_CALIB_CHW2018 = 1.2345
            rs1 = cmb._sound_horizon_from_z_m(
                z=z_star,
                H0_si=H0_si,
                omega_b_h2=omega_b_h2,
                omega_gamma_h2=omega_g_h2,
                omega_m=Omega_m,
                omega_r=Omega_r,
                omega_lambda=Omega_lambda,
                n=2048,
            )
        finally:
            cmb._RS_STAR_CALIB_CHW2018 = old

        self.assertAlmostEqual(rs0, rs1, places=12)


if __name__ == "__main__":
    unittest.main()

