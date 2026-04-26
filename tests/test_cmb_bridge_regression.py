import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.cmb_distance_priors import (  # noqa: E402
    compute_bridged_distance_priors,
    compute_lcdm_distance_priors,
)
from gsc.early_time.rd import omega_r_h2  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    GSCTransitionHistory,
    H0_to_SI,
)


class _LCDMRadiationModel:
    """Self-consistent LCDM+rad H(z) model used to regression-test bridging glue."""

    def __init__(self, *, H0_si: float, Omega_m: float, Omega_r: float, Omega_lambda: float):
        self._H0_si = float(H0_si)
        self._Om = float(Omega_m)
        self._Or = float(Omega_r)
        self._Ol = float(Omega_lambda)

    def H(self, z: float) -> float:
        return self._H0_si * math.sqrt(self._Or * (1.0 + z) ** 4 + self._Om * (1.0 + z) ** 3 + self._Ol)


class TestCMBDistancePriorsBridge(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        self.H0_km_s_Mpc = 67.4
        self.omega_b_h2 = 0.02237
        self.omega_c_h2 = 0.1200
        self.N_eff = 3.046
        self.Tcmb_K = 2.7255

        h = self.H0_km_s_Mpc / 100.0
        omega_r_h2_val = omega_r_h2(Tcmb_K=self.Tcmb_K, N_eff=self.N_eff)
        self.Omega_r = float(omega_r_h2_val) / (h * h)
        self.Omega_m_early = float(self.omega_b_h2 + self.omega_c_h2) / (h * h)
        self.Omega_lambda_early = 1.0 - float(self.Omega_m_early) - float(self.Omega_r)

        self.H0_si = float(H0_to_SI(self.H0_km_s_Mpc))

    def test_bridged_priors_match_lcdm_for_self_consistent_model(self):
        # If the model's H(z) matches the early-time LCDM+rad piece used by the bridge,
        # the split-integral glue should reproduce the pure LCDM distance priors across
        # a wide range of z_bridge values.
        model = _LCDMRadiationModel(
            H0_si=self.H0_si,
            Omega_m=self.Omega_m_early,
            Omega_r=self.Omega_r,
            Omega_lambda=self.Omega_lambda_early,
        )
        base = compute_lcdm_distance_priors(
            H0_km_s_Mpc=self.H0_km_s_Mpc,
            Omega_m=self.Omega_m_early,
            omega_b_h2=self.omega_b_h2,
            omega_c_h2=self.omega_c_h2,
            N_eff=self.N_eff,
            Tcmb_K=self.Tcmb_K,
        )

        # Include values spanning "almost no late-time" up to "moderate late-time"
        # contributions, but avoid huge z_bridge to keep this unit test cheap.
        for z_bridge in (1e-6, 0.1, 1.0, 5.0, 10.0, 30.0, 100.0):
            pred = compute_bridged_distance_priors(
                model=model,
                z_bridge=z_bridge,
                omega_b_h2=self.omega_b_h2,
                omega_c_h2=self.omega_c_h2,
                N_eff=self.N_eff,
                Tcmb_K=self.Tcmb_K,
            )
            for k in ("theta_star", "lA", "R", "D_M_star_Mpc", "r_s_star_Mpc"):
                rel = abs(pred[k] - base[k]) / abs(base[k])
                self.assertLess(rel, 1e-4, msg=f"{k} rel={rel} z_bridge={z_bridge}")

    def test_bridge_z_is_clamped_at_z_star(self):
        model = _LCDMRadiationModel(
            H0_si=self.H0_si,
            Omega_m=self.Omega_m_early,
            Omega_r=self.Omega_r,
            Omega_lambda=self.Omega_lambda_early,
        )

        out_small = compute_bridged_distance_priors(
            model=model,
            z_bridge=10.0,
            omega_b_h2=self.omega_b_h2,
            omega_c_h2=self.omega_c_h2,
            N_eff=self.N_eff,
            Tcmb_K=self.Tcmb_K,
        )
        self.assertAlmostEqual(out_small["bridge_z"], 10.0, places=12)

        out_large = compute_bridged_distance_priors(
            model=model,
            z_bridge=1.0e9,
            omega_b_h2=self.omega_b_h2,
            omega_c_h2=self.omega_c_h2,
            N_eff=self.N_eff,
            Tcmb_K=self.Tcmb_K,
        )
        self.assertAlmostEqual(out_large["bridge_z"], out_large["z_star"], places=12)

    def test_bridged_priors_are_finite_for_gsc_transition(self):
        # This is a smoke test: bridge should return finite values for a typical
        # late-time non-LCDM history when z_bridge is provided.
        H0_si = self.H0_si
        Omega_m = 0.315
        Omega_lambda = 1.0 - Omega_m
        model = GSCTransitionHistory(
            H0=H0_si,
            Omega_m=Omega_m,
            Omega_Lambda=Omega_lambda,
            p=0.7,
            z_transition=1.8,
        )
        out = compute_bridged_distance_priors(
            model=model,
            z_bridge=10.0,
            omega_b_h2=self.omega_b_h2,
            omega_c_h2=self.omega_c_h2,
            N_eff=self.N_eff,
            Tcmb_K=self.Tcmb_K,
        )
        for k in ("theta_star", "lA", "R", "r_s_star_Mpc", "D_M_star_Mpc", "rd_Mpc", "bridge_H_ratio"):
            self.assertTrue(math.isfinite(float(out[k])), msg=f"{k} is not finite")
        self.assertGreater(out["theta_star"], 0.0)
        self.assertGreater(out["r_s_star_Mpc"], 0.0)
        self.assertGreater(out["D_M_star_Mpc"], 0.0)


if __name__ == "__main__":
    unittest.main()
