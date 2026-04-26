import unittest

from pathlib import Path
import sys

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import (  # noqa: E402
    BAOBlock1D,
    BAOBlock2D,
    BAODataset,
    D_H,
)
from gsc.measurement_model import C_SI, D_M_flat, MPC_SI  # noqa: E402


class ConstantH:
    def __init__(self, H0: float):
        self._H0 = float(H0)

    def H(self, _z: float) -> float:
        return self._H0


class TestBAO(unittest.TestCase):
    def test_profile_rd_isotropic_1d(self):
        model = ConstantH(H0=2.0e-18)
        rd_true = 147.0 * MPC_SI

        # Two points so profiling does not make chi2 trivially zero.
        blocks = []
        for z, noise, sigma in [(0.1, 0.002, 0.01), (0.2, -0.001, 0.015)]:
            dm = D_M_flat(z=z, H_of_z=model.H, n=2000)
            dh = D_H(z=z, model=model)
            d = (z * dh * dm * dm) ** (1.0 / 3.0)
            y = d / rd_true + noise
            blocks.append(BAOBlock1D(z=z, y=y, sigma=sigma))

        ds = BAODataset(name="bao_synth_1d", blocks=tuple(blocks))
        r = ds.chi2(model, n=2000)

        # Expected analytic p_star from A,B.
        A = B = C = 0.0
        for b in blocks:
            a_i, b_i, c_i = b.abc(model, n=2000)
            A += a_i
            B += b_i
            C += c_i
        p_star = B / A
        chi2_star = C - (B * B) / A
        rd_star = 1.0 / p_star

        self.assertAlmostEqual(r.params["p_star"], p_star, places=14)
        self.assertAlmostEqual(r.params["rd_m"], rd_star, places=6)
        self.assertAlmostEqual(r.chi2, chi2_star, places=12)
        self.assertEqual(r.ndof, 1)  # 2 obs - 1 nuisance

    def test_profile_rd_anisotropic_2d(self):
        model = ConstantH(H0=2.0e-18)
        rd_true = 147.0 * MPC_SI

        z = 0.35
        dm = D_M_flat(z=z, H_of_z=model.H, n=2000)
        dh = D_H(z=z, model=model)

        y_dm = dm / rd_true + 0.001
        y_dh = dh / rd_true - 0.002

        sig_dm = 0.02
        sig_dh = 0.03
        rho = 0.4

        block = BAOBlock2D(
            z=z,
            y_dm=y_dm,
            y_dh=y_dh,
            sigma_dm=sig_dm,
            sigma_dh=sig_dh,
            rho_dm_dh=rho,
        )
        ds = BAODataset(name="bao_synth_2d", blocks=(block,))
        r = ds.chi2(model, n=2000)

        # Manual A,B,C with 2x2 inverse.
        a = sig_dm * sig_dm
        c = sig_dh * sig_dh
        b = rho * sig_dm * sig_dh
        det = a * c - b * b
        inv00 = c / det
        inv01 = -b / det
        inv11 = a / det

        A = dm * (inv00 * dm + inv01 * dh) + dh * (inv01 * dm + inv11 * dh)
        B = dm * (inv00 * y_dm + inv01 * y_dh) + dh * (inv01 * y_dm + inv11 * y_dh)
        C = y_dm * (inv00 * y_dm + inv01 * y_dh) + y_dh * (inv01 * y_dm + inv11 * y_dh)

        p_star = B / A
        chi2_star = C - (B * B) / A
        rd_star = 1.0 / p_star

        self.assertAlmostEqual(r.params["p_star"], p_star, places=14)
        self.assertAlmostEqual(r.params["rd_m"], rd_star, places=6)
        self.assertAlmostEqual(r.chi2, chi2_star, places=12)
        self.assertEqual(r.ndof, 1)  # 2 obs - 1 nuisance

    def test_fixed_rd_uses_no_nuisance_dof_penalty(self):
        model = ConstantH(H0=2.0e-18)
        rd_fixed = 147.0 * MPC_SI
        z = 0.2
        dm = D_M_flat(z=z, H_of_z=model.H, n=2000)
        dh = D_H(z=z, model=model)
        dv = (z * dh * dm * dm) ** (1.0 / 3.0)
        y = dv / rd_fixed
        block = BAOBlock1D(z=z, y=y, sigma=0.02)
        ds = BAODataset(name="bao_fixed", blocks=(block,))

        r = ds.chi2(model, rd_m=rd_fixed, n=2000)
        self.assertAlmostEqual(r.params["rd_m"], rd_fixed, places=6)
        self.assertEqual(r.ndof, 1)  # fixed-rd mode: no nuisance subtraction

    def test_csv_loader(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bao.csv"
            p.write_text(
                "type,z,dv_over_rd,sigma_dv_over_rd,label\n"
                "DV_over_rd,0.1,3.0,0.1,6dFGS\n"
                "DV_over_rd,0.2,4.0,0.2,MGS\n",
                encoding="utf-8",
            )
            ds = BAODataset.from_csv(p)
            self.assertEqual(len(ds.blocks), 2)


if __name__ == "__main__":
    unittest.main()
