import tempfile
import unittest
from pathlib import Path
import csv
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.cmb_priors import CMBPriorsDataset, load_cmb_priors_csv  # noqa: E402


class TestCMBPriorsLoader(unittest.TestCase):
    def test_load_scalar_priors(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cmb.csv"
            p.write_text(
                "name,value,sigma,label\n"
                "theta_star,0.0104,0.000003,Planck-like\n"
                "R,1.75,0.01,\n",
                encoding="utf-8",
            )
            priors = load_cmb_priors_csv(p)

        self.assertEqual(len(priors), 2)
        self.assertEqual(priors[0].name, "theta_star")
        self.assertAlmostEqual(priors[0].value, 0.0104)
        self.assertAlmostEqual(priors[0].sigma, 0.000003)
        self.assertAlmostEqual(priors[0].sigma_theory, 0.0)
        self.assertEqual(priors[0].label, "Planck-like")

    def test_rejects_nonpositive_sigma(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cmb.csv"
            p.write_text(
                "name,value,sigma\n"
                "theta_star,0.0104,0\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_cmb_priors_csv(p)

    def test_rejects_missing_required_columns(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cmb.csv"
            p.write_text(
                "name,value\n"
                "theta_star,0.0104\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_cmb_priors_csv(p)

    def test_dataset_chi2_diag(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cmb.csv"
            p.write_text(
                "name,value,sigma\n"
                "theta_star,0.0104,0.0002\n"
                "R,1.75,0.05\n",
                encoding="utf-8",
            )
            ds = CMBPriorsDataset.from_csv(p, name="cmb")

        pred = {"theta_star": 0.0105, "R": 1.80}
        r = ds.chi2_from_values(pred)
        self.assertEqual(r.ndof, 2)
        self.assertEqual(r.meta.get("method"), "diag")
        # ((0.0001/0.0002)^2 + (0.05/0.05)^2) = 0.25 + 1 = 1.25
        self.assertAlmostEqual(r.chi2, 1.25, places=12)

    def test_dataset_chi2_diag_supports_sigma_theory(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cmb.csv"
            p.write_text(
                "name,value,sigma,sigma_theory\n"
                "theta_star,0.0,1.0,1.0\n",
                encoding="utf-8",
            )
            ds = CMBPriorsDataset.from_csv(p, name="cmb")

        pred = {"theta_star": 1.0}
        r = ds.chi2_from_values(pred)
        # sigma_eff = sqrt(1^2 + 1^2) = sqrt(2); chi2 = (1/sqrt(2))^2 = 0.5
        self.assertAlmostEqual(r.chi2, 0.5, places=12)

    def test_dataset_chi2_covariance(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy not installed")

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            p_csv = td_p / "cmb.csv"
            p_cov = td_p / "cmb.cov"
            p_csv.write_text(
                "name,value,sigma\n"
                "theta_star,0.0104,0.0002\n"
                "R,1.75,0.05\n",
                encoding="utf-8",
            )
            cov = np.array(
                [
                    [4.0e-8, 0.0],
                    [0.0, 2.5e-3],
                ],
                dtype=float,
            )
            p_cov.write_text(
                "\n".join(" ".join(f"{float(x):.16g}" for x in row) for row in cov) + "\n",
                encoding="utf-8",
            )
            ds = CMBPriorsDataset.from_csv(p_csv, cov_path=p_cov, name="cmb")

        pred = {"theta_star": 0.0105, "R": 1.80}
        r = ds.chi2_from_values(pred)
        self.assertEqual(r.ndof, 2)
        self.assertEqual(r.meta.get("method"), "cov")
        self.assertAlmostEqual(r.chi2, 1.25, places=10)

    def test_chw2018_planck_distance_priors_cov_loads(self):
        try:
            import numpy as np  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        cmb_csv = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        cmb_cov = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

        ds = CMBPriorsDataset.from_csv(cmb_csv, cov_path=cmb_cov, name="cmb_chw2018")
        cov = np.asarray(ds.cov, dtype=float)
        np.linalg.cholesky(cov)  # should be positive-definite

        # If we evaluate at the mean itself, chi2 should be exactly ~0.
        pred = {p.name: p.value for p in ds.priors}
        r = ds.chi2_from_values(pred)
        self.assertAlmostEqual(r.chi2, 0.0, places=12)

    def test_chw2018_strict_has_no_sigma_theory_column(self):
        # Guardrail: the canonical CHW2018 dataset is strict by default.
        cmb_csv = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        with cmb_csv.open("r", newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            header = next(r)
        self.assertNotIn("sigma_theory", header)
        self.assertNotIn("sigma_th", header)


if __name__ == "__main__":
    unittest.main()
