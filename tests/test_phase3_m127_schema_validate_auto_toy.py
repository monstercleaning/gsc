from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORT_SCRIPT = ROOT / "scripts" / "phase3_sf_sigmatensor_fsigma8_report.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M127SchemaValidateAutoToy(unittest.TestCase):
    def test_schema_validate_auto_passes_for_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = td_path / "report"

            proc_report = subprocess.run(
                [
                    sys.executable,
                    str(REPORT_SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.315",
                    "--w0",
                    "-0.95",
                    "--lambda",
                    "0.4",
                    "--sigma8-mode",
                    "fixed",
                    "--sigma8-0",
                    "0.8",
                    "--rsd",
                    "0",
                    "--z-start",
                    "20",
                    "--n-steps-growth",
                    "256",
                    "--n-steps-bg",
                    "1024",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--outdir",
                    str(outdir),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(
                proc_report.returncode,
                0,
                msg=(proc_report.stdout or "") + (proc_report.stderr or ""),
            )

            proc_validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_SCRIPT),
                    "--auto",
                    "--json",
                    str(outdir / "FSIGMA8_REPORT.json"),
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(
                proc_validate.returncode,
                0,
                msg=(proc_validate.stdout or "") + (proc_validate.stderr or ""),
            )


if __name__ == "__main__":
    unittest.main()
