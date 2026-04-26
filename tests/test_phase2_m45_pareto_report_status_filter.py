import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _ok_row() -> dict:
    return {
        "status": "ok",
        "model": "lcdm",
        "params_hash": "hash_ok",
        "params": {"H0": 67.4, "Omega_m": 0.315},
        "chi2_total": 5.2,
        "chi2_parts": {
            "cmb": {"chi2": 4.9},
            "drift": {"min_zdot_si": 0.15, "sign_ok": True},
            "invariants": {"ok": True},
        },
        "drift": {"min_z_dot": 0.15, "all_positive": True},
        "invariants_ok": True,
    }


def _skipped_row() -> dict:
    return {
        "status": "skipped_drift",
        "model": "lcdm",
        "params_hash": "hash_skip",
        "params": {"H0": 68.1, "Omega_m": 0.290},
        "drift_precheck_spec": "z2_5_positive",
        "drift_precheck_ok": False,
        "skip_reason": "drift_precheck_failed",
        "drift": {"min_z_dot": -0.10, "all_positive": False},
    }


def _error_row() -> dict:
    return {
        "status": "error",
        "model": "lcdm",
        "params_hash": "hash_err",
        "params": {"H0": 66.5, "Omega_m": 0.340},
        "error": {"type": "ValueError", "message": "boom"},
    }


def _seed_params_hash(params: dict) -> str:
    canonical = json.dumps({k: float(v) for k, v in sorted(params.items())}, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TestPhase2M45ParetoReportStatusFilter(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_default_ok_only_ignores_skipped_and_error_and_refine_plan_uses_ok(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"
            refine_plan = td_path / "refine_plan.json"

            rows = [_ok_row(), _skipped_row(), _error_row()]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
                "--emit-refine-plan",
                str(refine_plan),
                "--refine-top-k",
                "1",
                "--refine-n-per-seed",
                "1",
            ]
            proc = self._run(cmd)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertIn("skipped_drift=", output)
            self.assertIn("incomplete_missing_metrics=", output)

            top_csv = out_dir / "pareto_top_positive.csv"
            self.assertTrue(top_csv.is_file())
            with top_csv.open("r", encoding="utf-8", newline="") as fh:
                rows_csv = list(csv.DictReader(fh))
            self.assertEqual(len(rows_csv), 1)
            self.assertEqual(rows_csv[0].get("params_hash"), "hash_ok")

            payload = json.loads(refine_plan.read_text(encoding="utf-8"))
            points = payload.get("points") or []
            self.assertGreaterEqual(len(points), 1)
            expected_seed_hash = _seed_params_hash({"H0": 67.4, "Omega_m": 0.315})
            for point in points:
                self.assertEqual(point.get("seed_params_hash"), expected_seed_hash)

    def test_any_eligible_still_excludes_incomplete_rows(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"
            rows = [_ok_row(), _skipped_row(), _error_row()]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
                "--status-filter",
                "any_eligible",
            ]
            proc = self._run(cmd)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            top_csv = out_dir / "pareto_top_positive.csv"
            self.assertTrue(top_csv.is_file())
            with top_csv.open("r", encoding="utf-8", newline="") as fh:
                rows_csv = list(csv.DictReader(fh))
            self.assertEqual(len(rows_csv), 1)
            self.assertEqual(rows_csv[0].get("params_hash"), "hash_ok")


if __name__ == "__main__":
    unittest.main()
