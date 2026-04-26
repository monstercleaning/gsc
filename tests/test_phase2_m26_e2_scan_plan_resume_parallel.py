import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M26E2ScanPlanResumeParallel(unittest.TestCase):
    def _write_priors_csv(self, path: Path) -> None:
        path.write_text(
            "\n".join(
                [
                    "name,value,sigma",
                    "100theta_star,1.041,0.001",
                    "R,1.75,0.01",
                    "lA,301.5,0.1",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_plan_json(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "deadbeef"},
            "points": [
                {"point_id": "p0", "params": {"H0": 67.1, "Omega_m": 0.310}},
                {"point_id": "p1", "params": {"H0": 67.3, "Omega_m": 0.305}},
                {"point_id": "p2", "params": {"H0": 67.6, "Omega_m": 0.315}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _load_jsonl(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _normalized(self, rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "sample_index": row.get("sample_index"),
                    "status": row.get("status"),
                    "params_hash": row.get("params_hash"),
                    "plan_point_id": row.get("plan_point_id"),
                    "plan_source_sha256": row.get("plan_source_sha256"),
                    "model": row.get("model"),
                    "params": row.get("params"),
                }
            )
        return out

    def _run_scan(self, *, script: Path, plan: Path, priors: Path, out_dir: Path, jobs: int, resume: bool) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--plan",
            str(plan),
            "--cmb",
            str(priors),
            "--omega-b-h2",
            "0.02237",
            "--omega-c-h2",
            "0.1200",
            "--Neff",
            "3.046",
            "--Tcmb-K",
            "2.7255",
            "--jobs",
            str(jobs),
            "--out-dir",
            str(out_dir),
        ]
        if resume:
            cmd.append("--resume")
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_plan_resume_and_parallel_are_deterministic(self):
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan_json = td_path / "plan.json"
            priors_csv = td_path / "cmb.csv"
            out_jobs1 = td_path / "out_jobs1"
            out_jobs2 = td_path / "out_jobs2"

            self._write_plan_json(plan_json)
            self._write_priors_csv(priors_csv)

            proc1 = self._run_scan(
                script=script,
                plan=plan_json,
                priors=priors_csv,
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
            for row in rows_1:
                self.assertTrue(isinstance(row.get("params_hash"), str) and row.get("params_hash"))
                self.assertIn(row.get("status"), {"ok", "error"})
                self.assertTrue(isinstance(row.get("plan_point_id"), str))

            proc_resume = self._run_scan(
                script=script,
                plan=plan_json,
                priors=priors_csv,
                out_dir=out_jobs1,
                jobs=1,
                resume=True,
            )
            output_resume = (proc_resume.stdout or "") + (proc_resume.stderr or "")
            self.assertEqual(proc_resume.returncode, 0, msg=output_resume)

            rows_resume = self._load_jsonl(jsonl_1)
            error_ids = {
                str(row.get("plan_point_id"))
                for row in rows_1
                if str(row.get("status", "ok")).strip().lower() == "error"
            }
            self.assertEqual(len(rows_resume), len(rows_1) + len(error_ids))
            for point_id in sorted(
                {
                    str(row.get("plan_point_id"))
                    for row in rows_1
                    if str(row.get("status", "ok")).strip().lower() != "error"
                }
            ):
                hits = [row for row in rows_resume if str(row.get("plan_point_id")) == point_id]
                self.assertEqual(len(hits), 1)

            proc2 = self._run_scan(
                script=script,
                plan=plan_json,
                priors=priors_csv,
                out_dir=out_jobs2,
                jobs=2,
                resume=False,
            )
            output2 = (proc2.stdout or "") + (proc2.stderr or "")
            self.assertEqual(proc2.returncode, 0, msg=output2)

            jsonl_2 = out_jobs2 / "e2_scan_points.jsonl"
            self.assertTrue(jsonl_2.is_file())
            rows_2 = self._load_jsonl(jsonl_2)
            self.assertEqual(len(rows_2), len(rows_1))
            self.assertEqual(self._normalized(rows_2), self._normalized(rows_1))


if __name__ == "__main__":
    unittest.main()
