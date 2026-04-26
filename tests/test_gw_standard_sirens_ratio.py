import math
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.diagnostics.gw_sirens import Xi_of_z, gw_distance_ratio  # noqa: E402


class TestGWStandardSirensRatio(unittest.TestCase):
    def test_xi0_equals_one_is_gr_exact(self):
        for z in (0.0, 0.1, 0.5, 1.0, 2.0, 10.0):
            Xi = Xi_of_z(float(z), Xi0=1.0, n=2.0)
            self.assertEqual(float(Xi), 1.0)

    def test_xi_is_monotone_and_approaches_xi0(self):
        # For n>0 and Xi0 != 1, Xi(z) should approach Xi0 monotonically.
        n = 2.0
        zs = [0.0, 0.2, 0.7, 1.0, 2.5, 5.0, 50.0]
        for Xi0 in (0.8, 1.2):
            Xis = [Xi_of_z(float(z), Xi0=float(Xi0), n=float(n)) for z in zs]
            self.assertEqual(float(Xis[0]), 1.0)
            for a, b in zip(Xis, Xis[1:]):
                if float(Xi0) < 1.0:
                    self.assertTrue(float(b) < float(a))
                else:
                    self.assertTrue(float(b) > float(a))
            self.assertTrue(abs(float(Xis[-1]) - float(Xi0)) < 1e-3)

    def test_const_delta_matches_analytic_power_law(self):
        delta0 = 0.123

        def delta(z: float) -> float:
            return float(delta0)

        for z in (0.0, 0.2, 0.7, 1.0, 2.5, 5.0):
            r_num = gw_distance_ratio(float(z), delta_of_z=delta, n=50_000)
            r_ana = (1.0 + float(z)) ** float(delta0)
            self.assertTrue(math.isfinite(float(r_num)))
            # Numerical trapezoid integration error should be small but not machine-precision.
            self.assertAlmostEqual(float(r_num), float(r_ana), places=9)

    def test_const_alphaM_matches_analytic_power_law(self):
        alpha0 = -0.42

        def alphaM(z: float) -> float:
            return float(alpha0)

        for z in (0.0, 0.2, 0.7, 1.0, 2.5, 5.0):
            r_num = gw_distance_ratio(float(z), alphaM_of_z=alphaM, n=50_000)
            r_ana = (1.0 + float(z)) ** (0.5 * float(alpha0))
            self.assertTrue(math.isfinite(float(r_num)))
            self.assertAlmostEqual(float(r_num), float(r_ana), places=9)


if __name__ == "__main__":
    unittest.main()
