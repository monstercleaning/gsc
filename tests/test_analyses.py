"""Diagnostic analyses are deterministic and reproduce their committed outputs."""

import json
import math
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
import a0_evolution  # noqa: E402
import a0_high_z  # noqa: E402
import emergent_gravity  # noqa: E402


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


class TestA0Evolution(unittest.TestCase):
    """Fast checks of analyses/a0_evolution.py; the full fit runs as a slow claim (a0-evolution-reproduces)."""

    @classmethod
    def setUpClass(cls):
        cls.galaxies = a0_evolution.load_galaxies()

    def test_transcribed_table_reproduces_the_papers_statistics(self):
        s = a0_evolution.paper_statistics(self.galaxies)
        self.assertEqual(s["n_galaxies"], 100)
        self.assertTrue(s["ids_in_order_and_redshift_sorted"])
        for key in ("median_fdm_z_0.6_1.2", "median_fdm_z_1.2_2.5", "spread_fdm_z_0.6_1.2", "spread_fdm_z_1.2_2.5"):
            with self.subTest(statistic=key):
                self.assertEqual(round(s[key]["table"], 2), s[key]["paper"])
        self.assertAlmostEqual(s["share_below_maximal_disk_z_0.6_1.2"]["table"], 0.33, delta=0.01)
        self.assertAlmostEqual(s["share_below_maximal_disk_z_1.2_2.5"]["table"], 0.5, delta=0.05)
        self.assertAlmostEqual(s["median_Re_kpc"]["table"], 5.5, delta=0.06)
        self.assertEqual(s["mass_consistency_Vbar2_Re_over_G_Mbar"]["outside_0.15_to_1.2"], [83])

    def test_relation_inverts_and_noise_free_mocks_are_recovered(self):
        v = a0_evolution.validate(self.galaxies)
        for row in v["inversion"]:
            self.assertLess(abs(row["relative_error_closed_form"]), 1e-12)
            self.assertLess(abs(row["relative_error_bisection"]), 1e-12)
        for name, p_true in (("p_true_0", 0.0), ("p_true_1", 1.0)):
            with self.subTest(mock=name):
                self.assertAlmostEqual(v["noise_free_mock_recovery"][name]["p_recovered"], p_true, delta=1e-4)
                self.assertAlmostEqual(v["noise_free_mock_recovery"][name]["A_recovered"], a0_evolution.A0_LOCAL,
                                       delta=1e-4)

    def test_dark_energy_density_matches_the_equation_of_state(self):
        # d ln rho / d ln a = -3 (1 + w(a)), w(a) = w0 + wa (1 - a), integrated numerically from a = 1.
        for w0, wa in a0_evolution.DESI_DR2_W0WA.values():
            for z in (0.5, 2.22, 5.0):
                n, lna_end = 4000, -math.log(1.0 + z)
                h = lna_end / n
                f = lambda x: -3.0 * (1.0 + w0 + wa * (1.0 - math.exp(x)))  # noqa: E731
                ln_rho = h / 3.0 * sum((1 if i in (0, n) else 4 if i % 2 else 2) * f(i * h) for i in range(n + 1))
                self.assertAlmostEqual(a0_evolution.rho_de_ratio(z, w0, wa), math.exp(ln_rho), places=9)
        self.assertEqual(a0_evolution.rho_de_ratio(3.0, -1.0, 0.0), 1.0)

    def test_committed_report_is_the_rendering_of_the_committed_numbers(self):
        committed = json.loads((ROOT / "analyses" / "a0_evolution.json").read_text(encoding="utf-8"))
        self.assertEqual((ROOT / "analyses" / "a0_evolution.md").read_text(encoding="utf-8"),
                         a0_evolution.render_markdown(committed))


class TestA0HighZ(unittest.TestCase):
    """The z ~ 4.5 check: special functions, component speeds, and the committed output."""

    def test_special_functions_and_components(self):
        v = a0_high_z.validate()
        self.assertLess(abs(v["gammainc_P1_x2_vs_closed_form"]), 1e-13)
        self.assertLess(abs(v["gammainc_P3_x10_vs_closed_form"]), 1e-13)
        for d in v["bessel_at_1_vs_tables"]:
            self.assertLess(abs(d), 1e-6)
        self.assertAlmostEqual(v["exponential_disc_peak"]["radius_over_rd"], 2.15, delta=0.03)
        self.assertAlmostEqual(v["exponential_disc_peak"]["v2_over_GM_rd"], 0.387, delta=0.002)
        self.assertAlmostEqual(v["sersic_encloses_total_mass"], 1.0, places=6)

    def test_analysis_reproduces_its_committed_output(self):
        proc = subprocess.run([sys.executable, str(ROOT / "analyses" / "a0_high_z.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)


class TestEmergentGravity(unittest.TestCase):
    """Verlinde's formula on RC100: the mass-distribution factor, the scale, and the committed output."""

    def test_mass_distribution_factor_and_scale(self):
        v = emergent_gravity.validate(emergent_gravity.load_galaxies())
        self.assertAlmostEqual(v["k_point_mass_bulge_far_out"], 1.0, delta=0.01)
        self.assertAlmostEqual(v["k_exponential_disc_at_R_e"], 2.30, delta=0.01)
        self.assertAlmostEqual(v["a_M_planck_today"], 1.0914, delta=1e-3)
        self.assertEqual(emergent_gravity.nu_verlinde(4.0, 1.0), 1.5)

    def test_analysis_reproduces_its_committed_output(self):
        proc = subprocess.run([sys.executable, str(ROOT / "analyses" / "emergent_gravity.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
