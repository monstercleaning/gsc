import math
import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.cmb_microphysics_knobs import (  # noqa: E402
    MicrophysicsKnobs,
    assess_knobs,
    validate_knobs,
)


class TestPhase2M24MicrophysicsPlausibilityContract(unittest.TestCase):
    def test_assess_defaults_is_clean(self):
        knobs = MicrophysicsKnobs()
        report = assess_knobs(knobs)
        self.assertTrue(bool(report["hard_ok"]))
        self.assertTrue(bool(report["plausible_ok"]))
        self.assertEqual(float(report["penalty"]), 0.0)
        self.assertEqual(float(report["max_rel_dev"]), 0.0)
        self.assertEqual(list(report["notes"]), [])

    def test_assess_outside_plausible_inside_hard_has_penalty(self):
        report = assess_knobs({"z_star_scale": 1.06})
        self.assertTrue(bool(report["hard_ok"]))
        self.assertFalse(bool(report["plausible_ok"]))
        self.assertGreater(float(report["penalty"]), 0.0)
        self.assertGreater(float(report["max_rel_dev"]), 0.0)
        notes = [str(v) for v in report.get("notes", [])]
        self.assertTrue(any("z_star_scale" in n for n in notes))

    def test_validate_outside_hard_raises(self):
        with self.assertRaises(ValueError):
            validate_knobs({"r_s_scale": 1.25})

    def test_assess_report_is_finite_json_safe_scalars(self):
        report = assess_knobs({"r_d_scale": 0.94})
        self.assertTrue(math.isfinite(float(report["penalty"])))
        self.assertTrue(math.isfinite(float(report["max_rel_dev"])))


if __name__ == "__main__":
    unittest.main()
