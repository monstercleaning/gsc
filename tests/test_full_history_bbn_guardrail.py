import math
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.histories.full_range import FlatLCDMRadHistory, GSCTransitionFullHistory  # noqa: E402
from gsc.measurement_model import H0_to_SI  # noqa: E402


class TestFullHistoryBBNGuardrail(unittest.TestCase):
    def test_bbn_guardrail_matches_lcdm_rad_at_high_z(self):
        H0 = H0_to_SI(67.4)
        Omega_m = 0.315
        Neff = 3.046
        Tcmb_K = 2.7255

        lcdm = FlatLCDMRadHistory(H0=H0, Omega_m=Omega_m, N_eff=Neff, Tcmb_K=Tcmb_K)
        full = GSCTransitionFullHistory(
            H0=H0,
            Omega_m=Omega_m,
            p_late=0.6,
            z_transition=1.8,
            z_relax=5.0,
            N_eff=Neff,
            Tcmb_K=Tcmb_K,
            z_bbn_clamp=1.0e7,
        )

        for z in (1.0e8, 1.0e9, 1.0e10):
            H_full = float(full.H(float(z)))
            H_ref = float(lcdm.H(float(z)))
            self.assertTrue(math.isfinite(H_full) and H_full > 0.0)
            self.assertTrue(math.isfinite(H_ref) and H_ref > 0.0)
            ratio = H_full / H_ref
            self.assertTrue(abs(float(ratio) - 1.0) < 0.01)


if __name__ == "__main__":
    unittest.main()
