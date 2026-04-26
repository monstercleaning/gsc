import unittest

from pathlib import Path
import sys

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.drift import DriftDataset  # noqa: E402
from gsc.datasets.sn import SNDataset, load_covariance  # noqa: E402
from gsc.likelihood import chi2_total  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    H0_to_SI,
    delta_v_cm_s,
    distance_modulus_flat,
)


class TestDatasets(unittest.TestCase):
    def test_sn_dataset_fits_delta_M(self):
        H0 = H0_to_SI(67.4)
        model = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)

        zs = (0.05, 0.2, 0.7, 1.1)
        delta_M_true = 1.23
        sig = 0.1
        mu_th = [distance_modulus_flat(z=z, H_of_z=model.H, n=2000) for z in zs]
        mu_obs = [m + delta_M_true for m in mu_th]
        ds = SNDataset(name="sn_synth", z=zs, mu=tuple(mu_obs), sigma_mu=tuple([sig] * len(zs)))

        r = ds.chi2(model, fit_delta_M=True, n=2000)
        self.assertAlmostEqual(r.chi2, 0.0, places=12)
        self.assertAlmostEqual(r.params["delta_M"], delta_M_true, places=12)
        self.assertEqual(r.ndof, len(zs) - 1)
        self.assertEqual(r.meta.get("method"), "diag")

    def test_sn_covariance_delta_M_and_chi2(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")

        H0 = H0_to_SI(67.4)
        model = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)

        zs = (0.1, 0.5, 1.0)
        mu_th = np.array([distance_modulus_flat(z=z, H_of_z=model.H, n=2000) for z in zs], dtype=float)

        delta_M_true = 0.3
        noise = np.array([0.05, -0.12, 0.07], dtype=float)
        mu_obs = mu_th + delta_M_true + noise

        C = np.array(
            [
                [0.04, 0.01, 0.00],
                [0.01, 0.09, 0.02],
                [0.00, 0.02, 0.16],
            ],
            dtype=float,
        )

        ds = SNDataset(
            name="sn_cov_synth",
            z=zs,
            mu=tuple(float(x) for x in mu_obs),
            sigma_mu=tuple([1.0] * len(zs)),  # ignored in cov mode
            cov=C,
        )

        r = ds.chi2(model, fit_delta_M=True, n=2000)

        ones = np.ones(3, dtype=float)
        r0 = mu_obs - mu_th
        x = np.linalg.solve(C, r0)
        y = np.linalg.solve(C, ones)
        a = float(ones @ x)
        b = float(ones @ y)
        delta_M_hat = a / b
        chi2_hat = float(r0 @ x - (a * a) / b)

        self.assertAlmostEqual(r.params["delta_M"], delta_M_hat, places=12)
        self.assertAlmostEqual(r.chi2, chi2_hat, places=12)
        self.assertEqual(r.ndof, 2)
        self.assertEqual(r.meta.get("method"), "cov")

    def test_load_covariance_layouts(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")

        import tempfile

        n = 3
        full = np.arange(1, 10, dtype=float).reshape((3, 3))

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            p_full = td_p / "full.cov"
            p_tri = td_p / "tri.cov"
            p_full_with_n = td_p / "full_with_n.cov"

            p_full.write_text(" ".join(str(float(x)) for x in full.flatten()) + "\n", encoding="utf-8")

            tri_vals = []
            for i in range(n):
                for j in range(i + 1):
                    tri_vals.append(float(full[i, j]))
            p_tri.write_text(" ".join(str(x) for x in tri_vals) + "\n", encoding="utf-8")

            p_full_with_n.write_text(
                "3\n" + " ".join(str(float(x)) for x in full.flatten()) + "\n",
                encoding="utf-8",
            )

            cov_full = load_covariance(p_full, n=n, cache_npz=False)
            cov_tri = load_covariance(p_tri, n=n, cache_npz=False)
            cov_full_with_n = load_covariance(p_full_with_n, n=n, cache_npz=False)

            self.assertEqual(cov_full.shape, (3, 3))
            self.assertTrue(np.allclose(cov_full, full))

            self.assertTrue(np.allclose(cov_full_with_n, full))

            # tri is symmetrized
            self.assertTrue(np.allclose(cov_tri, np.tril(full) + np.tril(full, -1).T))

    def test_drift_dataset(self):
        H0 = H0_to_SI(67.4)
        model = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)

        z = 3.573
        baseline_years = 1.0
        dv = delta_v_cm_s(z=z, years=baseline_years, H0=model.H(0.0), H_of_z=model.H)
        ds = DriftDataset(
            name="drift_synth",
            z=(z,),
            dv_cm_s=(dv,),
            sigma_dv_cm_s=(0.05,),
            baseline_years=baseline_years,
        )

        r = ds.chi2(model)
        self.assertAlmostEqual(r.chi2, 0.0, places=12)
        self.assertEqual(r.ndof, 1)

    def test_chi2_total(self):
        H0 = H0_to_SI(67.4)
        model = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)

        sn = SNDataset(name="sn", z=(0.1,), mu=(distance_modulus_flat(z=0.1, H_of_z=model.H, n=2000),), sigma_mu=(0.2,))
        drift = DriftDataset(name="drift", z=(3.573,), dv_cm_s=(delta_v_cm_s(z=3.573, years=1.0, H0=model.H(0.0), H_of_z=model.H),), sigma_dv_cm_s=(0.3,), baseline_years=1.0)

        r = chi2_total(model=model, datasets=[sn, drift])
        self.assertAlmostEqual(r.chi2, 0.0, places=12)
        self.assertEqual(r.ndof, 1 + 1 - 1)  # SN fits delta_M


if __name__ == "__main__":
    unittest.main()
