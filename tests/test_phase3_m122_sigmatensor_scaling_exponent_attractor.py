import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


class TestPhase3M122SigmaTensorScalingExponentAttractor(unittest.TestCase):
    def test_scalar_dominated_attractor_tracks_action_exponent(self) -> None:
        lam = 1.2
        w0 = -1.0 + (lam * lam) / 3.0
        params = SigmaTensorV1Params(
            H0_si=float(H0_to_SI(67.4)),
            Omega_m0=0.0,
            w_phi0=w0,
            lambda_=lam,
            Omega_r0_override=0.0,
            sign_u0=+1,
        )
        bg = solve_sigmatensor_v1_background(params, z_max=3.0, n_steps=2048)
        hist = SigmaTensorV1History(bg)

        p_action = float(bg.meta["p_action"])
        self.assertAlmostEqual(p_action, 0.5 * lam * lam, places=12)

        for z in (0.5, 1.0, 2.0, 3.0):
            expected = (1.0 + z) ** p_action
            got = hist.E(z)
            rel = abs(got - expected) / expected
            self.assertLess(rel, 2.0e-3, msg=f"z={z} rel={rel:.3e}")

            w_phi = hist.w_phi(z)
            self.assertTrue(math.isfinite(w_phi))
            self.assertLess(abs(w_phi - w0), 2.0e-3, msg=f"z={z} w={w_phi:.6f}")


if __name__ == "__main__":
    unittest.main()
