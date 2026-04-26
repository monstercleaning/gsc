import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M59E2RequeuePlan(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m59_plan_source"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.1, "Omega_m": 0.305}},
                {"point_id": "p2", "params": {"H0": 67.4, "Omega_m": 0.310}},
                {"point_id": "p3", "params": {"H0": 67.7, "Omega_m": 0.315}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_shards(self, dir_path: Path) -> None:
        shard1 = dir_path / "shard1.jsonl"
        shard2 = dir_path / "shard2.jsonl"
        shard1.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "plan_point_id": "p0",
                            "status": "ok",
                            "params": {"H0": 66.8, "Omega_m": 0.300},
                            "chi2_total": 3.0,
                        },
                        sort_keys=True,
                    ),
                    json.dumps(
                        {
                            "plan_point_id": "p1",
                            "status": "error",
                            "params": {"H0": 67.1, "Omega_m": 0.305},
                            "error": "ValueError: boom",
                        },
                        sort_keys=True,
                    ),
                    "{invalid_json",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        shard2.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "plan_point_id": "p2",
                            "status": "skipped_drift_precheck",
                            "params": {"H0": 67.4, "Omega_m": 0.310},
                        },
                        sort_keys=True,
                    ),
                    json.dumps(
                        {
                            "plan_point_id": "p3",
                            "params": {"H0": 67.7, "Omega_m": 0.315},
                            "chi2_total": 8.0,
                        },
                        sort_keys=True,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _run_tool(self, args: list[str]) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_requeue_plan.py"
        cmd = [sys.executable, str(script)] + list(args)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_requeue_classification_and_selection_modes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            shards = td_path / "shards"
            shards.mkdir(parents=True, exist_ok=True)
            self._write_plan(plan)
            self._write_shards(shards)

            out_unresolved = td_path / "plan_requeue_unresolved.json"
            proc = self._run_tool(
                [
                    "--plan",
                    str(plan),
                    "--input",
                    str(shards),
                    "--select",
                    "unresolved",
                    "--output-plan",
                    str(out_unresolved),
                    "--format",
                    "json",
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            summary = json.loads(proc.stdout)

            self.assertEqual(summary.get("schema"), "phase2_e2_requeue_plan_v1")
            self.assertEqual(int(summary.get("plan_points_total", 0)), 4)
            self.assertEqual(int(summary.get("seen_any", 0)), 4)
            self.assertEqual(int(summary.get("seen_final", 0)), 2)
            self.assertEqual(int(summary.get("missing", 0)), 0)
            self.assertEqual(int(summary.get("unresolved", 0)), 2)
            self.assertEqual(int(summary.get("errors_only", 0)), 1)
            self.assertEqual(int(summary.get("n_invalid_lines", 0)), 1)
            self.assertEqual(summary.get("selected_plan_point_ids"), ["p1", "p3"])

            requeue_plan_unresolved = json.loads(out_unresolved.read_text(encoding="utf-8"))
            unresolved_ids = [p.get("point_id") for p in requeue_plan_unresolved.get("points", [])]
            self.assertEqual(unresolved_ids, ["p1", "p3"])

            out_errors = td_path / "plan_requeue_errors.json"
            proc_errors = self._run_tool(
                [
                    "--plan",
                    str(plan),
                    "--input",
                    str(shards),
                    "--select",
                    "errors",
                    "--output-plan",
                    str(out_errors),
                    "--format",
                    "json",
                ]
            )
            output_errors = (proc_errors.stdout or "") + (proc_errors.stderr or "")
            self.assertEqual(proc_errors.returncode, 0, msg=output_errors)
            summary_errors = json.loads(proc_errors.stdout)
            self.assertEqual(summary_errors.get("selected_plan_point_ids"), ["p1"])

            requeue_plan_errors = json.loads(out_errors.read_text(encoding="utf-8"))
            error_ids = [p.get("point_id") for p in requeue_plan_errors.get("points", [])]
            self.assertEqual(error_ids, ["p1"])


if __name__ == "__main__":
    unittest.main()
