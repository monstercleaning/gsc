import math
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time.rd import omega_r_h2  # noqa: E402
from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.diagnostics.recombination import z_star_peebles_approx  # noqa: E402


class TestZStarRecombinationAudit(unittest.TestCase):
    def test_peebles_zstar_is_finite_and_in_sane_range(self):
        # Planck-like inputs.
        H0_km_s_Mpc = 67.4
        H0_si = H0_to_SI(H0_km_s_Mpc)
        Omega_m = 0.315
        Neff = 3.046
        Tcmb_K = 2.7255
        omega_b_h2 = 0.02237
        Yp = 0.245

        h = float(H0_km_s_Mpc) / 100.0
        Omega_r = float(omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(Neff))) / (h * h)
        Omega_L = 1.0 - float(Omega_m) - float(Omega_r)
        self.assertGreater(Omega_L, 0.0)

        z_star, info = z_star_peebles_approx(
            H0_si=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_r=float(Omega_r),
            Omega_Lambda=float(Omega_L),
            omega_b_h2=float(omega_b_h2),
            Tcmb_K=float(Tcmb_K),
            Yp=float(Yp),
            z_max=2500.0,
            z_min_ode=200.0,
            n_grid=2048,
            method="fixed_rk4_u",
        )

        self.assertTrue(math.isfinite(z_star) and z_star > 0.0)
        # Loose "sanity" range: we are not aiming for HyRec-level accuracy.
        self.assertGreater(z_star, 800.0)
        self.assertLess(z_star, 1600.0)

        x_e = float(info.get("x_e_at_z_star", float("nan")))
        self.assertTrue(math.isfinite(x_e))
        self.assertGreaterEqual(x_e, 1e-8)
        self.assertLessEqual(x_e, 1.0)


if __name__ == "__main__":
    unittest.main()
