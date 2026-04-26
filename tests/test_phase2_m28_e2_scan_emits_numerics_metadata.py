import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M28E2ScanEmitsNumericsMetadata(unittest.TestCase):
    def test_toy_scan_emits_recombination_and_numerics_fields(self):
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_dir = td_path / "out"
            cmd = [
                sys.executable,
                str(script),
                "--toy",
                "--model",
                "lcdm",
                "--sampler",
                "random",
                "--n-samples",
                "3",
                "--seed",
                "17",
                "--integrator",
                "adaptive_simpson",
                "--recombination",
                "peebles3",
                "--drag-method",
                "ode",
                "--grid",
                "H0=66.0:68.0",
                "--grid",
                "Omega_m=0.30:0.33",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            jsonl_path = out_dir / "e2_scan_points.jsonl"
            self.assertTrue(jsonl_path.is_file())
            rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 3)

            for row in rows:
                self.assertEqual(row.get("recombination_method"), "peebles3")
                self.assertIn("cmb_num_method", row)
                self.assertIn("cmb_num_n_eval_dm", row)
                self.assertIn("cmb_num_err_dm", row)
                self.assertIn("cmb_num_n_eval_rs", row)
                self.assertIn("cmb_num_err_rs", row)
                self.assertIn("cmb_num_n_eval_rs_drag", row)
                self.assertIn("cmb_num_err_rs_drag", row)
                self.assertIn("cmb_num_rtol", row)
                self.assertIn("cmb_num_atol", row)

                self.assertIsInstance(int(row.get("cmb_num_n_eval_dm")), int)
                self.assertIsInstance(int(row.get("cmb_num_n_eval_rs")), int)
                self.assertIsInstance(int(row.get("cmb_num_n_eval_rs_drag")), int)

                for key in (
                    "cmb_num_err_dm",
                    "cmb_num_err_rs",
                    "cmb_num_err_rs_drag",
                    "cmb_num_rtol",
                    "cmb_num_atol",
                ):
                    value = row.get(key)
                    self.assertIsNotNone(value, msg=f"missing {key}")
                    self.assertIsInstance(float(value), float)

            summary = json.loads((out_dir / "e2_scan_summary.json").read_text(encoding="utf-8"))
            cfg = summary.get("config") or {}
            self.assertEqual(cfg.get("recombination_method"), "peebles3")
            self.assertEqual(cfg.get("drag_method"), "ode")


if __name__ == "__main__":
    unittest.main()
