from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = ROOT / "scripts" / "phase3_scan_sigmatensor_lowz_joint.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M130LowzScanPlanSchemaValidateAutoToy(unittest.TestCase):
    def test_plan_schema_validate_auto(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"

            proc_plan = subprocess.run(
                [
                    sys.executable,
                    str(SCAN_SCRIPT),
                    "--plan-out",
                    str(plan),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m-min",
                    "0.30",
                    "--Omega-m-max",
                    "0.31",
                    "--Omega-m-steps",
                    "2",
                    "--w0-min",
                    "-1.0",
                    "--w0-max",
                    "-1.0",
                    "--w0-steps",
                    "1",
                    "--lambda-min",
                    "0.0",
                    "--lambda-max",
                    "0.0",
                    "--lambda-steps",
                    "1",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_plan.returncode, 0, msg=(proc_plan.stdout or "") + (proc_plan.stderr or ""))

            proc_validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_SCRIPT),
                    "--auto",
                    "--json",
                    str(plan),
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
