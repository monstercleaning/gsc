import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_drift_table_report.py"


class TestPhase2M68E2DriftTableReportToy(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, shard_a: Path, shard_b: Path) -> None:
        rows_a = [
            {
                "params_hash": "cand_a",
                "plan_point_id": "p1",
                "status": "ok",
                "chi2_total": 12.0,
                "microphysics_plausible_ok": True,
                "drift": {
                    "z": [2.0, 3.0, 4.0, 5.0],
                    "dv_cm_s_per_yr": [0.010, 0.020, 0.030, 0.040],
                    "z_dot": [1.0e-10, 2.0e-10, 3.0e-10, 4.0e-10],
                },
            },
            {
                "params_hash": "cand_b",
                "plan_point_id": "p2",
                "status": "ok",
                "chi2_total": 8.0,
                "microphysics_plausible_ok": False,
                "drift": {
                    "z": [2.0, 3.0, 4.0, 5.0],
                    "dv_cm_s_per_yr": [0.050, 0.060, 0.070, 0.080],
                    "z_dot": [5.0e-10, 6.0e-10, 7.0e-10, 8.0e-10],
                },
            },
            {
                "params_hash": "cand_err",
                "status": "error",
                "chi2_total": 1.5,
                "error": "ValueError: synthetic",
                "drift": {
                    "z": [2.0, 3.0, 4.0, 5.0],
                    "dv_cm_s_per_yr": [0.090, 0.090, 0.090, 0.090],
                },
            },
        ]
        rows_b = [
            {
                "params_hash": "cand_skip",
                "status": "skipped_drift",
                "chi2_total": 1.0e99,
                "drift": {
                    "z": [2.0, 3.0, 4.0, 5.0],
                    "dv_cm_s_per_yr": [0.0, 0.0, 0.0, 0.0],
                },
            },
            {
                "plan_point_id": "p3",
                "chi2_total": 9.0,
                "microphysics_plausible_ok": True,
                "drift": {
                    "z": [2.0, 3.0, 4.0, 5.0],
                    "dv_cm_s_per_yr": [0.011, 0.021, 0.031, 0.041],
                },
            },
        ]

        with shard_a.open("w", encoding="utf-8") as fh:
            for row in rows_a:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.write("{bad json\n")
            fh.write("\n")

        with shard_b.open("w", encoding="utf-8") as fh:
            for row in rows_b:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_json_output_selection_counts_and_determinism(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a = td_path / "shard_a.jsonl"
            shard_b = td_path / "shard_b.jsonl"
            self._write_fixture(shard_a, shard_b)

            proc = self._run(
                "--input",
                str(shard_a),
                "--input",
                str(shard_b),
                "--format",
                "json",
                "--years",
                "10",
                "--z",
                "2,3,4,5",
                "--eligible-status",
                "ok_only",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(proc.stdout)

            self.assertEqual(payload.get("schema"), "phase2_e2_drift_table_report_v1")
            header = payload.get("header") or {}
            self.assertEqual(int(header.get("n_records_parsed", -1)), 5)
            self.assertEqual(int(header.get("n_invalid_lines", -1)), 1)

            status_counts = payload.get("status_counts") or {}
            self.assertEqual(int(status_counts.get("ok", 0)), 2)
            self.assertEqual(int(status_counts.get("error", 0)), 1)
            self.assertEqual(int(status_counts.get("skipped_drift", 0)), 1)
            self.assertEqual(int(status_counts.get("unknown", 0)), 1)

            best_overall = payload.get("best_eligible_overall") or {}
            best_plausible = payload.get("best_eligible_plausible") or {}
            self.assertEqual(best_overall.get("params_hash"), "cand_b")
            self.assertEqual(best_plausible.get("params_hash"), "cand_a")

            table = payload.get("drift_table") or []
            z3 = [row for row in table if abs(float(row.get("z", -1.0)) - 3.0) < 1e-9]
            self.assertEqual(len(z3), 1)
            row_z3 = z3[0]
            self.assertAlmostEqual(float(row_z3.get("dv_best_cm_s")), 0.6, places=12)
            self.assertAlmostEqual(float(row_z3.get("dv_best_plausible_cm_s")), 0.2, places=12)
            self.assertIsInstance(float(row_z3.get("dv_lcdm_cm_s")), float)

            proc_repeat = self._run(
                "--input",
                str(shard_a),
                "--input",
                str(shard_b),
                "--format",
                "json",
                "--years",
                "10",
                "--z",
                "2,3,4,5",
                "--eligible-status",
                "ok_only",
            )
            self.assertEqual(proc_repeat.returncode, 0, msg=(proc_repeat.stdout or "") + (proc_repeat.stderr or ""))
            self.assertEqual(proc.stdout, proc_repeat.stdout)

    def test_missing_drift_metrics_is_graceful(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard = td_path / "scan.jsonl"
            rows = [
                {
                    "params_hash": "m0",
                    "status": "ok",
                    "chi2_total": 7.0,
                    "microphysics_plausible_ok": True,
                }
            ]
            with shard.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")

            proc = self._run("--input", str(shard), "--format", "json")
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            payload = json.loads(proc.stdout)
            self.assertFalse(bool(payload.get("candidate_drift_available_overall")))
            self.assertFalse(bool(payload.get("candidate_drift_available_plausible")))
            for row in payload.get("drift_table") or []:
                self.assertIsNone(row.get("dv_best_cm_s"))
                self.assertIsNone(row.get("dv_best_plausible_cm_s"))

    def test_missing_input_returns_exit_1(self) -> None:
        proc = self._run("--input", "/does/not/exist.jsonl", "--format", "json")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
