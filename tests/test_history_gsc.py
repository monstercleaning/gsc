import unittest

from pathlib import Path
import sys

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    GSCTransitionHistory,
    PowerLawHistory,
    z_dot_sandage_loeb,
)


class TestGSCHistories(unittest.TestCase):
    def test_gsc_powerlaw_drift_positive_grid(self):
        H0 = 2.0e-18
        p = 0.6
        model = PowerLawHistory(H0=H0, p=p)

        for z in [0.1, 0.3, 0.7, 1.0, 2.0, 3.0, 5.0]:
            zdot = z_dot_sandage_loeb(z=z, H0=H0, H_of_z=model.H)
            self.assertGreater(zdot, 0.0)

    def test_gsc_transition_continuity_at_z_t(self):
        H0 = 2.0e-18
        Omega_m = 0.315
        Omega_L = 0.685
        p = 0.6
        zt = 1.8

        model = GSCTransitionHistory(H0=H0, Omega_m=Omega_m, Omega_Lambda=Omega_L, p=p, z_transition=zt)

        # At z_t the piecewise definition is designed to be continuous.
        Hz_t = model.H(zt)
        E_t = (Omega_m * (1.0 + zt) ** 3 + Omega_L) ** 0.5
        Hz_high_form = H0 * E_t * (((1.0 + zt) / (1.0 + zt)) ** p)
        self.assertAlmostEqual(Hz_t, Hz_high_form, places=15)

    def test_gsc_transition_drift_positive_grid(self):
        H0 = 2.0e-18
        Omega_m = 0.315
        Omega_L = 0.685
        p = 0.6
        zt = 1.8  # keep LCDM segment in its positive-drift regime

        model = GSCTransitionHistory(H0=H0, Omega_m=Omega_m, Omega_Lambda=Omega_L, p=p, z_transition=zt)

        for z in [0.1, 0.3, 0.7, 1.0, 1.7, 2.0, 3.0, 5.0]:
            zdot = z_dot_sandage_loeb(z=z, H0=H0, H_of_z=model.H)
            self.assertGreater(zdot, 0.0)


if __name__ == "__main__":
    unittest.main()
