import math
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.histories.full_range import GSCTransitionFullHistory  # noqa: E402
from gsc.measurement_model import H0_to_SI  # noqa: E402


class TestFullHistoryContinuity(unittest.TestCase):
    def test_H_is_finite_positive_and_continuous_at_transition(self):
        H0 = H0_to_SI(67.4)
        hist = GSCTransitionFullHistory(
            H0=H0,
            Omega_m=0.315,
            p_late=0.6,
            z_transition=1.8,
            z_relax=5.0,
            z_bbn_clamp=1.0e7,
        )

        # Basic sanity across a few representative redshifts.
        for z in (-0.5, 0.0, 0.2, 1.0, 1.8, 2.0, 10.0, 100.0):
            Hz = float(hist.H(float(z)))
            self.assertTrue(math.isfinite(Hz) and Hz > 0.0)

        # Continuity around z_transition (function value, not derivative).
        zt = 1.8
        eps = 1e-6
        Hm = float(hist.H(zt - eps))
        H0v = float(hist.H(zt))
        Hp = float(hist.H(zt + eps))
        self.assertTrue(abs(H0v - Hm) / H0v < 1e-5)
        self.assertTrue(abs(Hp - H0v) / H0v < 1e-5)


if __name__ == "__main__":
    unittest.main()

