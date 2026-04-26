import math
import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.numerics_adaptive_quad import adaptive_simpson  # noqa: E402


class TestPhase2M20AdaptiveQuad(unittest.TestCase):
    def test_known_integrals(self):
        self.assertAlmostEqual(
            adaptive_simpson(math.sin, 0.0, math.pi, eps_abs=1e-12, eps_rel=1e-12),
            2.0,
            places=10,
        )
        self.assertAlmostEqual(
            adaptive_simpson(lambda x: 1.0 / (1.0 + x * x), 0.0, 1.0, eps_abs=1e-12, eps_rel=1e-12),
            math.pi / 4.0,
            places=10,
        )
        self.assertAlmostEqual(
            adaptive_simpson(math.exp, 0.0, 1.0, eps_abs=1e-12, eps_rel=1e-12),
            math.e - 1.0,
            places=10,
        )

    def test_relaxed_tolerance_is_reasonable(self):
        val = adaptive_simpson(math.exp, 0.0, 1.0, eps_abs=1e-4, eps_rel=1e-4)
        self.assertLess(abs(val - (math.e - 1.0)), 5e-4)

    def test_max_depth_error_is_controlled(self):
        with self.assertRaises(RuntimeError):
            adaptive_simpson(math.exp, 0.0, 1.0, eps_abs=1e-30, eps_rel=1e-30, max_depth=0)


if __name__ == "__main__":
    unittest.main()
