from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_sigmatensor_optimal_control_gap_diagnostic.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M146GapDiagnosticDeterminismToy(unittest.TestCase):
    def test_deterministic_outputs_and_baseline_negative_z3(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--outdir",
                        str(outdir),
                        "--format",
                        "json",
                        "--created-utc",
                        "946684800",
                        "--toy",
                        "1",
                        "--emit-plot",
                        "0",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "GAP_DIAGNOSTIC.json"
            json_b = out_b / "GAP_DIAGNOSTIC.json"
            txt_a = out_a / "GAP_DIAGNOSTIC.txt"
            txt_b = out_b / "GAP_DIAGNOSTIC.txt"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(txt_a.read_bytes(), txt_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_sigmatensor_optimal_control_gap_diagnostic_report_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))

            rows = payload.get("gap_by_lambda", [])
            self.assertIsInstance(rows, list)
            self.assertGreaterEqual(len(rows), 1)

            baseline_z3 = float(rows[0].get("baseline_drift_at_z3_si"))
            self.assertLess(baseline_z3, 0.0)

            content_json = json_a.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), content_json)
            for token in ABS_TOKENS:
                self.assertNotIn(token, content_json)


if __name__ == "__main__":
    unittest.main()
