import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.pt import sigmatensor_v1_eft_alphas  # noqa: E402
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


class TestPhase3M124SigmaTensorEFTAlphasSanity(unittest.TestCase):
    def test_lambda_limit_alpha_k_zero_and_other_alphas_zero(self) -> None:
        bg = solve_sigmatensor_v1_background(
            SigmaTensorV1Params(
                H0_si=float(H0_to_SI(67.4)),
                Omega_m0=0.315,
                w_phi0=-1.0,
                lambda_=0.0,
            ),
            z_max=10.0,
            n_steps=512,
        )
        alphas = sigmatensor_v1_eft_alphas(bg)
        alpha_k = [float(x) for x in alphas["alpha_K"]]
        self.assertLess(max(abs(x) for x in alpha_k), 1.0e-12)
        for key in ("alpha_M", "alpha_B", "alpha_T"):
            self.assertTrue(all(abs(float(x)) == 0.0 for x in alphas[key]), msg=key)
        self.assertTrue(all(abs(float(x) - 1.0) == 0.0 for x in alphas["c_s2"]))

    def test_attractor_alpha_k_tracks_lambda2_and_cross_identity(self) -> None:
        lam = 1.2
        w0 = -1.0 + (lam * lam) / 3.0
        bg = solve_sigmatensor_v1_background(
            SigmaTensorV1Params(
                H0_si=float(H0_to_SI(67.4)),
                Omega_m0=0.0,
                w_phi0=w0,
                lambda_=lam,
                Omega_r0_override=0.0,
                sign_u0=+1,
            ),
            z_max=3.0,
            n_steps=2048,
        )
        alphas = sigmatensor_v1_eft_alphas(bg)
        alpha_k = [float(x) for x in alphas["alpha_K"]]
        alpha_k_cross = [float(x) for x in alphas["alpha_K_from_Omega_phi_w_phi"]]

        idxs = [0, len(alpha_k) // 4, len(alpha_k) // 2, (3 * len(alpha_k)) // 4, len(alpha_k) - 1]
        target = lam * lam
        for idx in idxs:
            got = alpha_k[idx]
            rel = abs(got - target) / target
            self.assertLess(rel, 2.0e-3, msg=f"idx={idx} rel={rel:.3e}")
            self.assertLess(abs(got - alpha_k_cross[idx]), 2.0e-9, msg=f"idx={idx}")

        for key in ("alpha_M", "alpha_B", "alpha_T"):
            self.assertTrue(all(abs(float(x)) == 0.0 for x in alphas[key]), msg=key)
        self.assertTrue(all(math.isfinite(float(x)) for x in alphas["c_s2"]))
        self.assertTrue(all(abs(float(x) - 1.0) == 0.0 for x in alphas["c_s2"]))


if __name__ == "__main__":
    unittest.main()

