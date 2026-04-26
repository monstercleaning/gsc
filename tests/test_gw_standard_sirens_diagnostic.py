import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.diagnostics.gw_sirens import gw_distance_ratio  # noqa: E402


class TestGWStandardSirensDiagnostic(unittest.TestCase):
    def test_delta_zero_gives_unity_ratio(self):
        def delta(z: float) -> float:
            return 0.0

        for z in (0.0, 0.1, 0.5, 1.0, 2.0, 5.0):
            r = gw_distance_ratio(float(z), delta_of_z=delta, n=2000)
            self.assertAlmostEqual(float(r), 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
