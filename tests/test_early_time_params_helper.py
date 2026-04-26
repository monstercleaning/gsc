import unittest

from argparse import Namespace
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.params import EarlyTimeParams, early_time_params_from_namespace  # noqa: E402


class TestEarlyTimeParamsHelper(unittest.TestCase):
    def test_namespace_parses_neff_alias_and_method(self):
        ns = Namespace(
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            Neff=3.046,
            Tcmb_K=2.7255,
            rd_method="eisenstein_hu_1998",
        )
        p = early_time_params_from_namespace(ns, require=True, context="test")
        self.assertIsInstance(p, EarlyTimeParams)
        self.assertAlmostEqual(float(p.omega_b_h2), 0.02237, places=12)
        self.assertAlmostEqual(float(p.omega_c_h2), 0.1200, places=12)
        self.assertAlmostEqual(float(p.N_eff), 3.046, places=12)
        self.assertEqual(str(p.rd_method), "eisenstein_hu_1998")

    def test_namespace_requires_both_density_inputs(self):
        ns = Namespace(omega_b_h2=0.02237, omega_c_h2=None, Neff=3.046, Tcmb_K=2.7255, rd_method="x")
        with self.assertRaisesRegex(ValueError, "requires --omega-b-h2 and --omega-c-h2"):
            early_time_params_from_namespace(ns, require=True, context="--cmb")

    def test_rd_kwargs_include_canonical_fields(self):
        p = EarlyTimeParams(omega_b_h2=0.02237, omega_c_h2=0.1200, N_eff=3.046, Tcmb_K=2.7255, rd_method="foo")
        rd_kwargs = p.to_rd_kwargs()
        self.assertEqual(set(rd_kwargs.keys()), {"omega_b_h2", "omega_c_h2", "N_eff", "Tcmb_K", "method"})
        self.assertEqual(rd_kwargs["method"], "foo")


if __name__ == "__main__":
    unittest.main()
