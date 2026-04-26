import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M36E2MergeJsonlConflictPolicy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run_merge(self, *, inputs: list[Path], out_jsonl: Path, report_out: Optional[Path] = None) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        cmd = [sys.executable, str(script)] + [str(p) for p in inputs] + ["--out", str(out_jsonl)]
        if report_out is not None:
            cmd.extend(["--report-out", str(report_out)])
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_jsonl(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
        return rows

    def test_conflict_policy_prefers_ok_then_lowest_chi2(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            a = td_path / "a.jsonl"
            b = td_path / "b.jsonl"
            out = td_path / "merged.jsonl"
            report = td_path / "report.json"

            self._write_jsonl(
                a,
                [
                    {
                        "params_hash": "hash_A",
                        "status": "error",
                        "error": {"type": "RuntimeError", "message": "boom"},
                        "params": {"H0": 67.0, "Omega_m": 0.3},
                    },
                    {
                        "params_hash": "hash_B",
                        "status": "ok",
                        "chi2_total": 5.0,
                        "params": {"H0": 66.0, "Omega_m": 0.28},
                    },
                ],
            )
            self._write_jsonl(
                b,
                [
                    {
                        "params_hash": "hash_A",
                        "status": "ok",
                        "chi2_total": 9.0,
                        "params": {"H0": 67.0, "Omega_m": 0.3},
                    },
                    {
                        "params_hash": "hash_B",
                        "status": "ok",
                        "chi2_total": 1.0,
                        "params": {"H0": 66.0, "Omega_m": 0.28},
                    },
                ],
            )

            proc = self._run_merge(inputs=[a, b], out_jsonl=out, report_out=report)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue(out.is_file())
            self.assertTrue(report.is_file())

            rows = self._load_jsonl(out)
            self.assertEqual(len(rows), 2)
            by_hash = {str(row.get("params_hash")): row for row in rows}

            self.assertEqual(str(by_hash["hash_A"].get("status", "")).lower(), "ok")
            self.assertAlmostEqual(float(by_hash["hash_A"].get("chi2_total")), 9.0, places=9)
            self.assertAlmostEqual(float(by_hash["hash_B"].get("chi2_total")), 1.0, places=9)

            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("policy_prefer"), "ok_then_lowest_chi2")
            self.assertEqual(int(payload.get("n_duplicates", 0)), 2)
            self.assertGreaterEqual(int(payload.get("n_conflicts", 0)), 1)


if __name__ == "__main__":
    unittest.main()
