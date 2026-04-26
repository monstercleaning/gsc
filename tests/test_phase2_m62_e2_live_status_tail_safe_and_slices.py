import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M62E2LiveStatusTailSafeAndSlices(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m62_plan_sha"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.1, "Omega_m": 0.305}},
                {"point_id": "p2", "params": {"H0": 67.4, "Omega_m": 0.310}},
                {"point_id": "p3", "params": {"H0": 67.7, "Omega_m": 0.315}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_inputs(self, input_dir: Path) -> tuple[Path, Path]:
        shard_a = input_dir / "shard_a.jsonl"
        shard_b = input_dir / "shard_b.jsonl"

        a_lines = [
            json.dumps(
                {
                    "status": "ok",
                    "plan_point_id": "p0",
                    "plan_slice_i": 0,
                    "plan_slice_n": 2,
                    "params": {"H0": 66.8, "Omega_m": 0.300},
                    "chi2_total": 5.0,
                    "microphysics_plausible_ok": True,
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "status": "error",
                    "plan_point_id": "p2",
                    "plan_slice_i": 0,
                    "plan_slice_n": 2,
                    "params": {"H0": 67.4, "Omega_m": 0.310},
                    "error": {"type": "RuntimeError", "message": "boom"},
                },
                sort_keys=True,
            ),
        ]
        # No trailing newline; last partial line simulates active writer tail.
        shard_a.write_text("\n".join(a_lines) + "\n" + '{"status":"ok","plan_point_id":"pX"', encoding="utf-8")

        b_lines = [
            json.dumps(
                {
                    "status": "ok",
                    "plan_point_id": "p1",
                    "plan_slice_i": 1,
                    "plan_slice_n": 2,
                    "params": {"H0": 67.1, "Omega_m": 0.305},
                    "chi2_total": 2.0,
                    "microphysics_plausible_ok": False,
                },
                sort_keys=True,
            ),
            "{invalid_json",
            "",
            json.dumps(
                {
                    "status": "skipped_drift",
                    "plan_point_id": "p_extra",
                    "plan_slice_i": 1,
                    "plan_slice_n": 2,
                    "params": {"H0": 67.3, "Omega_m": 0.308},
                    "chi2_total": 1.0e99,
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "plan_point_id": "p_extra2",
                    "plan_slice_i": 1,
                    "plan_slice_n": 2,
                    "params": {"H0": 67.5, "Omega_m": 0.312},
                    "chi2_total": 4.0,
                },
                sort_keys=True,
            ),
        ]
        shard_b.write_text("\n".join(b_lines) + "\n", encoding="utf-8")
        return shard_a, shard_b

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_live_status.py"
        cmd = [sys.executable, str(script)] + list(args)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_tail_safe_and_slice_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_dir = td_path / "inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            self._write_inputs(input_dir)
            plan = td_path / "plan.json"
            self._write_plan(plan)

            proc_default = self._run(
                [
                    "--input",
                    str(input_dir),
                    "--plan",
                    str(plan),
                    "--format",
                    "json",
                ]
            )
            out_default = (proc_default.stdout or "") + (proc_default.stderr or "")
            self.assertEqual(proc_default.returncode, 0, msg=out_default)
            payload_default = json.loads(proc_default.stdout)
            self.assertEqual(int(payload_default.get("n_invalid_lines", 0)), 2)
            self.assertNotIn("n_partial_tail_lines_skipped", payload_default)
            self.assertNotIn("slice_summary", payload_default)

            args_tail = [
                "--input",
                str(input_dir),
                "--plan",
                str(plan),
                "--format",
                "json",
                "--tail-safe",
                "--include-slice-summary",
                "--eligible-status",
                "ok_only",
            ]
            proc_tail_a = self._run(args_tail)
            proc_tail_b = self._run(args_tail)
            out_tail_a = (proc_tail_a.stdout or "") + (proc_tail_a.stderr or "")
            out_tail_b = (proc_tail_b.stdout or "") + (proc_tail_b.stderr or "")
            self.assertEqual(proc_tail_a.returncode, 0, msg=out_tail_a)
            self.assertEqual(proc_tail_b.returncode, 0, msg=out_tail_b)
            self.assertEqual(proc_tail_a.stdout, proc_tail_b.stdout)

            payload = json.loads(proc_tail_a.stdout)
            self.assertEqual(int(payload.get("n_invalid_lines", 0)), 1)
            self.assertEqual(int(payload.get("n_partial_tail_lines_skipped", 0)), 1)
            self.assertEqual(int(payload.get("n_records_total", 0)), 7)
            self.assertEqual(int(payload.get("n_records_parsed", 0)), 5)

            slice_summary = list(payload.get("slice_summary") or [])
            self.assertEqual(len(slice_summary), 2)
            keys = {(int(row["slice_i"]), int(row["slice_n"])) for row in slice_summary}
            self.assertEqual(keys, {(0, 2), (1, 2)})

            by_key = {(int(row["slice_i"]), int(row["slice_n"])): row for row in slice_summary}
            row0 = by_key[(0, 2)]
            row1 = by_key[(1, 2)]
            self.assertEqual(int(row0.get("eligible_count", 0)), 1)
            self.assertEqual(int(row1.get("eligible_count", 0)), 1)
            self.assertAlmostEqual(float(row0.get("best_chi2_total_eligible")), 5.0, places=12)
            self.assertAlmostEqual(float(row1.get("best_chi2_total_eligible")), 2.0, places=12)
            self.assertEqual(int(row0.get("plan_points_total_in_slice", 0)), 2)
            self.assertEqual(int(row1.get("plan_points_total_in_slice", 0)), 2)
            self.assertEqual(int(row1.get("plan_points_seen_any_in_slice", 0)), 1)
            self.assertAlmostEqual(float(row1.get("coverage_any_in_slice")), 0.5, places=12)

            proc_gate = self._run(
                args_tail
                + [
                    "--require-plan-coverage",
                    "complete",
                ]
            )
            out_gate = (proc_gate.stdout or "") + (proc_gate.stderr or "")
            self.assertEqual(proc_gate.returncode, 2, msg=out_gate)


if __name__ == "__main__":
    unittest.main()
