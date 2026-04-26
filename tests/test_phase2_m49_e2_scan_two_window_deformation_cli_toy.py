import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M49E2ScanTwoWindowCLIToy(unittest.TestCase):
    def _run_scan(self, *, script: Path, out_dir: Path) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "logh_two_window",
            "--toy",
            "--sampler",
            "random",
            "--n-samples",
            "4",
            "--seed",
            "123",
            "--grid",
            "H0=66.0:69.0",
            "--grid",
            "Omega_m=0.28:0.34",
            "--grid",
            "tw1_zc=1.5:8.0",
            "--grid",
            "tw1_w=0.05:0.80",
            "--grid",
            "tw1_a=-1.0:1.0",
            "--grid",
            "tw2_zc=50.0:2000.0",
            "--grid",
            "tw2_w=0.05:1.50",
            "--grid",
            "tw2_a=-1.0:1.0",
            "--out-dir",
            str(out_dir),
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_rows(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _normalized(self, rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        for row in rows:
            params = row.get("params") or {}
            out.append(
                {
                    "sample_index": int(row.get("sample_index", -1)),
                    "status": row.get("status"),
                    "deformation_family": row.get("deformation_family"),
                    "model": row.get("model"),
                    "params_hash": row.get("params_hash"),
                    "chi2_total": round(float(row.get("chi2_total")), 12),
                    "tw1_zc": round(float(params.get("tw1_zc")), 12),
                    "tw1_w": round(float(params.get("tw1_w")), 12),
                    "tw1_a": round(float(params.get("tw1_a")), 12),
                    "tw2_zc": round(float(params.get("tw2_zc")), 12),
                    "tw2_w": round(float(params.get("tw2_w")), 12),
                    "tw2_a": round(float(params.get("tw2_a")), 12),
                }
            )
        return out

    def test_toy_cli_smoke_and_determinism(self) -> None:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            proc_a = self._run_scan(script=script, out_dir=out_a)
            output_a = (proc_a.stdout or "") + (proc_a.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=output_a)

            jsonl_a = out_a / "e2_scan_points.jsonl"
            self.assertTrue(jsonl_a.is_file())
            rows_a = self._load_rows(jsonl_a)
            self.assertGreaterEqual(len(rows_a), 1)
            self.assertTrue(any(str(r.get("status")) == "ok" for r in rows_a))

            for row in rows_a:
                self.assertEqual(row.get("model"), "logh_two_window")
                self.assertEqual(row.get("deformation_family"), "logh_two_window")
                params = row.get("params") or {}
                for key in ("tw1_zc", "tw1_w", "tw1_a", "tw2_zc", "tw2_w", "tw2_a"):
                    self.assertIn(key, params)

            proc_b = self._run_scan(script=script, out_dir=out_b)
            output_b = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_b.returncode, 0, msg=output_b)

            rows_b = self._load_rows(out_b / "e2_scan_points.jsonl")
            self.assertEqual(self._normalized(rows_a), self._normalized(rows_b))


if __name__ == "__main__":
    unittest.main()
