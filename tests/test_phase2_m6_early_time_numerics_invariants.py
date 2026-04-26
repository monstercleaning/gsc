import json
import math
import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.numerics_invariants import run_early_time_invariants  # noqa: E402
from gsc.early_time.numerics_invariants import INVARIANTS_SCHEMA_VERSION  # noqa: E402
from gsc.early_time.numerics_invariants import DEFAULT_REQUIRED_CHECK_IDS  # noqa: E402
from gsc.measurement_model import MPC_SI  # noqa: E402


def _assert_json_safe(testcase: unittest.TestCase, payload: dict) -> None:
    text = json.dumps(payload, allow_nan=False)
    testcase.assertIsInstance(text, str)


def _good_predicted() -> dict[str, float]:
    theta_star = 0.010409
    rd_mpc = 147.0
    return {
        "theta_star": theta_star,
        "100theta_star": 100.0 * theta_star,
        "lA": math.pi / theta_star,
        "R": 1.75,
        "rd_Mpc": rd_mpc,
        "rd_m": rd_mpc * float(MPC_SI),
    }


class TestPhase2M6EarlyTimeNumericsInvariants(unittest.TestCase):
    def test_happy_path_passes(self):
        report = run_early_time_invariants(_good_predicted())
        _assert_json_safe(self, report)
        self.assertTrue(bool(report.get("ok")), msg=report)
        self.assertEqual(int(report.get("schema_version", -1)), int(INVARIANTS_SCHEMA_VERSION))
        self.assertIs(report.get("strict"), True)
        self.assertEqual(
            set(str(x) for x in report.get("required_check_ids", [])),
            set(str(x) for x in DEFAULT_REQUIRED_CHECK_IDS),
        )
        self.assertEqual(report.get("violations"), [])

    def test_alias_mismatch_fails(self):
        pred = _good_predicted()
        pred["100theta_star"] = 2.0
        report = run_early_time_invariants(pred)
        _assert_json_safe(self, report)
        self.assertFalse(bool(report.get("ok")), msg=report)
        violations = [str(v) for v in report.get("violations", [])]
        self.assertTrue(any("alias mismatch" in v for v in violations), msg=violations)

    def test_identity_lA_mismatch_fails(self):
        pred = _good_predicted()
        pred["lA"] = pred["lA"] * 1.02
        report = run_early_time_invariants(pred)
        _assert_json_safe(self, report)
        self.assertFalse(bool(report.get("ok")), msg=report)
        violations = [str(v) for v in report.get("violations", [])]
        self.assertTrue(any("lA=" in v or "pi/theta_star" in v for v in violations), msg=violations)

    def test_identity_rd_units_mismatch_fails(self):
        pred = _good_predicted()
        pred["rd_m"] = pred["rd_Mpc"]  # wrong units by construction
        report = run_early_time_invariants(pred)
        _assert_json_safe(self, report)
        self.assertFalse(bool(report.get("ok")), msg=report)
        violations = [str(v) for v in report.get("violations", [])]
        self.assertTrue(any("rd_Mpc*MPC_SI" in v for v in violations), msg=violations)

    def test_non_finite_fails_and_is_json_safe(self):
        pred = _good_predicted()
        pred["theta_star"] = float("nan")
        report = run_early_time_invariants(pred)
        _assert_json_safe(self, report)
        self.assertFalse(bool(report.get("ok")), msg=report)
        violations = [str(v).lower() for v in report.get("violations", [])]
        self.assertTrue(any("not finite" in v for v in violations), msg=violations)

    def test_missing_optional_keys_do_not_hard_fail_in_lenient_mode(self):
        pred = {"theta_star": 0.01}
        report = run_early_time_invariants(pred, strict=False)
        _assert_json_safe(self, report)
        self.assertTrue(bool(report.get("ok")), msg=report)
        self.assertEqual(report.get("violations"), [])

    def test_missing_required_keys_fail_in_strict_mode(self):
        pred = {"theta_star": 0.01}
        report = run_early_time_invariants(pred, strict=True)
        _assert_json_safe(self, report)
        self.assertFalse(bool(report.get("ok")), msg=report)
        missing_required = [str(x) for x in report.get("missing_required", [])]
        self.assertTrue(any("finite_positive_core" in x for x in missing_required), msg=missing_required)

    def test_report_is_deterministic_for_same_input(self):
        pred = _good_predicted()
        first = run_early_time_invariants(pred)
        second = run_early_time_invariants(pred)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
