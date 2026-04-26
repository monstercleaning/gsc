from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EFT_SCRIPT = ROOT / "scripts" / "phase3_pt_sigmatensor_eft_export_pack.py"
VALIDATOR = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M124SchemaValidateAutoToy(unittest.TestCase):
    def test_auto_schema_validation_for_eft_export_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "eft"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EFT_SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.315",
                    "--w0",
                    "-0.95",
                    "--lambda",
                    "0.4",
                    "--z-max",
                    "5",
                    "--n-steps",
                    "256",
                    "--outdir",
                    str(outdir),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            summary = outdir / "EFT_EXPORT_SUMMARY.json"
            self.assertTrue(summary.is_file())

            proc_val = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--auto",
                    "--schema-dir",
                    str(ROOT / "schemas"),
                    "--json",
                    str(summary),
                    "--format",
                    "text",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_val.returncode, 0, msg=(proc_val.stdout or "") + (proc_val.stderr or ""))


if __name__ == "__main__":
    unittest.main()

