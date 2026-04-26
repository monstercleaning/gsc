from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.structure.growth_factor import solve_growth_D_f  # noqa: E402


class TestPhase2M81GrowthFactorEdSRegression(unittest.TestCase):
    def test_eds_recovers_D_and_f(self) -> None:
        H0_si = H0_to_SI(70.0)

        def H_of_z(z: float) -> float:
            return H0_si * (1.0 + float(z)) ** 1.5

        z_eval = [0.0, 0.5, 1.0, 2.0, 5.0]
        out = solve_growth_D_f(
            z_eval,
            H_of_z=H_of_z,
            Omega_m0=1.0,
            z_init=120.0,
            n_steps=6000,
        )

        self.assertEqual(out.get("method"), "rk4_ln_a_v1")
        self.assertEqual(list(out.get("z", [])), z_eval)

        D_vals = list(out.get("D", []))
        f_vals = list(out.get("f", []))
        self.assertEqual(len(D_vals), len(z_eval))
        self.assertEqual(len(f_vals), len(z_eval))

        for z, d_val, f_val in zip(z_eval, D_vals, f_vals):
            expected_D = 1.0 / (1.0 + z)
            self.assertAlmostEqual(float(d_val), expected_D, delta=1.0e-3)
            self.assertAlmostEqual(float(f_val), 1.0, delta=1.0e-3)


if __name__ == "__main__":
    unittest.main()
