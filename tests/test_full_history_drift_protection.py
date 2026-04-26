import math
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.histories.full_range import GSCTransitionFullHistory  # noqa: E402
from gsc.measurement_model import H0_to_SI, delta_v_cm_s  # noqa: E402


class TestFullHistoryDriftProtection(unittest.TestCase):
    def test_guarded_relax_does_not_affect_drift_window(self):
        # Guarded relaxation: start above the drift window.
        H0 = H0_to_SI(67.4)
        common = dict(
            H0=H0,
            Omega_m=0.315,
            p_late=0.6,
            z_transition=1.8,
            z_relax_start=5.0,
            N_eff=3.046,
            Tcmb_K=2.7255,
            z_bbn_clamp=1.0e7,
        )

        # Same history, but one has a very fast relax scale and the other has no relax.
        guarded_fast = GSCTransitionFullHistory(**common, z_relax=0.5)
        guarded_none = GSCTransitionFullHistory(**common, z_relax=math.inf)

        # Below z_relax_start, H(z) (and thus drift) must be identical.
        for z in (2.0, 3.0, 4.0, 5.0):
            H_fast = float(guarded_fast.H(float(z)))
            H_none = float(guarded_none.H(float(z)))
            self.assertTrue(math.isfinite(H_fast) and H_fast > 0.0)
            self.assertTrue(math.isfinite(H_none) and H_none > 0.0)
            rel = abs(H_fast - H_none) / H_none
            self.assertLess(rel, 1e-12)

            dv_fast = float(delta_v_cm_s(z=float(z), years=10.0, H0=float(guarded_fast.H(0.0)), H_of_z=guarded_fast.H))
            dv_none = float(delta_v_cm_s(z=float(z), years=10.0, H0=float(guarded_none.H(0.0)), H_of_z=guarded_none.H))
            rel_dv = abs(dv_fast - dv_none) / max(1e-30, abs(dv_none))
            self.assertLess(rel_dv, 1e-12)


if __name__ == "__main__":
    unittest.main()

