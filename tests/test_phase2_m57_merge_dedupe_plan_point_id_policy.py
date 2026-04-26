import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M57MergeDedupePlanPointIDPolicy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run_merge(self, *, inputs: list[Path], out_jsonl: Path) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        cmd = [
            sys.executable,
            str(script),
            *[str(p) for p in inputs],
            "--out",
            str(out_jsonl),
            "--dedupe-key",
            "auto",
            "--canonicalize",
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_rows(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_merge_prefers_ok_and_lowest_chi2_for_plan_point_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            a = td_path / "a.jsonl"
            b = td_path / "b.jsonl"
            out = td_path / "merged.jsonl"
            source = "plan_sha_same"

            self._write_jsonl(
                a,
                [
                    {
                        "plan_point_id": "p0",
                        "plan_source_sha256": source,
                        "status": "error",
                        "params_hash": "hash0",
                    },
                    {
                        "plan_point_id": "p1",
                        "plan_source_sha256": source,
                        "status": "ok",
                        "chi2_total": 5.0,
                        "params_hash": "hash1a",
                    },
                ],
            )
            self._write_jsonl(
                b,
                [
                    {
                        "plan_point_id": "p0",
                        "plan_source_sha256": source,
                        "status": "ok",
                        "chi2_total": 9.0,
                        "params_hash": "hash0b",
                    },
                    {
                        "plan_point_id": "p1",
                        "plan_source_sha256": source,
                        "status": "ok",
                        "chi2_total": 1.0,
                        "params_hash": "hash1b",
                    },
                ],
            )

            proc = self._run_merge(inputs=[a, b], out_jsonl=out)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            rows = self._load_rows(out)
            self.assertEqual(len(rows), 2)
            by_pid = {str(row.get("plan_point_id")): row for row in rows}
            self.assertEqual(str(by_pid["p0"].get("status", "")).lower(), "ok")
            self.assertAlmostEqual(float(by_pid["p0"].get("chi2_total")), 9.0, places=9)
            self.assertAlmostEqual(float(by_pid["p1"].get("chi2_total")), 1.0, places=9)

    def test_merge_fails_on_plan_source_mismatch_for_same_plan_point_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            a = td_path / "a.jsonl"
            b = td_path / "b.jsonl"
            out = td_path / "merged.jsonl"
            self._write_jsonl(
                a,
                [
                    {
                        "plan_point_id": "p0",
                        "plan_source_sha256": "plan_sha_A",
                        "status": "ok",
                        "chi2_total": 2.0,
                        "params_hash": "hashA",
                    }
                ],
            )
            self._write_jsonl(
                b,
                [
                    {
                        "plan_point_id": "p0",
                        "plan_source_sha256": "plan_sha_B",
                        "status": "ok",
                        "chi2_total": 1.5,
                        "params_hash": "hashB",
                    }
                ],
            )

            proc = self._run_merge(inputs=[a, b], out_jsonl=out)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=output)
            self.assertIn("plan_source_sha256", output)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
