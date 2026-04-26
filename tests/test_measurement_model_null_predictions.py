import unittest

from pathlib import Path
import sys

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    demo_ratio_clock_comparison,
    demo_ratio_nu_atom_over_nu_orb,
    kepler_orbital_frequency_scaling_power,
    universal_scaling_exponents,
)


class TestMeasurementModelNullPredictions(unittest.TestCase):
    def test_universal_scaling_exponents_contract(self):
        ex = universal_scaling_exponents()
        self.assertAlmostEqual(ex["length_bound"], 1.0, places=12)
        self.assertAlmostEqual(ex["mass"], -1.0, places=12)
        self.assertAlmostEqual(ex["G_IR"], 2.0, places=12)
        self.assertAlmostEqual(ex["nu_atomic"], -1.0, places=12)

        # Derived Kepler orbital frequency scaling should match ν_atom scaling in the universal limit.
        p_orb = kepler_orbital_frequency_scaling_power()
        self.assertAlmostEqual(p_orb, -1.0, places=12)
        self.assertAlmostEqual(p_orb, ex["nu_atomic"], places=12)

    def test_geometric_lock_ratio_nu_atom_over_orbital_is_invariant(self):
        # A toy "GPS-style" lock: ν_atom / ν_orb is dimensionless and should not drift.
        for sigma in [0.1, 0.3, 1.0, 3.0, 10.0]:
            r = demo_ratio_nu_atom_over_nu_orb(sigma=sigma, sigma_ref=1.0)
            self.assertAlmostEqual(r, 1.0, delta=1e-12)

    def test_clock_comparison_ratio_is_invariant(self):
        # Two local atomic clocks with different transition frequencies should have a constant ratio
        # under strict universal scaling.
        for sigma in [0.2, 0.7, 2.5, 9.0]:
            r = demo_ratio_clock_comparison(sigma=sigma, sigma_ref=1.0, nu_a0=1.0e15, nu_b0=9.19263177e9)
            self.assertAlmostEqual(r, 1.0, delta=1e-12)


if __name__ == "__main__":
    unittest.main()

