import unittest

from pathlib import Path
import sys

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time import compute_rd_Mpc, z_drag_eisenstein_hu  # noqa: E402


class TestEarlyTimeBridgeRD(unittest.TestCase):
    def test_rd_planck_like_sanity(self):
        # Planck-like physical densities; EH98+integral is approximate, so keep broad tolerance.
        rd = compute_rd_Mpc(omega_b_h2=0.02237, omega_c_h2=0.1200)
        self.assertTrue(145.0 <= rd <= 155.0)

    def test_rd_monotonic_with_omega_m_h2(self):
        # Larger matter density -> larger H(z) -> smaller sound horizon.
        rd_low = compute_rd_Mpc(omega_b_h2=0.02237, omega_c_h2=0.1100)
        rd_high = compute_rd_Mpc(omega_b_h2=0.02237, omega_c_h2=0.1300)
        self.assertGreater(rd_low, rd_high)

    def test_z_drag_guardrail_range(self):
        z_d = z_drag_eisenstein_hu(omega_m_h2=0.14237, omega_b_h2=0.02237)
        self.assertTrue(800.0 <= z_d <= 1500.0)

    def test_neff_alias_matches_n_eff(self):
        rd_a = compute_rd_Mpc(omega_b_h2=0.02237, omega_c_h2=0.1200, N_eff=3.046)
        rd_b = compute_rd_Mpc(omega_b_h2=0.02237, omega_c_h2=0.1200, Neff=3.046)
        self.assertAlmostEqual(rd_a, rd_b, places=12)


if __name__ == "__main__":
    unittest.main()
