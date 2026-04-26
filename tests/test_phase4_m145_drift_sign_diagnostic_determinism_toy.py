from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_sigmatensor_drift_sign_diagnostic.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M145DriftSignDiagnosticDeterminismToy(unittest.TestCase):
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
                        "--lambda-min",
                        "0",
                        "--lambda-max",
                        "0",
                        "--n-lambda",
                        "1",
                        "--z-min",
                        "2",
                        "--z-max",
                        "5",
                        "--n-z",
                        "4",
                        "--n-steps-bg",
                        "512",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "DRIFT_SIGN_DIAGNOSTIC.json"
            json_b = out_b / "DRIFT_SIGN_DIAGNOSTIC.json"
            md_a = out_a / "DRIFT_SIGN_DIAGNOSTIC.md"
            md_b = out_b / "DRIFT_SIGN_DIAGNOSTIC.md"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(md_a.read_bytes(), md_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_sigmatensor_drift_sign_diagnostic_report_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))

            baseline = float(payload.get("summary", {}).get("baseline_lambda0_drift_at_z3_si"))
            self.assertLess(baseline, 0.0)

            text = json_a.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
