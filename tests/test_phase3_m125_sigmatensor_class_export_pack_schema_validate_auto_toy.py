from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = ROOT / "scripts" / "phase3_pt_sigmatensor_class_export_pack.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M125SigmaTensorClassExportPackSchemaValidateAutoToy(unittest.TestCase):
    def test_auto_schema_validation_for_summary_and_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "pack"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT_SCRIPT),
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

            for name in ("EXPORT_SUMMARY.json", "CANDIDATE_RECORD.json"):
                target = outdir / name
                self.assertTrue(target.is_file(), msg=name)
                proc_val = subprocess.run(
                    [
                        sys.executable,
                        str(VALIDATE_SCRIPT),
                        "--auto",
                        "--schema-dir",
                        str(ROOT / "schemas"),
                        "--json",
                        str(target),
                        "--format",
                        "text",
                    ],
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(
                    proc_val.returncode,
                    0,
                    msg=f"{name}: {(proc_val.stdout or '') + (proc_val.stderr or '')}",
                )


if __name__ == "__main__":
    unittest.main()

