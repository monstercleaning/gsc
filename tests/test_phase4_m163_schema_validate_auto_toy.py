from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_m163_five_problems_report.py"
SCHEMA_VALIDATE = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4M163SchemaValidateAutoToy(unittest.TestCase):
    def test_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "m163"
            run_proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--outdir",
                    str(outdir),
                    "--format",
                    "json",
                    "--created-utc",
                    "946684800",
                    "--drift-eps",
                    "0.01",
                    "--use-cov",
                    "0",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(run_proc.returncode, 0, msg=(run_proc.stdout or "") + (run_proc.stderr or ""))

            report = outdir / "FIVE_PROBLEMS_REPORT.json"
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
