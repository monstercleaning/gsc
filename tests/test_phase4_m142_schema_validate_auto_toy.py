from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT / "scripts" / "phase4_cosmofalsify_demo.py"
VALIDATOR = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4M142SchemaValidateAutoToy(unittest.TestCase):
    def test_demo_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "demo"
            proc_demo = subprocess.run(
                [
                    sys.executable,
                    str(DEMO_SCRIPT),
                    "--outdir",
                    str(outdir),
                    "--created-utc",
                    "946684800",
                    "--keep-work",
                    "0",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_demo.returncode, 0, msg=(proc_demo.stdout or "") + (proc_demo.stderr or ""))

            report_json = outdir / "cosmofalsify_demo_report.json"
            self.assertTrue(report_json.is_file())

            proc_validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--auto",
                    "--schema-dir",
                    str(ROOT / "schemas"),
                    "--json",
                    str(report_json),
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
