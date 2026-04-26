import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M58E2LiveStatus(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m58_plan_sha"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.1, "Omega_m": 0.305}},
                {"point_id": "p2", "params": {"H0": 67.4, "Omega_m": 0.310}},
                {"point_id": "p3", "params": {"H0": 67.7, "Omega_m": 0.315}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_jsonl_inputs(self, dir_path: Path) -> tuple[Path, Path]:
        plan_source = "m58_plan_sha"
        a = dir_path / "shard_a.jsonl"
        b = dir_path / "shard_b.jsonl"
        a.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "status": "ok",
                            "plan_point_id": "p0",
                            "plan_source_sha256": plan_source,
                            "params": {"H0": 66.8, "Omega_m": 0.300},
                            "chi2_total": 5.0,
                            "microphysics_plausible_ok": True,
                        },
                        sort_keys=True,
                    ),
                    "{invalid_json",
                    json.dumps(
                        {
                            "status": "error",
                            "plan_point_id": "p1",
                            "plan_source_sha256": plan_source,
                            "params": {"H0": 67.1, "Omega_m": 0.305},
                            "error": {"type": "RuntimeError", "message": "boom"},
                        },
                        sort_keys=True,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        b.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "status": "ok",
                            "plan_point_id": "p1",
                            "plan_source_sha256": plan_source,
                            "params": {"H0": 67.1, "Omega_m": 0.305},
                            "chi2_total": 2.0,
                            "microphysics_plausible_ok": False,
                            "drift_precheck_ok": True,
                        },
                        sort_keys=True,
                    ),
                    json.dumps(
                        {
                            "status": "skipped_drift",
                            "plan_point_id": "p2",
                            "plan_source_sha256": plan_source,
                            "params": {"H0": 67.4, "Omega_m": 0.310},
                            "chi2_total": 1.0e99,
                            "microphysics_plausible_ok": False,
                            "drift_precheck_ok": False,
                        },
                        sort_keys=True,
                    ),
                    json.dumps(
                        {
                            "params": {"H0": 67.7, "Omega_m": 0.315},
                            "chi2_total": 3.0,
                            "microphysics_plausible_ok": True,
                        },
                        sort_keys=True,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return a, b

    def _run_tool(self, args: list[str]) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_live_status.py"
        cmd = [sys.executable, str(script)] + list(args)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_json_output_and_coverage_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_dir = td_path / "inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            self._write_jsonl_inputs(input_dir)
            plan = td_path / "plan.json"
            self._write_plan(plan)

            proc = self._run_tool(
                [
                    "--input",
                    str(input_dir),
                    "--plan",
                    str(plan),
                    "--format",
                    "json",
                    "--mode",
                    "summary",
                    "--eligible-status",
                    "ok_only",
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(proc.stdout)

            self.assertEqual(payload.get("schema"), "phase2_e2_live_status_v1")
            self.assertEqual(int(payload.get("n_files_expanded", 0)), 2)
            self.assertEqual(int(payload.get("n_invalid_lines", 0)), 1)
            self.assertEqual(int(payload.get("n_records_total", 0)), 6)
            self.assertEqual(int(payload.get("n_records_parsed", 0)), 5)
            self.assertEqual(payload.get("status_counts", {}).get("ok"), 2)
            self.assertEqual(payload.get("status_counts", {}).get("error"), 1)
            self.assertEqual(payload.get("status_counts", {}).get("skipped_drift"), 1)
            self.assertEqual(payload.get("status_counts", {}).get("unknown"), 1)
            self.assertEqual(payload.get("error_counts", {}).get("RuntimeError"), 1)

            best = payload.get("best", {}).get("overall") or {}
            self.assertEqual(best.get("plan_point_id"), "p1")
            self.assertAlmostEqual(float(best.get("chi2_total")), 2.0, places=9)

            cov = payload.get("plan_coverage") or {}
            self.assertTrue(bool(cov.get("known")))
            self.assertEqual(cov.get("strategy"), "plan_point_id")
            self.assertEqual(int(cov.get("plan_points_total", 0)), 4)
            self.assertEqual(int(cov.get("plan_points_seen_any", 0)), 3)
            self.assertAlmostEqual(float(cov.get("coverage_any")), 0.75, places=12)

            proc_gate = self._run_tool(
                [
                    "--input",
                    str(input_dir),
                    "--plan",
                    str(plan),
                    "--format",
                    "json",
                    "--require-plan-coverage",
                    "complete",
                ]
            )
            out_gate = (proc_gate.stdout or "") + (proc_gate.stderr or "")
            self.assertEqual(proc_gate.returncode, 2, msg=out_gate)

    def test_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_dir = td_path / "inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            self._write_jsonl_inputs(input_dir)
            plan = td_path / "plan.json"
            self._write_plan(plan)

            args = [
                "--input",
                str(input_dir),
                "--plan",
                str(plan),
                "--format",
                "json",
                "--mode",
                "by_file",
                "--eligible-status",
                "any_eligible",
            ]
            proc_a = self._run_tool(args)
            proc_b = self._run_tool(args)
            out_a = (proc_a.stdout or "") + (proc_a.stderr or "")
            out_b = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=out_a)
            self.assertEqual(proc_b.returncode, 0, msg=out_b)
            self.assertEqual(proc_a.stdout, proc_b.stdout)


if __name__ == "__main__":
    unittest.main()
