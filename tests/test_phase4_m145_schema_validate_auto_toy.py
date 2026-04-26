from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_sigmatensor_drift_sign_diagnostic.py"
VALIDATOR = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4M145SchemaValidateAutoToy(unittest.TestCase):
    def test_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "diag"
            proc_diag = subprocess.run(
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
                    "0.5",
                    "--n-lambda",
                    "2",
                    "--n-steps-bg",
                    "512",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_diag.returncode, 0, msg=(proc_diag.stdout or "") + (proc_diag.stderr or ""))

            report = outdir / "DRIFT_SIGN_DIAGNOSTIC.json"
            self.assertTrue(report.is_file())

            proc_validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--auto",
                    "--schema-dir",
                    str(ROOT / "schemas"),
                    "--json",
                    str(report),
                    "--format",
                    "text",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_validate.returncode, 0, msg=(proc_validate.stdout or "") + (proc_validate.stderr or ""))


if __name__ == "__main__":
    unittest.main()
