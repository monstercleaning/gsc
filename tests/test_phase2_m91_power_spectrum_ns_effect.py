import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.structure.power_spectrum_linear import sigma8_0_from_As  # noqa: E402


class TestPhase2M91PowerSpectrumNsEffect(unittest.TestCase):
    def test_sigma8_depends_on_ns_and_is_deterministic(self) -> None:
        params = {
            "As": 2.1e-9,
            "omega_m0": 0.3,
            "h": 0.7,
            "omega_b0": 0.049,
            "kmin": 1.0e-4,
            "kmax": 1.0e1,
            "nk": 768,
            "z_start": 80.0,
            "n_steps": 3200,
        }

        s8_ns1 = sigma8_0_from_As(ns=1.0, **params)
        s8_ns096 = sigma8_0_from_As(ns=0.96, **params)
        s8_ns096_repeat = sigma8_0_from_As(ns=0.96, **params)

        self.assertTrue(math.isfinite(s8_ns1) and s8_ns1 > 0.0)
        self.assertTrue(math.isfinite(s8_ns096) and s8_ns096 > 0.0)
        self.assertLess(s8_ns096, s8_ns1)
        self.assertGreater(abs(s8_ns1 - s8_ns096), 1.0e-4)
        self.assertAlmostEqual(s8_ns096, s8_ns096_repeat, places=14)

    def test_ns1_regression_keeps_previous_baseline_behavior(self) -> None:
        params = {
            "As": 2.1e-9,
            "ns": 1.0,
            "omega_m0": 0.3,
            "h": 0.7,
            "omega_b0": 0.049,
            "kmin": 1.0e-4,
            "kmax": 1.0e1,
            "nk": 768,
            "z_start": 80.0,
            "n_steps": 3200,
        }
        s8_default_pivot = sigma8_0_from_As(**params)
        s8_explicit_alt_pivot = sigma8_0_from_As(k_pivot_mpc=1.0, **params)
        self.assertAlmostEqual(s8_default_pivot, s8_explicit_alt_pivot, places=14)


if __name__ == "__main__":
    unittest.main()
