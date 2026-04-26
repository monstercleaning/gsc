from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_st_sigmatensor_consistency_report.py"


class TestPhase3M124M123ConsistencyReportDefaultNoCrash(unittest.TestCase):
    def test_default_zmax_runs_without_endpoint_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.315",
                    "--w0",
                    "-0.95",
                    "--lambda",
                    "0.4",
                    "--n-steps",
                    "64",
                    "--outdir",
                    str(outdir),
                    "--format",
                    "text",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue((outdir / "THEORY_CONSISTENCY_REPORT.json").is_file())
            self.assertTrue((outdir / "THEORY_CONSISTENCY_REPORT.md").is_file())


if __name__ == "__main__":
    unittest.main()

