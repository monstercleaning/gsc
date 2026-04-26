import json
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time.numerics_invariants import (  # noqa: E402
    CHECK_ID_ALIAS_THETA_100,
    CHECK_ID_FINITE_POSITIVE_CORE,
    CHECK_ID_IDENTITY_LA,
    CHECK_ID_IDENTITY_RD_UNITS,
    DEFAULT_REQUIRED_CHECK_IDS,
    INVARIANTS_SCHEMA_VERSION,
    run_early_time_invariants,
)
from gsc.measurement_model import MPC_SI  # noqa: E402


def _baseline_predicted() -> dict[str, float]:
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


class TestPhase2M8InvariantsRegressionGuards(unittest.TestCase):
    def test_strict_report_has_frozen_schema_and_required_ids(self):
        report = run_early_time_invariants(_baseline_predicted(), strict=True)
        self.assertEqual(int(report.get("schema_version", -1)), int(INVARIANTS_SCHEMA_VERSION))
        self.assertIs(report.get("strict"), True)
        self.assertEqual(
            set(str(x) for x in report.get("required_check_ids", [])),
            set(str(x) for x in DEFAULT_REQUIRED_CHECK_IDS),
        )
        checks = report.get("checks")
        self.assertIsInstance(checks, dict)
        for check_id in DEFAULT_REQUIRED_CHECK_IDS:
            self.assertIn(check_id, checks)
            self.assertTrue(bool(checks[check_id].get("ok")), msg=checks[check_id])
            self.assertEqual(str(checks[check_id].get("status", "")).upper(), "PASS")

    def test_strict_mode_fails_when_required_keys_are_missing(self):
        report = run_early_time_invariants({"theta_star": 0.010409}, strict=True)
        self.assertFalse(bool(report.get("ok")), msg=report)
        missing = [str(x) for x in report.get("missing_required", [])]
        self.assertIn(CHECK_ID_FINITE_POSITIVE_CORE, missing)
        self.assertIn(CHECK_ID_IDENTITY_LA, missing)
        self.assertIn(CHECK_ID_IDENTITY_RD_UNITS, missing)

    def test_lenient_mode_keeps_skip_as_non_fatal(self):
        report = run_early_time_invariants({"theta_star": 0.010409}, strict=False)
        self.assertTrue(bool(report.get("ok")), msg=report)
        checks = report.get("checks") or {}
        self.assertEqual(str((checks.get(CHECK_ID_ALIAS_THETA_100) or {}).get("status", "")).upper(), "PASS")
        self.assertEqual(str((checks.get(CHECK_ID_IDENTITY_LA) or {}).get("status", "")).upper(), "SKIP")
        self.assertEqual(str((checks.get(CHECK_ID_IDENTITY_RD_UNITS) or {}).get("status", "")).upper(), "SKIP")

    def test_json_safe_contract_even_with_non_finite_values(self):
        pred = _baseline_predicted()
        pred["theta_star"] = float("nan")
        report = run_early_time_invariants(pred, strict=True)
        self.assertFalse(bool(report.get("ok")), msg=report)
        text = json.dumps(report, allow_nan=False)
        self.assertIsInstance(text, str)

    def test_unknown_required_check_fails_in_strict_mode(self):
        report = run_early_time_invariants(
            _baseline_predicted(),
            strict=True,
            required_check_ids=list(DEFAULT_REQUIRED_CHECK_IDS) + ["unknown_check_id"],
        )
        self.assertFalse(bool(report.get("ok")), msg=report)
        errors = [str(x) for x in report.get("errors", [])]
        self.assertTrue(any("unknown required check ids" in x for x in errors), msg=errors)


if __name__ == "__main__":
    unittest.main()
