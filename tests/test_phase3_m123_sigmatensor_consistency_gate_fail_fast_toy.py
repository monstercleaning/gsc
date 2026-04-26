from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_st_sigmatensor_consistency_report.py"


class TestPhase3M123SigmaTensorConsistencyGateFailFastToy(unittest.TestCase):
    def test_invalid_precondition_returns_exit_2_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.99999",
                    "--w0",
                    "-0.9",
                    "--lambda",
                    "0.5",
                    "--Omega-r0-override",
                    "0.01",
                    "--z-max",
                    "10",
                    "--n-steps",
                    "256",
                    "--outdir",
                    str(outdir),
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            combined = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=combined)
            self.assertIn("PHASE3_SIGMATENSOR_CONSISTENCY_FAILED", combined)


if __name__ == "__main__":
    unittest.main()
