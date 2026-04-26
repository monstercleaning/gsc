import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402
from gsc.early_time.rd import compute_rd_Mpc  # noqa: E402


class TestDmStarCalibrationNoLeakage(unittest.TestCase):
    def test_dm_star_calibration_does_not_affect_rd_or_rs(self):
        # Guardrail: dm_star_calibration must not affect E0 r_d (BAO) or r_s(z*).
        # It is a diagnostic-only multiplicative knob applied only to D_M(z*).
        omega_b_h2 = 0.02237
        omega_c_h2 = 0.1200

        rd0 = compute_rd_Mpc(
            omega_b_h2=omega_b_h2,
            omega_c_h2=omega_c_h2,
            N_eff=3.046,
            Tcmb_K=2.7255,
            method="eisenstein_hu_1998",
        )

        p0 = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=omega_b_h2,
            omega_c_h2=omega_c_h2,
            N_eff=3.046,
            Tcmb_K=2.7255,
            rs_star_calibration=1.0,
            dm_star_calibration=1.0,
        )
        p1 = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=omega_b_h2,
            omega_c_h2=omega_c_h2,
            N_eff=3.046,
            Tcmb_K=2.7255,
            rs_star_calibration=1.0,
            dm_star_calibration=1.2345,
        )

        # rd is separate (E0) and must not change.
        self.assertAlmostEqual(rd0, float(p0["rd_Mpc"]), places=12)
        self.assertAlmostEqual(float(p0["rd_Mpc"]), float(p1["rd_Mpc"]), places=12)

        # r_s(z*) must not change under dm scaling.
        self.assertAlmostEqual(float(p0["r_s_star_Mpc"]), float(p1["r_s_star_Mpc"]), places=12)

        # D_M(z*) should scale linearly with dm.
        self.assertAlmostEqual(float(p1["D_M_star_Mpc"]) / float(p0["D_M_star_Mpc"]), 1.2345, places=12)

        # Derived priors must scale consistently (R ∝ D_M; lA ∝ D_M when rs fixed).
        self.assertAlmostEqual(float(p1["R"]) / float(p0["R"]), 1.2345, places=12)
        self.assertAlmostEqual(float(p1["lA"]) / float(p0["lA"]), 1.2345, places=12)


if __name__ == "__main__":
    unittest.main()
