import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M57ScanPlanResumeDedupeByPlanPointID(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m57resumeplan"},
            "points": [
                {"point_id": "p0", "params": {"H0": 67.0, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.0, "Omega_m": 0.300}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_scan(self, *, plan: Path, out_dir: Path, resume: bool) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan),
            "--jobs",
            "1",
            "--out-dir",
            str(out_dir),
        ]
        if resume:
            cmd.append("--resume")
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_jsonl(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                rows.append(json.loads(text))
        return rows

    def test_resume_skips_completed_by_plan_point_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            out_dir = td_path / "out"
            self._write_plan(plan)

            proc_first = self._run_scan(plan=plan, out_dir=out_dir, resume=False)
            out_first = (proc_first.stdout or "") + (proc_first.stderr or "")
            self.assertEqual(proc_first.returncode, 0, msg=out_first)

            jsonl = out_dir / "e2_scan_points.jsonl"
            rows_first = self._load_jsonl(jsonl)
            self.assertEqual(len(rows_first), 2)
            self.assertEqual([row.get("plan_point_id") for row in rows_first], ["p0", "p1"])

            proc_resume = self._run_scan(plan=plan, out_dir=out_dir, resume=True)
            out_resume = (proc_resume.stdout or "") + (proc_resume.stderr or "")
            self.assertEqual(proc_resume.returncode, 0, msg=out_resume)
            rows_resume = self._load_jsonl(jsonl)
            self.assertEqual(rows_resume, rows_first)

    def test_resume_retries_error_plan_point_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            out_dir = td_path / "out"
            self._write_plan(plan)

            proc_first = self._run_scan(plan=plan, out_dir=out_dir, resume=False)
            out_first = (proc_first.stdout or "") + (proc_first.stderr or "")
            self.assertEqual(proc_first.returncode, 0, msg=out_first)

            jsonl = out_dir / "e2_scan_points.jsonl"
            rows = self._load_jsonl(jsonl)
            self.assertEqual(len(rows), 2)
            rows[0]["status"] = "error"
            rows[0]["error"] = {"type": "RuntimeError", "message": "synthetic test error"}
            with jsonl.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")

            proc_resume = self._run_scan(plan=plan, out_dir=out_dir, resume=True)
            out_resume = (proc_resume.stdout or "") + (proc_resume.stderr or "")
            self.assertEqual(proc_resume.returncode, 0, msg=out_resume)

            rows_after = self._load_jsonl(jsonl)
            self.assertEqual(len(rows_after), 3)
            p0_rows = [row for row in rows_after if row.get("plan_point_id") == "p0"]
            self.assertEqual(len(p0_rows), 2)
            self.assertIn("error", {str(row.get("status")) for row in p0_rows})
            self.assertIn("ok", {str(row.get("status")) for row in p0_rows})


if __name__ == "__main__":
    unittest.main()
