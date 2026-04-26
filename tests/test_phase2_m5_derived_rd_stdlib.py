import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import BAOBlock1D, BAODataset, BAODatasetFixedRd  # noqa: E402
from gsc.early_time import compute_rd_Mpc  # noqa: E402
from gsc.measurement_model import C_SI, D_M_flat, MPC_SI  # noqa: E402


class _ConstantH:
    def __init__(self, h0: float):
        self._h0 = float(h0)

    def H(self, _z: float) -> float:
        return self._h0


class TestPhase2M5DerivedRDStdlib(unittest.TestCase):
    def test_rd_regression_planck_like(self):
        rd = compute_rd_Mpc(
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            method="eisenstein_hu_1998",
        )
        # EH98-like closure is approximate; keep a pragmatic regression window
        # around the current deterministic baseline implementation.
        self.assertAlmostEqual(float(rd), 150.8, delta=2.5)

    def test_bao_fixed_rd_ndof_and_method(self):
        model = _ConstantH(h0=2.0e-18)
        rd_m = 147.0 * float(MPC_SI)
        z = 0.2
        dm = D_M_flat(z=z, H_of_z=model.H, n=2000)
        dh = float(C_SI) / float(model.H(z))
        dv = (z * dh * dm * dm) ** (1.0 / 3.0)
        y = dv / rd_m
        base = BAODataset(name="bao_one_point", blocks=(BAOBlock1D(z=z, y=y, sigma=0.05),))
        fixed = BAODatasetFixedRd(base=base, rd_m=rd_m, name="bao")

        result = fixed.chi2(model)
        self.assertEqual(result.meta.get("method"), "fixed_rd")
        self.assertEqual(int(result.ndof), 1)
        self.assertGreater(float(result.params.get("rd_m", 0.0)), 0.0)


if __name__ == "__main__":
    unittest.main()
