import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class TestPhase3M131ScanAnalysisDeterminismToy(unittest.TestCase):
    def test_deterministic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_path = td_path / "scan.jsonl"
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            rows = [
                {
                    "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                    "status": "ok",
                    "plan_point_id": "p1",
                    "point_index": 0,
                    "results": {
                        "chi2_total": 2.5,
                        "ndof_total": 7,
                        "deltas": {"delta_chi2_total": -0.2},
                    },
                    "params": {"Omega_m": 0.31, "w0": -0.95, "lambda": 0.1, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
                },
                {
                    "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                    "status": "ok",
                    "plan_point_id": "p2",
                    "point_index": 1,
                    "results": {
                        "chi2_total": 2.0,
                        "ndof_total": 8,
                        "deltas": {"delta_chi2_total": -0.1},
                    },
                    "params": {"Omega_m": 0.30, "w0": -1.0, "lambda": 0.0, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
                },
            ]
            with in_path.open("w", encoding="utf-8", newline="\n") as fh:
                for row in rows:
                    fh.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
                    fh.write("\n")

            base_cmd = [
                sys.executable,
                str(SCRIPT),
                "--inputs",
                str(in_path),
                "--top-k",
                "10",
                "--metric",
                "chi2_total",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]

            proc_a = subprocess.run(
                [*base_cmd, "--outdir", str(out_a)],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))

            proc_b = subprocess.run(
                [*base_cmd, "--outdir", str(out_b)],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            for name in (
                "SCAN_ANALYSIS.json",
                "SCAN_ANALYSIS.md",
                "BEST_CANDIDATES.csv",
                "REPRODUCE_TOP_CANDIDATES.sh",
            ):
                self.assertEqual(_sha256(out_a / name), _sha256(out_b / name), msg=f"non-deterministic file: {name}")
                text = (out_a / name).read_text(encoding="utf-8")
                for token in ABS_TOKENS:
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
