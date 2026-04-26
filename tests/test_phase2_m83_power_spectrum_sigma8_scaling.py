import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.structure.power_spectrum_linear import (  # noqa: E402
    sigma8_0_from_As,
    sigma8_z,
    tophat_window,
)


class TestPhase2M83PowerSpectrumSigma8Scaling(unittest.TestCase):
    def test_sigma8_scales_as_sqrt_As_and_decreases_with_z(self) -> None:
        base_params = {
            "ns": 0.965,
            "omega_m0": 0.3,
            "h": 0.7,
            "omega_b0": 0.049,
            "kmin": 1.0e-4,
            "kmax": 1.0e1,
            "nk": 768,
            "z_start": 80.0,
            "n_steps": 3200,
        }
        As = 2.1e-9

        for transfer_model in ("bbks", "eh98_nowiggle"):
            params = dict(base_params)
            params["transfer_model"] = transfer_model

            s8_a = sigma8_0_from_As(As=As, **params)
            s8_b = sigma8_0_from_As(As=4.0 * As, **params)

            self.assertTrue(math.isfinite(s8_a) and s8_a > 0.0)
            self.assertTrue(math.isfinite(s8_b) and s8_b > 0.0)
            self.assertAlmostEqual(s8_b / s8_a, 2.0, delta=2.0e-2)

            s8_z0 = s8_a
            s8_z1 = sigma8_z(1.0, As=As, **params)
            self.assertTrue(math.isfinite(s8_z1) and s8_z1 > 0.0)
            self.assertLess(s8_z1, s8_z0)

    def test_tophat_window_small_x_stability(self) -> None:
        w = tophat_window(1.0e-8)
        self.assertAlmostEqual(w, 1.0, delta=1.0e-10)


if __name__ == "__main__":
    unittest.main()
