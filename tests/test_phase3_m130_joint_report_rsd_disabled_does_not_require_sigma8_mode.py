import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_joint_sigmatensor_lowz_report.py"


class TestPhase3M130JointReportRsdDisabledDoesNotRequireSigma8Mode(unittest.TestCase):
    def test_rsd_disabled_default_sigma8_mode_is_allowed(self) -> None:
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
                    "--bao",
                    "0",
                    "--sn",
                    "0",
                    "--rsd",
                    "0",
                    "--cmb",
                    "0",
                    "--compare-lcdm",
                    "0",
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
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            report_path = outdir / "LOWZ_JOINT_REPORT.json"
            self.assertTrue(report_path.is_file())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            rsd_block = payload.get("blocks", {}).get("rsd", {})
            self.assertEqual(rsd_block.get("enabled"), False)
            self.assertEqual(rsd_block.get("sigma8_mode"), "unused")


if __name__ == "__main__":
    unittest.main()
