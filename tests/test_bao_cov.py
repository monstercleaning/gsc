import unittest

from pathlib import Path
import sys

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import BAODataset  # noqa: E402
from gsc.measurement_model import C_SI, D_M_flat, MPC_SI  # noqa: E402


class ConstantH:
    def __init__(self, H0: float):
        self._H0 = float(H0)

    def H(self, _z: float) -> float:
        return self._H0


class TestBAOCovarianceBlock(unittest.TestCase):
    def test_vector_over_rd_block_profiles_rd(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")

        import tempfile

        model = ConstantH(H0=2.0e-18)
        rd_true = 150.0 * MPC_SI
        p_true = 1.0 / rd_true

        # Define 4 observables with a full covariance.
        obs = [
            ("DM", 0.2),
            ("DH", 0.2),
            ("DM", 0.5),
            ("DH", 0.5),
        ]

        # Model distance vector d (meters).
        d = []
        for k, z in obs:
            if k == "DM":
                d.append(D_M_flat(z=z, H_of_z=model.H, n=200))
            elif k == "DH":
                d.append(C_SI / model.H(z))
            else:
                raise AssertionError("unexpected kind")
        d = np.array(d, dtype=float)

        noise = np.array([0.002, -0.001, 0.0015, -0.0005], dtype=float)
        y = p_true * d + noise

        # Positive-definite covariance on y (dimensionless).
        C = np.array(
            [
                [1.0e-4, 2.0e-5, 0.0, 0.0],
                [2.0e-5, 2.5e-4, 0.0, 0.0],
                [0.0, 0.0, 1.4e-4, -1.0e-5],
                [0.0, 0.0, -1.0e-5, 1.9e-4],
            ],
            dtype=float,
        )

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            values_p = td_p / "values.csv"
            cov_p = td_p / "cov.cov"
            bao_p = td_p / "bao.csv"

            values_p.write_text(
                "kind,z,y\n"
                + "\n".join([f"{k},{z},{float(y_i):.16g}" for (k, z), y_i in zip(obs, y)])
                + "\n",
                encoding="utf-8",
            )

            cov_lines = []
            for row in C:
                cov_lines.append(" ".join(f"{float(x):.16g}" for x in row))
            cov_p.write_text("\n".join(cov_lines) + "\n", encoding="utf-8")

            bao_p.write_text(
                "type,values_path,cov_path,label\n"
                "VECTOR_over_rd,values.csv,cov.cov,synthetic\n",
                encoding="utf-8",
            )

            ds = BAODataset.from_csv(bao_p)
            r = ds.chi2(model, n=200)

        # Manual quadratic form profiling (no inverse; solve is fine for N=4).
        x = np.linalg.solve(C, d)
        u = np.linalg.solve(C, y)
        A = float(d @ x)
        B = float(d @ u)
        C0 = float(y @ u)
        p_star = B / A
        chi2_star = C0 - (B * B) / A

        self.assertAlmostEqual(r.params["p_star"], p_star, places=14)
        self.assertAlmostEqual(r.chi2, chi2_star, places=8)
        self.assertEqual(r.ndof, len(obs) - 1)


if __name__ == "__main__":
    unittest.main()
