import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.structure.transfer_eh98 import transfer_eh98_nowiggle  # noqa: E402


class TestPhase2M86TransferEH98Nowiggle(unittest.TestCase):
    def test_smoke_limits(self) -> None:
        params = {
            "omega_b_h2": 0.02237,
            "omega_c_h2": 0.1200,
            "h": 0.674,
            "Tcmb_K": 2.7255,
            "N_eff": 3.046,
        }
        self.assertEqual(transfer_eh98_nowiggle(0.0, **params), 1.0)
        self.assertGreater(transfer_eh98_nowiggle(1.0e-4, **params), 0.98)
        self.assertLess(transfer_eh98_nowiggle(10.0, **params), 0.2)

    def test_validation(self) -> None:
        with self.assertRaises(ValueError):
            transfer_eh98_nowiggle(
                -1.0e-3,
                omega_b_h2=0.022,
                omega_c_h2=0.12,
                h=0.67,
            )
        with self.assertRaises(ValueError):
            transfer_eh98_nowiggle(
                1.0e-2,
                omega_b_h2=0.0,
                omega_c_h2=0.0,
                h=0.67,
            )
        with self.assertRaises(ValueError):
            transfer_eh98_nowiggle(
                1.0e-2,
                omega_b_h2=0.022,
                omega_c_h2=0.12,
                h=0.0,
            )

    def test_deterministic_pinned_values(self) -> None:
        params = {
            "omega_b_h2": 0.02237,
            "omega_c_h2": 0.1200,
            "h": 0.674,
            "Tcmb_K": 2.7255,
            "N_eff": 3.046,
        }
        self.assertAlmostEqual(transfer_eh98_nowiggle(1.0e-4, **params), 0.9996327153320017, places=12)
        self.assertAlmostEqual(transfer_eh98_nowiggle(1.0e-2, **params), 0.5703398569058159, places=12)
        self.assertAlmostEqual(transfer_eh98_nowiggle(1.0, **params), 0.0023430368922888415, places=12)
        self.assertTrue(math.isfinite(transfer_eh98_nowiggle(1.0, **params)))


if __name__ == "__main__":
    unittest.main()

