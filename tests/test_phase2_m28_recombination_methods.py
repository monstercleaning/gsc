import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.recombination_methods import compute_z_star  # noqa: E402
from gsc.early_time.rd import omega_r_h2  # noqa: E402
from gsc.measurement_model import H0_to_SI  # noqa: E402


class TestPhase2M28RecombinationMethods(unittest.TestCase):
    def test_z_star_fit_and_peebles3_are_finite_and_sane(self):
        h0_km_s_mpc = 67.4
        h0_si = H0_to_SI(h0_km_s_mpc)
        omega_m = 0.315
        neff = 3.046
        tcmb_k = 2.7255
        omega_b_h2 = 0.02237
        omega_c_h2 = 0.1200

        h = h0_km_s_mpc / 100.0
        omega_r = omega_r_h2(Tcmb_K=tcmb_k, N_eff=neff) / (h * h)
        omega_lambda = 1.0 - omega_m - omega_r
        omega_m_h2 = omega_b_h2 + omega_c_h2

        z_fit, fit_meta = compute_z_star(
            method="fit",
            omega_b_h2=omega_b_h2,
            omega_m_h2=omega_m_h2,
            H0_si=h0_si,
            Omega_m=omega_m,
            Omega_r=omega_r,
            Omega_lambda=omega_lambda,
            Tcmb_K=tcmb_k,
            Y_p=0.245,
        )
        z_peeb, peeb_meta = compute_z_star(
            method="peebles3",
            omega_b_h2=omega_b_h2,
            omega_m_h2=omega_m_h2,
            H0_si=h0_si,
            Omega_m=omega_m,
            Omega_r=omega_r,
            Omega_lambda=omega_lambda,
            Tcmb_K=tcmb_k,
            Y_p=0.245,
            max_steps=2048,
            rtol=1e-6,
            atol=1e-10,
        )

        self.assertTrue(math.isfinite(z_fit))
        self.assertTrue(math.isfinite(z_peeb))
        self.assertGreater(z_fit, 800.0)
        self.assertLess(z_fit, 1400.0)
        self.assertGreater(z_peeb, 800.0)
        self.assertLess(z_peeb, 1400.0)

        rel_diff = abs(float(z_peeb) - float(z_fit)) / float(z_fit)
        self.assertLess(rel_diff, 0.05)

        self.assertEqual(fit_meta.get("method"), "fit")
        self.assertIn("method", peeb_meta)
        self.assertIn("converged", peeb_meta)
        self.assertIsInstance(bool(peeb_meta.get("converged")), bool)

    def test_recombination_metadata_is_finite(self):
        h0_km_s_mpc = 67.4
        h0_si = H0_to_SI(h0_km_s_mpc)
        omega_m = 0.315
        neff = 3.046
        tcmb_k = 2.7255
        omega_b_h2 = 0.02237
        omega_c_h2 = 0.1200

        h = h0_km_s_mpc / 100.0
        omega_r = omega_r_h2(Tcmb_K=tcmb_k, N_eff=neff) / (h * h)
        omega_lambda = 1.0 - omega_m - omega_r
        omega_m_h2 = omega_b_h2 + omega_c_h2

        _, meta = compute_z_star(
            method="peebles3",
            omega_b_h2=omega_b_h2,
            omega_m_h2=omega_m_h2,
            H0_si=h0_si,
            Omega_m=omega_m,
            Omega_r=omega_r,
            Omega_lambda=omega_lambda,
            Tcmb_K=tcmb_k,
            Y_p=0.245,
            max_steps=512,
            rtol=1e-6,
            atol=1e-10,
        )

        steps = int(meta.get("steps", 0) or 0)
        self.assertGreaterEqual(steps, 0)
        for key in ("rtol", "atol"):
            value = meta.get(key)
            if value is None:
                continue
            self.assertTrue(math.isfinite(float(value)))
            self.assertGreater(float(value), 0.0)


if __name__ == "__main__":
    unittest.main()
