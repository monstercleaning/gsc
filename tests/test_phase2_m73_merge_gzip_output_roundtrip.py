import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M73MergeGzipOutputRoundtrip(unittest.TestCase):
    def _write_plain_jsonl(self, path: Path, rows: list[dict], *, add_invalid: bool = False) -> None:
        lines = [json.dumps(row, sort_keys=True) for row in rows]
        if bool(add_invalid):
            lines.append("{invalid_json")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_gzip_jsonl(self, path: Path, rows: list[dict]) -> None:
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_merge_to_gzip_and_live_status_roundtrip(self) -> None:
        merge_script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        status_script = ROOT / "scripts" / "phase2_e2_live_status.py"
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            shard_a = tdp / "a.jsonl"
            shard_b = tdp / "b.jsonl.gz"
            merged = tdp / "merged.jsonl.gz"

            self._write_plain_jsonl(
                shard_a,
                [
                    {"params_hash": "h1", "status": "ok", "chi2_total": 5.0},
                    {"params_hash": "h2", "status": "error", "chi2_total": 9.0, "error": "ValueError bad"},
                ],
                add_invalid=True,
            )
            self._write_gzip_jsonl(
                shard_b,
                [
                    {"params_hash": "h1", "status": "ok", "chi2_total": 4.0},
                    {"params_hash": "h3", "status": "ok", "chi2_total": 7.0},
                    {"params_hash": "h4", "chi2_total": 6.0},
                ],
            )

            merge_cmd = [
                sys.executable,
                str(merge_script),
                str(shard_a),
                str(shard_b),
                "--out",
                str(merged),
                "--external-sort",
                "--chunk-records",
                "2",
            ]
            proc_merge = subprocess.run(merge_cmd, cwd=str(ROOT), text=True, capture_output=True)
            merge_output = (proc_merge.stdout or "") + (proc_merge.stderr or "")
            self.assertEqual(proc_merge.returncode, 0, msg=merge_output)
            self.assertTrue(merged.is_file(), msg=str(merged))

            with merged.open("rb") as fh:
                self.assertEqual(fh.read(2), b"\x1f\x8b")
            with gzip.open(merged, "rt", encoding="utf-8") as fh:
                parsed = [json.loads(line) for line in fh if str(line).strip()]
            self.assertEqual(len(parsed), 4)

            status_cmd = [
                sys.executable,
                str(status_script),
                "--input",
                str(merged),
                "--format",
                "json",
            ]
            proc_status = subprocess.run(status_cmd, cwd=str(ROOT), text=True, capture_output=True)
            status_output = (proc_status.stdout or "") + (proc_status.stderr or "")
            self.assertEqual(proc_status.returncode, 0, msg=status_output)
            payload = json.loads(proc_status.stdout)
            self.assertEqual(int(payload.get("n_records_parsed", 0)), 4)
            self.assertEqual(int(payload.get("n_invalid_lines", 0)), 0)
            status_counts = payload.get("status_counts", {})
            self.assertEqual(int(status_counts.get("ok", 0)), 2)
            self.assertEqual(int(status_counts.get("error", 0)), 1)
            self.assertEqual(int(status_counts.get("unknown", 0)), 1)
            best = payload.get("best", {}).get("overall") or {}
            self.assertEqual(str(best.get("params_hash", "")), "h1")
            self.assertAlmostEqual(float(best.get("chi2_total", 0.0)), 4.0, places=12)


if __name__ == "__main__":
    unittest.main()
