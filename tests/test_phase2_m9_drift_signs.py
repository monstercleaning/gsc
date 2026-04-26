import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
    z_dot_sandage_loeb,
)


class TestPhase2M9DriftSigns(unittest.TestCase):
    def test_z_dot_powerlaw_sign(self):
        h0 = H0_to_SI(70.0)
        history_positive = PowerLawHistory(H0=h0, p=0.5)
        history_negative = PowerLawHistory(H0=h0, p=1.5)

        self.assertGreater(z_dot_sandage_loeb(z=3.0, H0=h0, H_of_z=history_positive.H), 0.0)
        self.assertLess(z_dot_sandage_loeb(z=3.0, H0=h0, H_of_z=history_negative.H), 0.0)

    def test_z_dot_lcdm_sign(self):
        h0 = H0_to_SI(67.4)
        history = FlatLambdaCDMHistory(H0=h0, Omega_m=0.315, Omega_Lambda=0.685)
        self.assertLess(z_dot_sandage_loeb(z=3.0, H0=h0, H_of_z=history.H), 0.0)

    def test_transition_history_positive_drift_hypothesis(self):
        h0 = H0_to_SI(67.4)
        history = GSCTransitionHistory(
            H0=h0,
            Omega_m=0.315,
            Omega_Lambda=0.685,
            p=0.6,
            z_transition=1.8,
        )
        for z in (2.0, 3.0, 4.0, 5.0):
            self.assertGreater(z_dot_sandage_loeb(z=z, H0=h0, H_of_z=history.H), 0.0)

    def test_z_dot_docstring_mentions_history_not_frame_claim(self):
        doc = z_dot_sandage_loeb.__doc__ or ""
        self.assertIn("frame-independent", doc)
        self.assertIn("histories", doc)


if __name__ == "__main__":
    unittest.main()
