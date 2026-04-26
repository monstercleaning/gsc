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


class TestPhase3M124SigmaTensorInterpEndpointTolerance(unittest.TestCase):
    def test_e_endpoint_clamps_with_tolerance(self) -> None:
        z_max = 1100.0
        bg = solve_sigmatensor_v1_background(
            SigmaTensorV1Params(
                H0_si=float(H0_to_SI(67.4)),
                Omega_m0=0.315,
                w_phi0=-0.95,
                lambda_=0.4,
            ),
            z_max=z_max,
            n_steps=64,
        )
        hist = SigmaTensorV1History(bg)
        z_last = float(bg.z_grid[-1])
        self.assertTrue(math.isfinite(z_last))
        self.assertGreater(z_last, 1000.0)

        e_req = hist.E(z_max)
        e_last = hist.E(z_last)
        self.assertTrue(math.isfinite(e_req))
        self.assertTrue(math.isfinite(e_last))
        self.assertAlmostEqual(e_req, e_last, places=12)


if __name__ == "__main__":
    unittest.main()

