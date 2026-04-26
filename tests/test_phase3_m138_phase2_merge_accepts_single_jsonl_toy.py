import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MERGE_SCRIPT = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"


class TestPhase3M138Phase2MergeAcceptsSingleJsonlToy(unittest.TestCase):
    def test_single_input_file_merge(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_dir = td_path / "inputs"
            in_dir.mkdir(parents=True, exist_ok=True)
            in_file = in_dir / "single.jsonl"
            out_file = td_path / "merged.jsonl"

            row = {
                "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                "status": "ok",
                "plan_point_id": "single_point_000",
                "plan_source_sha256": "plan_sha_single",
                "scan_config_sha256": "scan_sha_single",
                "point_index": 0,
                "params": {
                    "Omega_m": 0.31,
                    "w0": -1.0,
                    "lambda": 0.0,
                },
                "results": {
                    "chi2_total": 1.0,
                    "ndof_total": 1,
                },
            }
            in_file.write_text(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(MERGE_SCRIPT),
                    str(in_dir),
                    "--out",
                    str(out_file),
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertTrue(out_file.is_file())

            rows = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(str(rows[0].get("plan_point_id")), "single_point_000")


if __name__ == "__main__":
    unittest.main()
