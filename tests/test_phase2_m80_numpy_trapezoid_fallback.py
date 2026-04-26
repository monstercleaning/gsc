import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.early_time import cmb_distance_priors as _cdp  # noqa: E402


class TestPhase2M80NumpyTrapezoidFallback(unittest.TestCase):
    def test_np_trapezoid_falls_back_to_trapz(self) -> None:
        try:
            import numpy as np  # type: ignore
        except ImportError:
            self.skipTest("numpy not installed")

        x = np.linspace(0.0, 1.0, 11, dtype=float)
        y = x**2
        expected = float(0.5 * np.sum((y[1:] + y[:-1]) * (x[1:] - x[:-1])))

        had_trapezoid = hasattr(np, "trapezoid")
        original = getattr(np, "trapezoid", None)
        try:
            if had_trapezoid:
                setattr(np, "trapezoid", None)
            got = float(_cdp._np_trapezoid(np, y, x))
        finally:
            if had_trapezoid:
                setattr(np, "trapezoid", original)

        self.assertTrue(math.isfinite(got))
        self.assertAlmostEqual(got, expected, places=12)


if __name__ == "__main__":
    unittest.main()
