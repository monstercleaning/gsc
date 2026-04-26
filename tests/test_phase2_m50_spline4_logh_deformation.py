import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.e2_deformations import Spline4LogHDeformation  # noqa: E402


class TestPhase2M50Spline4LogHDeformation(unittest.TestCase):
    def test_anchor_is_zero_at_z0(self) -> None:
        deformation = Spline4LogHDeformation(
            spl4_dlogh_z3=0.3,
            spl4_dlogh_z30=-0.4,
            spl4_dlogh_z300=0.1,
            spl4_dlogh_z1100=-0.2,
        )
        self.assertAlmostEqual(deformation.dlogh(0.0), 0.0, places=15)

    def test_knot_exactness(self) -> None:
        deformation = Spline4LogHDeformation(
            spl4_dlogh_z3=0.25,
            spl4_dlogh_z30=-0.10,
            spl4_dlogh_z300=0.40,
            spl4_dlogh_z1100=-0.35,
        )
        self.assertAlmostEqual(deformation.dlogh(3.0), 0.25, places=14)
        self.assertAlmostEqual(deformation.dlogh(30.0), -0.10, places=14)
        self.assertAlmostEqual(deformation.dlogh(300.0), 0.40, places=14)
        self.assertAlmostEqual(deformation.dlogh(1100.0), -0.35, places=14)

    def test_midpoint_interpolation_in_log1p_space(self) -> None:
        p3 = 0.6
        p30 = -0.2
        deformation = Spline4LogHDeformation(
            spl4_dlogh_z3=p3,
            spl4_dlogh_z30=p30,
            spl4_dlogh_z300=0.0,
            spl4_dlogh_z1100=0.0,
        )
        x3 = math.log1p(3.0)
        x30 = math.log1p(30.0)
        xm = 0.5 * (x3 + x30)
        zm = math.exp(xm) - 1.0
        expected = 0.5 * (p3 + p30)
        self.assertAlmostEqual(deformation.dlogh(zm), expected, places=12)

    def test_continuity_around_knots(self) -> None:
        deformation = Spline4LogHDeformation(
            spl4_dlogh_z3=0.2,
            spl4_dlogh_z30=0.5,
            spl4_dlogh_z300=-0.1,
            spl4_dlogh_z1100=0.3,
        )
        eps = 1e-10
        left = deformation.dlogh(30.0 * (1.0 - eps))
        right = deformation.dlogh(30.0 * (1.0 + eps))
        self.assertLess(abs(left - right), 1e-8)

    def test_hold_last_above_z1100(self) -> None:
        deformation = Spline4LogHDeformation(
            spl4_dlogh_z3=0.0,
            spl4_dlogh_z30=0.0,
            spl4_dlogh_z300=0.0,
            spl4_dlogh_z1100=0.17,
        )
        self.assertAlmostEqual(deformation.dlogh(2000.0), 0.17, places=14)
        self.assertAlmostEqual(deformation.dlogh(10000.0), 0.17, places=14)


if __name__ == "__main__":
    unittest.main()
