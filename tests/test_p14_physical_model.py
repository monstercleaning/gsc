"""Physics and reproducibility tests for the P14 nucleosynthesis diagnostic."""
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyses"))
import p14_physical_model as model
import p14_network as bbn
import p14_bbn_status as status


class TestP14PhysicalModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(model.OUTPUT.read_text())

    def test_reproduce_validated_network_and_rendering(self):
        subprocess.run([sys.executable, str(model.OUTPUT.with_suffix(".py")), "--check"], check=True)

    def test_absolute_abundances_and_constant_G_response(self):
        validation = self.report["validation"]
        for el, code, scale, tolerance in (("Y_p", status.PRIMAT, 1, .01), ("D/H", status.GP, 1e-5, .05)):
            with self.subTest(element=el):
                run = validation["elements"][el]
                ref = status.standard(code, el, "as published")[0] * scale
                self.assertLess(abs(run["standard"] / ref - 1), tolerance)
                self.assertLess(abs(run["G_slope"] / status.SENS[el]["G"] - 1), .10)
        self.assertLess(validation["physical_baryon_residual"], 1e-11)
        self.assertLess(max(map(abs, validation["step_halving_relative_change_in_ratio"].values())), 1e-4)

    def test_thermal_weak_rates(self):
        for t in (.1, 1., 10.):
            forward, reverse = bbn.weak_integrals(t, t)
            self.assertAlmostEqual(reverse / forward, math.exp(-bbn.DELTA / t), places=11)
        forward, _ = bbn.weak_integrals(.0001, .0001)
        self.assertAlmostEqual(forward / bbn.vacuum_integral(), 1., places=7)
        self.assertAlmostEqual(bbn.plasma(.001).tnu / .001, (4/11)**(1/3), places=10)

    def test_transition_conservation_and_registered_frame(self):
        q, zt = self.report["q"], self.report["z_transition"]
        epochs = json.loads(status.P14_OUTPUT.read_text())["prediction"]["epochs"]
        for epoch in epochs:
            # Atomic temperature at a specified observed redshift, including pair entropy.
            z = epoch["z_obs"]
            lo, hi = model.T0, 10.
            for _ in range(75):
                mid = (lo + hi) / 2
                if model.thermal(mid).log_a > -math.log1p(z):
                    lo = mid
                else:
                    hi = mid
            A = model.matter(mid, q, -math.log1p(zt)).A
            self.assertAlmostEqual(A**2, epoch["G_over_G0"], delta=5e-7)
        temp = model.T0 * (1 + zt)
        bg, residual = model.history([temp * .99, temp, temp * 1.01, .1], q, zt)
        self.assertEqual(bg[temp * .99][2], 1.)
        self.assertLess(bg[temp * 1.01][2], 1.)
        self.assertLess(residual["adjacent_to_transition"], 1e-8)
        self.assertLess(self.report["conservation"]["max_cell"], 1e-7)
        null, _ = model.history([.1, 1.], 0., zt)
        self.assertAlmostEqual(null[.1][0] / null[.1][1], 1., places=12)

    def test_proxy_likelihood_and_conditional_interval(self):
        old = next(row for row in status.analyse()["combined"] if row["prediction"] == status.GP
                   and row["baryon_density"] == "as published" and row["deuterium"] == status.PRIMARY_DEUTERIUM)
        row = self.report["comparisons"][0]["cases"]["(1+q)^2 G/G0"]
        self.assertAlmostEqual(row["likelihood_standard_over_model"], old["likelihood_standard_over_p14"], places=7)
        for delta in self.report["validation"]["direct_delta_chi2_at_GP_limits"]:
            self.assertAlmostEqual(delta, 4, places=5)
