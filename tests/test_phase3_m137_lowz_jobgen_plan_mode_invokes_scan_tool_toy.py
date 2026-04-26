import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JOBGEN_SCRIPT = ROOT / "scripts" / "phase3_lowz_jobgen.py"


class TestPhase3M137LowzJobgenPlanModeInvokesScanToolToy(unittest.TestCase):
    def test_grid_plan_mode_writes_plan_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = td_path / "pack"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(JOBGEN_SCRIPT),
                    "--outdir",
                    str(outdir),
                    "--slices",
                    "1",
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m-min",
                    "0.31",
                    "--Omega-m-max",
                    "0.31",
                    "--Omega-m-steps",
                    "1",
                    "--w0-min",
                    "-0.95",
                    "--w0-max",
                    "-0.95",
                    "--w0-steps",
                    "1",
                    "--lambda-min",
                    "0.2",
                    "--lambda-max",
                    "0.2",
                    "--lambda-steps",
                    "1",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            plan_path = outdir / "plan" / "LOWZ_SCAN_PLAN.json"
            self.assertTrue(plan_path.is_file())

            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase3_sigmatensor_lowz_scan_plan_v1")
            points = payload.get("points")
            self.assertIsInstance(points, list)
            self.assertGreaterEqual(len(points), 1)


if __name__ == "__main__":
    unittest.main()
