import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M50E2ScanSpline4LogHCliToy(unittest.TestCase):
    def _run_scan(self, *, script: Path, out_dir: Path, p3_spec: str) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(script),
            "--deformation",
            "spline4_logh",
            "--toy",
            "--sampler",
            "random",
            "--n-samples",
            "3",
            "--seed",
            "42",
            "--grid",
            "H0=66.0:69.0",
            "--grid",
            "Omega_m=0.28:0.34",
            "--grid",
            f"spl4_dlogh_z3={p3_spec}",
            "--grid",
            "spl4_dlogh_z30=-0.5:0.5",
            "--grid",
            "spl4_dlogh_z300=-0.5:0.5",
            "--grid",
            "spl4_dlogh_z1100=-0.5:0.5",
            "--out-dir",
            str(out_dir),
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_rows(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_toy_cli_smoke_with_spline4_logh(self) -> None:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            proc_a = self._run_scan(script=script, out_dir=out_a, p3_spec="-0.5:0.5")
            output_a = (proc_a.stdout or "") + (proc_a.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=output_a)

            jsonl_a = out_a / "e2_scan_points.jsonl"
            self.assertTrue(jsonl_a.is_file())
            rows_a = self._load_rows(jsonl_a)
            self.assertGreaterEqual(len(rows_a), 1)
            self.assertTrue(any(str(r.get("status", "")).strip() for r in rows_a))
            self.assertTrue(any(str(r.get("status")) == "ok" for r in rows_a))

            for row in rows_a:
                self.assertEqual(row.get("model"), "spline4_logh")
                self.assertEqual(row.get("deformation_family"), "spline4_logh")
                self.assertTrue(str(row.get("params_hash", "")).strip())
                params = row.get("params") or {}
                for key in ("spl4_dlogh_z3", "spl4_dlogh_z30", "spl4_dlogh_z300", "spl4_dlogh_z1100"):
                    self.assertIn(key, params)

            out_b = td_path / "out_b"
            proc_b = self._run_scan(script=script, out_dir=out_b, p3_spec="0.9:0.9")
            output_b = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_b.returncode, 0, msg=output_b)
            rows_b = self._load_rows(out_b / "e2_scan_points.jsonl")
            self.assertGreaterEqual(len(rows_b), 1)

            hashes_a = {str(row.get("params_hash")) for row in rows_a}
            hashes_b = {str(row.get("params_hash")) for row in rows_b}
            self.assertNotEqual(hashes_a, hashes_b)


if __name__ == "__main__":
    unittest.main()
