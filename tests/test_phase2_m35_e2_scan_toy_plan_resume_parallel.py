import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M35E2ScanToyPlanResumeParallel(unittest.TestCase):
    def _write_plan_json(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "toyplansha"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.4, "Omega_m": 0.315}},
                {"point_id": "p2", "params": {"H0": 68.1, "Omega_m": 0.325}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_scan(
        self,
        *,
        script: Path,
        plan: Path,
        out_dir: Path,
        jobs: int,
        resume: bool,
        dry_run: bool = False,
    ) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan),
            "--jobs",
            str(jobs),
            "--out-dir",
            str(out_dir),
        ]
        if resume:
            cmd.append("--resume")
        if dry_run:
            cmd.append("--dry-run")
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_jsonl(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _normalized(self, rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "sample_index": int(row.get("sample_index", -1)),
                    "plan_point_id": row.get("plan_point_id"),
                    "params_hash": row.get("params_hash"),
                    "status": row.get("status"),
                    "chi2_total": round(float(row.get("chi2_total")), 12) if row.get("chi2_total") is not None else None,
                    "chi2_cmb": round(float(row.get("chi2_cmb")), 12) if row.get("chi2_cmb") is not None else None,
                    "drift_pass": bool(row.get("drift_pass", False)),
                    "microphysics_penalty": round(float(row.get("microphysics_penalty", 0.0)), 12),
                }
            )
        return out

    def test_toy_plan_parallel_is_deterministic_and_resume_dedupes(self):
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan_json = td_path / "plan.json"
            out_jobs1 = td_path / "out_jobs1"
            out_jobs2 = td_path / "out_jobs2"
            self._write_plan_json(plan_json)

            proc1 = self._run_scan(
                script=script,
                plan=plan_json,
                out_dir=out_jobs1,
                jobs=1,
                resume=False,
            )
            output1 = (proc1.stdout or "") + (proc1.stderr or "")
            self.assertEqual(proc1.returncode, 0, msg=output1)

            jsonl_1 = out_jobs1 / "e2_scan_points.jsonl"
            self.assertTrue(jsonl_1.is_file())
            rows_1 = self._load_jsonl(jsonl_1)
            self.assertEqual(len(rows_1), 3)
            self.assertEqual([row.get("plan_point_id") for row in rows_1], ["p0", "p1", "p2"])

            proc_resume = self._run_scan(
                script=script,
                plan=plan_json,
                out_dir=out_jobs1,
                jobs=1,
                resume=True,
            )
            output_resume = (proc_resume.stdout or "") + (proc_resume.stderr or "")
            self.assertEqual(proc_resume.returncode, 0, msg=output_resume)
            rows_resume = self._load_jsonl(jsonl_1)
            self.assertEqual(len(rows_resume), len(rows_1))

            proc2 = self._run_scan(
                script=script,
                plan=plan_json,
                out_dir=out_jobs2,
                jobs=2,
                resume=False,
            )
            output2 = (proc2.stdout or "") + (proc2.stderr or "")
            self.assertEqual(proc2.returncode, 0, msg=output2)
            jsonl_2 = out_jobs2 / "e2_scan_points.jsonl"
            self.assertTrue(jsonl_2.is_file())
            rows_2 = self._load_jsonl(jsonl_2)
            self.assertEqual(self._normalized(rows_2), self._normalized(rows_1))

    def test_toy_plan_dry_run_reports_summary_and_no_artifacts(self):
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan_json = td_path / "plan.json"
            out_dir = td_path / "out_dry"
            self._write_plan_json(plan_json)

            proc = self._run_scan(
                script=script,
                plan=plan_json,
                out_dir=out_dir,
                jobs=2,
                resume=False,
                dry_run=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            payload = json.loads((proc.stdout or "").strip())
            self.assertEqual(payload.get("mode"), "dry_run")
            self.assertEqual(int(payload.get("n_pending_points", -1)), 3)
            self.assertFalse((out_dir / "e2_scan_points.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
