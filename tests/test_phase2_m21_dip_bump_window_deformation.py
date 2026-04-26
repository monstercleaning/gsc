import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.e2_deformations import DipBumpWindowDeformation  # noqa: E402


class TestPhase2M21DipBumpWindowDeformation(unittest.TestCase):
    def test_factor_is_finite_on_representative_grid(self):
        deformation = DipBumpWindowDeformation(A_dip=0.5, A_bump=1.0)
        for z in (0.0, 1.0, 3.0, 6.0, 50.0, 1100.0):
            f = deformation.factor(z)
            self.assertTrue(math.isfinite(f))
            self.assertGreater(f, 0.0)

    def test_dip_reduces_history_in_quasar_window(self):
        deformation = DipBumpWindowDeformation(A_dip=0.5, A_bump=0.0)
        h_base = lambda z: (1.0 + float(z)) ** 2  # noqa: E731
        h_def = deformation.apply(h_base)
        self.assertLess(h_def(3.0), h_base(3.0))

    def test_dip_can_flip_drift_sign_in_toy_history(self):
        h0 = 1.0
        deformation = DipBumpWindowDeformation(A_dip=0.9, A_bump=0.0)
        h_base = lambda z: h0 * (1.0 + float(z)) ** 2  # noqa: E731
        h_def = deformation.apply(h_base)
        z = 3.0
        z_dot = h0 * (1.0 + z) - h_def(z)
        self.assertGreater(z_dot, 0.0)


if __name__ == "__main__":
    unittest.main()
