"""Diagnostic analyses are deterministic and reproduce their committed outputs."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyses"))
import joint_fit  # noqa: E402
import timescape_fit  # noqa: E402
import ccbh_fit  # noqa: E402


class TestAnalyses(unittest.TestCase):
    def test_p_role_consistency_reproduces_its_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            subprocess.run([sys.executable, str(ROOT / "analyses" / "p_role_consistency.py"), "--output", str(out)],
                           check=True, capture_output=True)
            self.assertEqual(out.read_bytes(), (ROOT / "analyses" / "p_role_consistency.json").read_bytes())

    def test_w0wa_diagnostic_fast_blocks_reproduce(self):
        committed = json.loads((ROOT / "analyses" / "w0wa_rd_shift_diagnostic.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            subprocess.run([sys.executable, str(ROOT / "analyses" / "w0wa_rd_shift_diagnostic.py"), "--fast",
                            "--output", str(out)], check=True, capture_output=True)
            fresh = json.loads(out.read_text())
        for key in ("controls", "fits_on_shifted_mock", "fits_on_shifted_mock_dr2_precision"):
            with self.subTest(block=key):
                self.assertEqual(fresh[key], committed[key])


class TestJointFit(unittest.TestCase):
    """Fast checks of analyses/joint_fit.py; the full refit runs as a slow claim (joint-fit-reproduces)."""

    def test_reproduces_the_planck_distance_priors_at_planck_parameters(self):
        p = joint_fit.PLANCK2018_TTTEEE_LOWE
        obs = joint_fit.LCDM(p["h"], p["omega_b"], p["omega_c"]).cmb()
        self.assertLess(abs(obs["R"] - 1.7502) / 0.0046, 0.1)
        self.assertLess(abs(obs["l_A"] - 301.471) / 0.0895, 0.5)

    def test_every_reading_reduces_to_lcdm_at_zero_exponent(self):
        data = joint_fit.load_data()
        ref = joint_fit.chi2_total(joint_fit.LCDM(0.68, 0.0224, 0.119), data)
        for name in ("early_transition", "powerlaw", "history_b"):
            with self.subTest(name):
                model = joint_fit.MODELS[name](0.68, 0.0224, 0.119, 0.0)
                self.assertAlmostEqual(joint_fit.chi2_total(model, data), ref, places=9)

    def test_redshift_maps_invert(self):
        for name in ("early_transition", "powerlaw"):
            model = joint_fit.MODELS[name](0.68, 0.0224, 0.119, 8.65e-4)
            for z in (0.5, 5.0, 20.0, 1100.0, 1.0e6):
                self.assertAlmostEqual(model.zobs(model.zE(z)), z, delta=1e-9 * (1.0 + z))

    def test_p1_tuned_variant_shifts_the_ruler_at_fixed_parameters(self):
        base = joint_fit.LCDM(0.6852, 0.02255, 0.1175)
        variant = joint_fit.EarlyTransition(0.6852, 0.02255, 0.1175, joint_fit.q_tuned_to_p1())
        shift = 100.0 * ((variant.dm(0.934) / variant.r_d()) / (base.dm(0.934) / base.r_d()) - 1.0)
        self.assertAlmostEqual(shift, -0.42, delta=0.01)

    def test_committed_report_is_the_rendering_of_the_committed_numbers(self):
        committed = json.loads((ROOT / "analyses" / "joint_fit.json").read_text(encoding="utf-8"))
        self.assertEqual((ROOT / "analyses" / "joint_fit.md").read_text(encoding="utf-8"),
                         joint_fit.render_markdown(committed))


class TestTimescapeFit(unittest.TestCase):
    """The timescape implementation reproduces Wiltshire (2009), and the DESI result reproduces."""

    def test_reproduces_the_published_model(self):
        v = timescape_fit.validate()
        self.assertAlmostEqual(v["drift_z4_10yr"]["this_code"], -3.3e-10, delta=0.05e-10)
        self.assertAlmostEqual(v["Om0_at_f_0.774"]["numerical_from_H"], 0.638, delta=0.001)
        self.assertAlmostEqual(v["distance_closed_form_vs_integral_z1"]["closed_form"],
                               v["distance_closed_form_vs_integral_z1"]["integral"], places=9)
        self.assertAlmostEqual(v["lapse_consistency_z1"]["from_eq72"], v["lapse_consistency_z1"]["eq77_with_b_eq38"],
                               places=12)

    def test_lcdm_branch_matches_desi_published_fit(self):
        res = json.loads((ROOT / "analyses" / "timescape_fit.json").read_text(encoding="utf-8"))
        omega_m, sigma = res["desi_published_lcdm_bao_only_Omega_m"]
        self.assertLess(abs(res["fits"]["lcdm_bao"]["best"] - omega_m), sigma)

    def test_analysis_reproduces_its_committed_output(self):
        proc = subprocess.run([sys.executable, str(ROOT / "analyses" / "timescape_fit.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)


class TestCCBHFit(unittest.TestCase):
    """Fast checks of analyses/ccbh_fit.py; the full refit runs as a slow claim (ccbh-fit-reproduces)."""

    def test_model_bookkeeping(self):
        v = ccbh_fit.validate()
        self.assertAlmostEqual(v["closure_H0_today"], 0.0, places=12)
        self.assertAlmostEqual(v["no_dark_energy_before_star_formation"], 0.0, places=9)
        self.assertGreater(v["dark_energy_density_today_over_baryon_loss_comoving"], 1.0)
        self.assertLess(v["w_eff_during_production_z3"], -1.0)
        self.assertLess(abs(v["step_convergence_H_at_z1"]), 1e-3)

    def test_committed_report_is_the_rendering_of_the_committed_numbers(self):
        committed = json.loads((ROOT / "analyses" / "ccbh_fit.json").read_text(encoding="utf-8"))
        self.assertEqual((ROOT / "analyses" / "ccbh_fit.md").read_text(encoding="utf-8"),
                         ccbh_fit.render_markdown(committed))


if __name__ == "__main__":
    unittest.main()
