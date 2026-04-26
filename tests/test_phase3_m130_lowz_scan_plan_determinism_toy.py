import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_scan_sigmatensor_lowz_joint.py"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class TestPhase3M130LowzScanPlanDeterminismToy(unittest.TestCase):
    def test_plan_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan_a = td_path / "plan_a.json"
            plan_b = td_path / "plan_b.json"
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--plan-out",
                str(plan_a),
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
                "-0.9",
                "--w0-steps",
                "2",
                "--lambda-min",
                "0.0",
                "--lambda-max",
                "0.2",
                "--lambda-steps",
                "2",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]
            proc_a = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))

            cmd[cmd.index(str(plan_a))] = str(plan_b)
            proc_b = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            self.assertEqual(_sha256(plan_a), _sha256(plan_b))


if __name__ == "__main__":
    unittest.main()
