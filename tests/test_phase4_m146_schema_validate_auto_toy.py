from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GAP_SCRIPT = ROOT / "scripts" / "phase4_sigmatensor_optimal_control_gap_diagnostic.py"
SCHEMA_VALIDATE = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4M146SchemaValidateAutoToy(unittest.TestCase):
    def test_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "gap"

            run_proc = subprocess.run(
                [
                    sys.executable,
                    str(GAP_SCRIPT),
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
            self.assertEqual(run_proc.returncode, 0, msg=(run_proc.stdout or "") + (run_proc.stderr or ""))

            report = outdir / "GAP_DIAGNOSTIC.json"
            self.assertTrue(report.is_file())

            val_proc = subprocess.run(
                [
                    sys.executable,
                    str(SCHEMA_VALIDATE),
                    "--auto",
                    "--schema-dir",
                    str(ROOT / "schemas"),
                    "--json",
                    str(report),
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(val_proc.returncode, 0, msg=(val_proc.stdout or "") + (val_proc.stderr or ""))


if __name__ == "__main__":
    unittest.main()
