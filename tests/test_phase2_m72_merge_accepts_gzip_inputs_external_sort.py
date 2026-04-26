import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M72MergeAcceptsGzipInputsExternalSort(unittest.TestCase):
    def _write_jsonl_gz(self, path: Path, rows: list[dict], *, add_invalid: bool = False) -> None:
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            if bool(add_invalid):
                fh.write("{not_json\n")

    def _load_jsonl_gz(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                text = str(line).strip()
                if not text:
                    continue
                rows.append(json.loads(text))
        return rows

    def test_merge_reads_gzip_inputs_with_external_sort(self) -> None:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            a = tdp / "shard_a.jsonl.gz"
            b = tdp / "shard_b.jsonl.gz"
            out = tdp / "merged.jsonl.gz"

            rows_a = [
                {"params_hash": "h2", "status": "ok", "chi2_total": 8.0},
                {"params_hash": "h1", "status": "ok", "chi2_total": 10.0},
                {"params_hash": "h4", "status": "unknown", "chi2_total": 12.0},
            ]
            rows_b = [
                {"params_hash": "h1", "status": "ok", "chi2_total": 7.0},
                {"params_hash": "h3", "status": "error", "chi2_total": 9.0, "error": "ValueError: unstable"},
                {"params_hash": "h4", "status": "ok", "chi2_total": 11.0},
            ]
            self._write_jsonl_gz(a, rows_a, add_invalid=True)
            self._write_jsonl_gz(b, rows_b, add_invalid=True)

            cmd = [
                sys.executable,
                str(script),
                str(a),
                str(b),
                "--out",
                str(out),
                "--external-sort",
                "--chunk-records",
                "2",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue(out.is_file())

            merged = self._load_jsonl_gz(out)
            self.assertEqual([str(row.get("params_hash")) for row in merged], ["h1", "h2", "h3", "h4"])
            by_hash = {str(row.get("params_hash")): row for row in merged}
            self.assertAlmostEqual(float(by_hash["h1"]["chi2_total"]), 7.0, places=12)
            self.assertEqual(str(by_hash["h1"].get("status")), "ok")
            self.assertAlmostEqual(float(by_hash["h4"]["chi2_total"]), 11.0, places=12)
            self.assertEqual(str(by_hash["h4"].get("status")), "ok")


if __name__ == "__main__":
    unittest.main()
