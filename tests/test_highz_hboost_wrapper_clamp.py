import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
sys.path.insert(0, str(ROOT))

from gsc.histories.full_range import FlatLCDMRadHistory, HBoostWrapper  # noqa: E402
from gsc.measurement_model import H0_to_SI  # noqa: E402


class TestHighZHBoostWrapperClamp(unittest.TestCase):
    def test_A_is_one_below_start_and_above_bbn_clamp(self):
        base = FlatLCDMRadHistory(H0=H0_to_SI(67.4), Omega_m=0.315)
        w = HBoostWrapper(
            base_history=base,
            z_boost_start=5.0,
            z_boost_end=None,
            z_bbn_clamp=1.0e7,
            transition_width=0.0,
            boost_mode="const",
            A_const=1.23,
        )

        self.assertEqual(w.A(0.0), 1.0)
        self.assertEqual(w.A(4.999), 1.0)
        # The contract is inclusive at the boundary: protect z <= z_boost_start.
        self.assertEqual(w.A(5.0), 1.0)
        self.assertAlmostEqual(w.A(5.0001), 1.23, places=12)

        # Above the BBN clamp, the wrapper must disable any boost.
        self.assertEqual(w.A(1.0e8), 1.0)

    def test_A_is_one_above_z_boost_end_if_set(self):
        base = FlatLCDMRadHistory(H0=H0_to_SI(67.4), Omega_m=0.315)
        w = HBoostWrapper(
            base_history=base,
            z_boost_start=5.0,
            z_boost_end=50.0,
            z_bbn_clamp=1.0e7,
            transition_width=0.0,
            boost_mode="const",
            A_const=1.5,
        )
        self.assertEqual(w.A(5.0), 1.0)
        self.assertAlmostEqual(w.A(10.0), 1.5, places=12)
        self.assertEqual(w.A(50.0), 1.0)
        self.assertEqual(w.A(100.0), 1.0)


if __name__ == "__main__":
    unittest.main()

