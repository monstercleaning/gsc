import unittest

from pathlib import Path
import sys

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.drift import DriftDataset  # noqa: E402
from gsc.fit import profile_H0_from_drift  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    H0_to_SI,
    delta_v_cm_s,
)


class TestDriftProfileH0(unittest.TestCase):
    def test_profile_H0_recovers_fiducial_noiseless(self):
        # Generate a noiseless drift dataset from a fiducial LCDM model.
        H0_true_km_s_Mpc = 67.4
        Om = 0.315
        Ol = 1.0 - Om
        H0_true_si = H0_to_SI(H0_true_km_s_Mpc)
        fid = FlatLambdaCDMHistory(H0=H0_true_si, Omega_m=Om, Omega_Lambda=Ol)

        years = 20.0
        zs = (2.0, 3.0, 4.0, 4.5)
        sig = 1.0
        dvs = tuple(delta_v_cm_s(z=z, years=years, H0=H0_true_si, H_of_z=fid.H) for z in zs)
        drift = DriftDataset(
            name="noiseless",
            z=zs,
            dv_cm_s=dvs,
            sigma_dv_cm_s=tuple(sig for _ in zs),
            baseline_years=years,
        )

        # Use a *different* H0 for the reference shape; profiling should still recover H0_true.
        H0_ref_si = H0_to_SI(70.0)
        ref = FlatLambdaCDMHistory(H0=H0_ref_si, Omega_m=Om, Omega_Lambda=Ol)

        res = profile_H0_from_drift(drift=drift, model_ref=ref, H0_bounds_km_s_Mpc=(60.0, 80.0))
        self.assertFalse(res["clamped"])
        self.assertAlmostEqual(res["H0_km_s_Mpc"], H0_true_km_s_Mpc, places=6)
        self.assertLess(res["chi2"], 1e-9)
        self.assertEqual(res["ndof"], len(zs) - 1)

    def test_profile_H0_clamps_to_bounds(self):
        H0_true_km_s_Mpc = 67.4
        Om = 0.315
        Ol = 1.0 - Om
        H0_true_si = H0_to_SI(H0_true_km_s_Mpc)
        fid = FlatLambdaCDMHistory(H0=H0_true_si, Omega_m=Om, Omega_Lambda=Ol)

        years = 20.0
        zs = (2.0, 3.0, 4.0)
        sig = 1.0
        dvs = tuple(delta_v_cm_s(z=z, years=years, H0=H0_true_si, H_of_z=fid.H) for z in zs)
        drift = DriftDataset(
            name="noiseless",
            z=zs,
            dv_cm_s=dvs,
            sigma_dv_cm_s=tuple(sig for _ in zs),
            baseline_years=years,
        )

        H0_ref_si = H0_to_SI(70.0)
        ref = FlatLambdaCDMHistory(H0=H0_ref_si, Omega_m=Om, Omega_Lambda=Ol)

        res = profile_H0_from_drift(drift=drift, model_ref=ref, H0_bounds_km_s_Mpc=(60.0, 65.0))
        self.assertTrue(res["clamped"])
        self.assertAlmostEqual(res["H0_km_s_Mpc"], 65.0, places=10)


if __name__ == "__main__":
    unittest.main()
