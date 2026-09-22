import math
import unittest

from pathlib import Path
import sys

# Allow running from the package root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    C_SI,
    PC_SI,
    D_A_flat,
    D_L_flat,
    D_L_from_distance_modulus,
    FlatLambdaCDMHistory,
    H0_to_SI,
    PowerLawHistory,
    comoving_distance_flat,
    delta_v_cm_s,
    distance_modulus_flat,
    distance_modulus_from_D_L,
    sigma_ratio_from_z,
    time_dilation_factor,
    tolman_surface_brightness_ratio,
    z_dot_sandage_loeb,
    z_from_sigma,
)


class TestMeasurementModel(unittest.TestCase):
    def test_z_from_sigma(self):
        self.assertAlmostEqual(z_from_sigma(sigma_emit=1.0, sigma_obs=1.0), 0.0)
        self.assertAlmostEqual(z_from_sigma(sigma_emit=2.0, sigma_obs=1.0), 1.0)
        self.assertAlmostEqual(z_from_sigma(sigma_emit=1.0, sigma_obs=2.0), -0.5)

    def test_sigma_ratio_from_z(self):
        self.assertAlmostEqual(sigma_ratio_from_z(0.0), 1.0)
        self.assertAlmostEqual(sigma_ratio_from_z(2.0), 3.0)

    def test_time_dilation_is_1_plus_z(self):
        self.assertAlmostEqual(time_dilation_factor(0.0), 1.0)
        self.assertAlmostEqual(time_dilation_factor(2.0), 3.0)

    def test_tolman_surface_brightness_scaling(self):
        self.assertAlmostEqual(tolman_surface_brightness_ratio(0.0), 1.0)
        self.assertAlmostEqual(tolman_surface_brightness_ratio(1.0), 1.0 / 16.0)

    def test_distance_modulus_definition_and_inverse(self):
        mu0 = distance_modulus_from_D_L(D_L_m=10.0 * PC_SI)
        self.assertAlmostEqual(mu0, 0.0)

        mu = 33.21
        dl = D_L_from_distance_modulus(mu=mu)
        mu2 = distance_modulus_from_D_L(D_L_m=dl)
        self.assertAlmostEqual(mu2, mu, places=12)

    def test_redshift_drift_positive_for_p_lt_1(self):
        H0 = H0_to_SI(67.4)
        hist = PowerLawHistory(H0=H0, p=0.5)
        z = 3.0
        z_dot = z_dot_sandage_loeb(z=z, H0=H0, H_of_z=hist.H)
        self.assertGreater(z_dot, 0.0)

    def test_lcdm_redshift_drift_changes_sign(self):
        # In flat ΛCDM: ż > 0 at low z and ż < 0 at high z (~2-5).
        H0 = H0_to_SI(67.4)
        lcdm = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)
        self.assertGreater(z_dot_sandage_loeb(z=0.5, H0=H0, H_of_z=lcdm.H), 0.0)
        self.assertLess(z_dot_sandage_loeb(z=4.0, H0=H0, H_of_z=lcdm.H), 0.0)

    def test_lcdm_redshift_drift_matches_trost_2025_order_of_magnitude(self):
        # v10.1 pre-publication sanity gate (see GSC_v10_prepub_tests):
        # Trost et al. (A&A 699, A159, 2025) quotes ~ -0.43 cm/s/yr at z=3.573
        # for a Planck-like ΛCDM baseline.
        H0 = H0_to_SI(67.4)
        lcdm = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)
        dv_1yr = delta_v_cm_s(z=3.573, years=1.0, H0=H0, H_of_z=lcdm.H)
        self.assertAlmostEqual(dv_1yr, -0.43, delta=0.05)

    def test_comoving_distance_constant_H(self):
        H0 = 1.23e-18

        def H_of_z(_z: float) -> float:
            return H0

        z = 2.5
        chi = comoving_distance_flat(z=z, H_of_z=H_of_z, n=2000)
        self.assertAlmostEqual(chi, C_SI * z / H0, delta=1e-8 * C_SI * z / H0)

    def test_distance_modulus_flat_constant_H(self):
        H0 = 1.23e-18

        def H_of_z(_z: float) -> float:
            return H0

        z = 0.7
        dl_analytic = (1.0 + z) * C_SI * z / H0
        mu_expected = distance_modulus_from_D_L(D_L_m=dl_analytic)
        mu = distance_modulus_flat(z=z, H_of_z=H_of_z, n=2000)
        self.assertAlmostEqual(mu, mu_expected, delta=5e-10)

    def test_etherington_reciprocity_in_flat_helpers(self):
        H0 = 2.0e-18

        def H_of_z(_z: float) -> float:
            return H0

        z = 1.7
        dl = D_L_flat(z=z, H_of_z=H_of_z, n=2000)
        da = D_A_flat(z=z, H_of_z=H_of_z, n=2000)
        self.assertAlmostEqual(dl, (1.0 + z) ** 2 * da, delta=1e-12 * dl)


if __name__ == "__main__":
    unittest.main()


class TestSigmaModulatedLCDMHistory(unittest.TestCase):
    """The modulated late-time history used by P8 must stay LCDM-degenerate.

    Guards the P8 r2 finding: the canonical metrology exponent must produce a
    sub-percent modulation of LCDM with identical drift sign structure — never
    a coasting universe (which is what feeding it into PowerLawHistory gives).
    """

    def _histories(self):
        from gsc.canonical_params import CANONICAL_P
        from gsc.measurement_model import (
            FlatLambdaCDMHistory,
            PowerLawHistory,
            SigmaModulatedLCDMHistory,
            H0_to_SI,
            z_dot_sandage_loeb,
        )
        H0 = H0_to_SI(67.4)
        lcdm = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)
        mod = SigmaModulatedLCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685, p=CANONICAL_P)
        toy = PowerLawHistory(H0=H0, p=CANONICAL_P)
        return H0, lcdm, mod, toy, z_dot_sandage_loeb

    def test_modulated_history_is_sub_percent_from_lcdm(self):
        H0, lcdm, mod, _, _ = self._histories()
        for z in (0.1, 0.5, 1.0, 2.0, 3.0, 5.0):
            rel = abs(mod.H(z) / lcdm.H(z) - 1.0)
            self.assertLess(rel, 0.01, msg=f"z={z}: H deviates from LCDM by {rel:.4%}")

    def test_modulated_history_keeps_lcdm_drift_sign_structure(self):
        H0, lcdm, mod, _, z_dot = self._histories()
        for z in (0.1, 1.0, 1.5, 2.0, 3.0, 5.0):
            a = z_dot(z=z, H0=H0, H_of_z=lcdm.H)
            b = z_dot(z=z, H0=H0, H_of_z=mod.H)
            self.assertGreater(a * b, 0.0, msg=f"z={z}: drift sign differs from LCDM")

    def test_canonical_p_in_toy_history_is_coasting_and_thus_wrong(self):
        # Negative control: the misuse that produced P8 r1 must remain detectable.
        H0, lcdm, _, toy, _ = self._histories()
        self.assertLess(abs(toy.H(2.33) / H0 - 1.0), 0.01, "toy at canonical p should be ~coasting")
        self.assertGreater(lcdm.H(2.33) / toy.H(2.33), 3.0, "LCDM H(z=2.33) is >3x the coasting value")
