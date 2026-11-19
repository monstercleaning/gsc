"""Cross-check the beta scan against the physical model, BAO data and CMB translations."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyses"))
import p14_beta_scan as scan
import p14_physical_model as model
import timescape_fit as bao


class TestP14BetaScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(scan.OUTPUT.read_text())
        cls.rows = {row["beta"]: row for row in cls.report["rows"]}
        cls.physical = json.loads(model.OUTPUT.read_text())

    def test_recompute_json_and_rendering(self):
        subprocess.run([sys.executable, str(scan.OUTPUT.with_suffix(".py")), "--check"], check=True)

    def test_grid_and_reference_rows(self):
        expected = {float(f"{10**(-3+i/8):.10g}") for i in range(25)}
        alt = self.physical["alternative_coupling"]
        self.assertTrue(expected.union({.008, .01, .02, alt["beta"]}).issubset(self.rows))
        self.assertEqual(list(self.rows), sorted(self.rows))
        self.assertEqual(len(self.rows), len(self.report["rows"]))
        unit, cancel = self.rows[1.], self.rows[alt["beta"]]
        self.assertAlmostEqual(unit["H_atomic_over_standard"]["0.1"], .98581, places=5)
        self.assertAlmostEqual(cancel["H_atomic_over_standard"]["0.1"], alt["H_ratio_at_0.1_MeV"], places=8)
        self.assertAlmostEqual(unit["omega_phi_recombination"], .000219, delta=.000001)
        self.assertAlmostEqual(cancel["omega_phi_recombination"], .035, delta=.001)
        for el in model.ELEMENTS:
            self.assertAlmostEqual(unit["network_ratios"][el], self.physical["abundance_ratios"]["physical"][el], places=8)
            self.assertAlmostEqual(cancel["network_ratios"][el], alt["abundance_ratios"][el], places=8)
        self.assertAlmostEqual(self.rows[.01]["likelihood_standard_over_model"], 10.7, delta=.05)
        self.assertAlmostEqual(self.rows[.02]["likelihood_standard_over_model"], 14.1, delta=.05)

    def test_scalar_accounting_and_cmb_crossings(self):
        for beta, row in self.rows.items():
            k2 = (self.report["q"]/beta)**2
            omega = row["omega_phi_radiation"]
            self.assertAlmostEqual(omega, k2/4, places=9)
            one_nu = 7/8 * (4/11)**(4/3)
            rad_per_nu = 1/one_nu + self.report["N_eff_standard"]
            self.assertAlmostEqual(row["delta_N_eff_energy"] / rad_per_nu, omega/(1-omega), places=9)
            self.assertAlmostEqual((1+row["w_phi_today"])*3*model.DARK0/model.CRITICAL, k2, places=8)
        fractions = [r["omega_phi_recombination"] for r in self.rows.values()]
        self.assertEqual(fractions, sorted(fractions, reverse=True))
        for limit in self.report["smooth_fraction_translations"]:
            threshold = limit["beta_min"]
            self.assertAlmostEqual(self.rows[threshold]["omega_phi_recombination"], limit["omega_phi_max"], places=9)
            selected = [r["likelihood_standard_over_model"] for b, r in self.rows.items() if b >= threshold]
            self.assertEqual(limit["likelihood_range"], [min(selected), max(selected)])

    def test_profiled_bao(self):
        data = bao.load_bao()
        null = self.report["bao_k0"]
        self.assertAlmostEqual(null["chi2"], 10.54, places=2)
        self.assertAlmostEqual(null["C_m"], .2975, delta=.001)
        cancel = self.rows[self.report["cancelling_beta"]]
        self.assertAlmostEqual(cancel["bao"]["chi2"], 9.71, places=2)
        # The earlier background estimate used beta rounded to 0.0026.
        rounded = scan.fit_bao((self.report["q"]/.0026)**2, data)
        self.assertAlmostEqual(rounded["chi2"], 9.73, places=2)
        for row in (self.rows[.001], cancel, self.rows[1.]):
            fit, k2 = row["bao"], row["k"]**2
            self.assertAlmostEqual(fit["delta_chi2_vs_k0"], fit["chi2"]-null["chi2"], places=7)
            scale = scan.jf.C/fit["H0_rd_km_s"]
            # Evaluate the residuals directly at the reported scale, without the profiler.
            total = 0.
            for shape, obs, icov in bao.shape_blocks(scan.LateBranch(fit["C_m"], k2), data):
                diff = [scale*s - d for s, d in zip(shape, obs)]
                total += sum(x*icov[i][j]*y for i, x in enumerate(diff) for j, y in enumerate(diff))
            self.assertAlmostEqual(total, fit["chi2"], places=7)
            for offset in (-.001, .001):
                shifted = scan.LateBranch(fit["C_m"]+offset, k2)
                self.assertGreater(bao.chi2_bao_scale_free(shifted, data)[0], total)
