import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.histories.full_range import FlatLCDMRadHistory  # noqa: E402
from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


class TestPhase3M122SigmaTensorLCDMLimit(unittest.TestCase):
    def test_lcdm_limit_matches_flat_lcdm_rad(self) -> None:
        H0_km = 67.4
        H0_si = float(H0_to_SI(H0_km))
        params = SigmaTensorV1Params(
            H0_si=H0_si,
            Omega_m0=0.315,
            w_phi0=-1.0,
            lambda_=0.0,
            Tcmb_K=2.7255,
            N_eff=3.046,
        )
        bg = solve_sigmatensor_v1_background(params, z_max=5.0, n_steps=2048)
        hist = SigmaTensorV1History(bg)

        baseline = FlatLCDMRadHistory(
            H0=H0_si,
            Omega_m=0.315,
            Tcmb_K=2.7255,
            N_eff=3.046,
        )

        for z in (0.0, 0.5, 1.0, 2.0, 5.0):
            h_model = hist.H(z)
            h_ref = baseline.H(z)
            rel = abs(h_model - h_ref) / h_ref
            self.assertLess(rel, 1.0e-6, msg=f"z={z} rel={rel:.3e}")
            self.assertTrue(math.isfinite(h_model))


if __name__ == "__main__":
    unittest.main()
