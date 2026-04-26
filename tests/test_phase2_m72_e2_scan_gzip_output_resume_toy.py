import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M72E2ScanGzipOutputResumeToy(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m72_scan_gzip_resume_source"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.2, "Omega_m": 0.305}},
                {"point_id": "p2", "params": {"H0": 67.6, "Omega_m": 0.310}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_scan(
        self,
        *,
        plan: Path,
        outdir: Path,
        points_jsonl_name: str,
        resume: bool,
    ) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan),
            "--out-dir",
            str(outdir),
            "--points-jsonl-name",
            str(points_jsonl_name),
        ]
        if bool(resume):
            cmd.append("--resume")
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_rows_gzip(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                text = str(line).strip()
                if not text:
                    continue
                rows.append(json.loads(text))
        return rows

    def test_toy_scan_writes_gzip_jsonl_and_resume_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            plan = tdp / "plan.json"
            outdir = tdp / "out"
            self._write_plan(plan)

            points_name = "e2_scan_points.jsonl.gz"
            proc1 = self._run_scan(plan=plan, outdir=outdir, points_jsonl_name=points_name, resume=False)
            output1 = (proc1.stdout or "") + (proc1.stderr or "")
            self.assertEqual(proc1.returncode, 0, msg=output1)

            jsonl_gz = outdir / points_name
            self.assertTrue(jsonl_gz.is_file(), msg=str(jsonl_gz))
            rows1 = self._load_rows_gzip(jsonl_gz)
            self.assertGreaterEqual(len(rows1), 1)
            hashes1 = sorted(str(row.get("params_hash", "")) for row in rows1)

            proc2 = self._run_scan(plan=plan, outdir=outdir, points_jsonl_name=points_name, resume=True)
            output2 = (proc2.stdout or "") + (proc2.stderr or "")
            self.assertEqual(proc2.returncode, 0, msg=output2)
            rows2 = self._load_rows_gzip(jsonl_gz)
            hashes2 = sorted(str(row.get("params_hash", "")) for row in rows2)

            self.assertEqual(len(rows2), len(rows1))
            self.assertEqual(hashes2, hashes1)


if __name__ == "__main__":
    unittest.main()
