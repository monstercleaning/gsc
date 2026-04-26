import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.e2_deformations import LogHTwoWindowDeformation, log1p_gaussian_window  # noqa: E402


class TestPhase2M49TwoWindowLogHDeformation(unittest.TestCase):
    def test_identity_when_amplitudes_zero(self) -> None:
        deformation = LogHTwoWindowDeformation(
            tw1_zc=3.0,
            tw1_w=0.25,
            tw1_a=0.0,
            tw2_zc=800.0,
            tw2_w=0.40,
            tw2_a=0.0,
        )
        for z in (0.0, 1.0, 3.0, 10.0, 1100.0):
            self.assertAlmostEqual(deformation.factor(z), 1.0, places=14)

    def test_factor_is_positive_for_representative_parameters(self) -> None:
        deformation = LogHTwoWindowDeformation(
            tw1_zc=2.8,
            tw1_w=0.20,
            tw1_a=0.35,
            tw2_zc=1000.0,
            tw2_w=0.55,
            tw2_a=-0.40,
        )
        for z in (0.0, 1.0, 3.0, 10.0, 50.0, 1100.0):
            factor = deformation.factor(z)
            self.assertTrue(math.isfinite(factor))
            self.assertGreater(factor, 0.0)

    def test_window_locality_for_well_separated_centers(self) -> None:
        # For strongly separated centers in ln(1+z), the far window should be negligible.
        w2_at_tw1 = log1p_gaussian_window(z=3.0, zc=1200.0, w=0.10)
        self.assertLess(w2_at_tw1, 1e-6)

    def test_deterministic_factor_values(self) -> None:
        deformation = LogHTwoWindowDeformation(
            tw1_zc=2.5,
            tw1_w=0.30,
            tw1_a=-0.25,
            tw2_zc=600.0,
            tw2_w=0.35,
            tw2_a=0.45,
        )
        values_a = [deformation.factor(z) for z in (0.0, 2.0, 3.0, 50.0, 1100.0)]
        values_b = [deformation.factor(z) for z in (0.0, 2.0, 3.0, 50.0, 1100.0)]
        self.assertEqual(values_a, values_b)


if __name__ == "__main__":
    unittest.main()
