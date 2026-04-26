import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"


class TestPhase3M131ScanAnalysisSupportsGzAndDirsToy(unittest.TestCase):
    def test_dir_discovery_supports_jsonl_and_jsonl_gz(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_dir = td_path / "shards"
            shard_dir.mkdir(parents=True, exist_ok=True)
            plain = shard_dir / "a.jsonl"
            gz = shard_dir / "b.jsonl.gz"
            outdir = td_path / "out"

            row_a = {
                "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                "status": "ok",
                "plan_point_id": "p_a",
                "point_index": 0,
                "results": {"chi2_total": 2.0, "ndof_total": 5},
                "params": {"Omega_m": 0.3, "w0": -1.0, "lambda": 0.0, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
            }
            row_b = {
                "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                "status": "ok",
                "plan_point_id": "p_b",
                "point_index": 1,
                "results": {"chi2_total": 1.5, "ndof_total": 6},
                "params": {"Omega_m": 0.31, "w0": -0.95, "lambda": 0.1, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
            }

            plain.write_text(json.dumps(row_a, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")
            with gzip.open(gz, "wt", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row_b, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--inputs",
                    str(shard_dir),
                    "--outdir",
                    str(outdir),
                    "--top-k",
                    "5",
                    "--metric",
                    "chi2_total",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            payload = json.loads((outdir / "SCAN_ANALYSIS.json").read_text(encoding="utf-8"))
            counts = payload.get("counts", {})
            self.assertEqual(int(counts.get("rows_parsed", -1)), 2)
            inputs = payload.get("inputs", [])
            basenames = sorted(str(row.get("basename")) for row in inputs if isinstance(row, dict))
            self.assertEqual(basenames, ["a.jsonl", "b.jsonl.gz"])


if __name__ == "__main__":
    unittest.main()
