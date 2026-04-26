import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M39PlanCoverage(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "plan_sha_m39"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.1, "Omega_m": 0.310}},
                {"point_id": "p2", "params": {"H0": 67.4, "Omega_m": 0.320}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_plan_coverage.py"
        cmd = [sys.executable, str(script)] + list(args)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _parse_stdout_json(self, proc: subprocess.CompletedProcess) -> dict:
        text = (proc.stdout or "").strip()
        self.assertTrue(text, msg=(proc.stderr or ""))
        return json.loads(text)

    def test_full_coverage_all_ok(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            jsonl = td_path / "scan.jsonl"
            self._write_plan(plan)
            self._write_jsonl(
                jsonl,
                [
                    {"plan_point_id": "p0", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                    {"plan_point_id": "p1", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                    {"plan_point_id": "p2", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                ],
            )

            proc = self._run(["--plan", str(plan), "--jsonl", str(jsonl)])
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            payload = self._parse_stdout_json(proc)
            self.assertEqual(payload["schema"], "phase2_e2_plan_coverage_v1")
            self.assertEqual(int(payload["counts"]["n_missing"]), 0)
            self.assertEqual(int(payload["counts"]["n_failed"]), 0)

            proc_strict = self._run(["--plan", str(plan), "--jsonl", str(jsonl), "--strict"])
            self.assertEqual(proc_strict.returncode, 0, msg=(proc_strict.stdout or "") + (proc_strict.stderr or ""))

    def test_missing_points_strict_exit_2_and_emit_missing_plan(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            jsonl = td_path / "scan.jsonl"
            missing_plan = td_path / "missing_plan.json"
            self._write_plan(plan)
            self._write_jsonl(
                jsonl,
                [
                    {"plan_point_id": "p0", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                    {"plan_point_id": "p1", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                ],
            )

            proc = self._run(
                [
                    "--plan",
                    str(plan),
                    "--jsonl",
                    str(jsonl),
                    "--emit-missing-plan",
                    str(missing_plan),
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            payload = self._parse_stdout_json(proc)
            self.assertEqual(int(payload["counts"]["n_missing"]), 1)
            self.assertTrue(missing_plan.is_file())
            mp = json.loads(missing_plan.read_text(encoding="utf-8"))
            self.assertEqual(mp.get("plan_version"), "phase2_e2_refine_plan_v1")
            self.assertEqual([p.get("point_id") for p in mp.get("points", [])], ["p2"])

            proc_strict = self._run(["--plan", str(plan), "--jsonl", str(jsonl), "--strict"])
            self.assertEqual(proc_strict.returncode, 2, msg=(proc_strict.stdout or "") + (proc_strict.stderr or ""))

    def test_failed_points_strict_exit_3_and_emit_failed_plan(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            jsonl = td_path / "scan.jsonl"
            failed_plan = td_path / "failed_plan.json"
            self._write_plan(plan)
            self._write_jsonl(
                jsonl,
                [
                    {"plan_point_id": "p0", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                    {"plan_point_id": "p1", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                    {"plan_point_id": "p2", "plan_source_sha256": "plan_sha_m39", "status": "error"},
                ],
            )

            proc = self._run(
                [
                    "--plan",
                    str(plan),
                    "--jsonl",
                    str(jsonl),
                    "--emit-failed-plan",
                    str(failed_plan),
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            payload = self._parse_stdout_json(proc)
            self.assertEqual(int(payload["counts"]["n_missing"]), 0)
            self.assertEqual(int(payload["counts"]["n_failed"]), 1)
            self.assertTrue(failed_plan.is_file())
            fp = json.loads(failed_plan.read_text(encoding="utf-8"))
            self.assertEqual([p.get("point_id") for p in fp.get("points", [])], ["p2"])

            proc_strict = self._run(["--plan", str(plan), "--jsonl", str(jsonl), "--strict"])
            self.assertEqual(proc_strict.returncode, 3, msg=(proc_strict.stdout or "") + (proc_strict.stderr or ""))

    def test_foreign_and_unmapped_records_accounted(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            jsonl = td_path / "scan.jsonl"
            self._write_plan(plan)
            self._write_jsonl(
                jsonl,
                [
                    {"plan_point_id": "p0", "plan_source_sha256": "WRONG_SHA", "status": "ok"},
                    {"status": "ok", "params_hash": "abc"},
                    {"plan_point_id": "p1", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                    {"plan_point_id": "p2", "plan_source_sha256": "plan_sha_m39", "status": "ok"},
                ],
            )

            proc = self._run(["--plan", str(plan), "--jsonl", str(jsonl)])
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            payload = self._parse_stdout_json(proc)
            counts = payload["counts"]
            self.assertEqual(int(counts["n_records_foreign"]), 1)
            self.assertEqual(int(counts["n_records_unmapped"]), 1)
            self.assertEqual(int(counts["n_missing"]), 1)
            self.assertEqual(payload["missing_plan_point_ids"], ["p0"])


if __name__ == "__main__":
    unittest.main()

