import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI, z_dot_sandage_loeb  # noqa: E402


class TestPhase2M13DriftIsHistoryOnly(unittest.TestCase):
    def test_same_history_callable_gives_identical_drift(self):
        h0 = H0_to_SI(67.4)

        def history_a(z: float) -> float:
            return h0 * (1.0 + z) ** 1.1

        def history_b(z: float) -> float:
            # Different callable, same H(z) values.
            base = 1.0 + z
            return h0 * base * (base ** 0.1)

        z = 3.2
        drift_a = z_dot_sandage_loeb(z=z, H0=h0, H_of_z=history_a)
        drift_b = z_dot_sandage_loeb(z=z, H0=h0, H_of_z=history_b)
        self.assertAlmostEqual(drift_a, drift_b, places=20)

    def test_different_history_changes_drift(self):
        h0 = H0_to_SI(67.4)

        def history_1(z: float) -> float:
            return h0 * (1.0 + z) ** 0.8

        def history_2(z: float) -> float:
            return h0 * (1.0 + z) ** 1.2

        z = 3.2
        drift_1 = z_dot_sandage_loeb(z=z, H0=h0, H_of_z=history_1)
        drift_2 = z_dot_sandage_loeb(z=z, H0=h0, H_of_z=history_2)
        self.assertNotEqual(drift_1, drift_2)


if __name__ == "__main__":
    unittest.main()
