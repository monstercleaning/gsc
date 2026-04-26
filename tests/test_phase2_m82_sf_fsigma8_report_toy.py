import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_sf_fsigma8_report.py"


class TestPhase2M82SFFSigma8ReportToy(unittest.TestCase):
    def test_eds_sigma8_profile_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            csv_path = tmp / "toy_fsigma8.csv"

            z_vals = [0.0, 0.5, 1.0, 2.0]
            sigma8_true = 0.8
            sigma_obs = 1.0e-4

            with csv_path.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["z", "fsigma8", "sigma"])
                for z in z_vals:
                    g = 1.0 / (1.0 + z)
                    w.writerow([f"{z}", f"{sigma8_true * g:.12f}", f"{sigma_obs}"])

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--history",
                "lcdm",
                "--H0",
                "70",
                "--Omega-m",
                "1",
                "--Omega-lambda",
                "0",
                "--data",
                str(csv_path),
                "--format",
                "json",
            ]

            run1 = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out1 = (run1.stdout or "") + (run1.stderr or "")
            self.assertEqual(run1.returncode, 0, msg=out1)

            payload = json.loads(run1.stdout)
            self.assertEqual(payload.get("tool"), "phase2_sf_fsigma8_report_v1")
            data = payload.get("data") or {}
            self.assertAlmostEqual(float(data.get("sigma8")), sigma8_true, delta=1.0e-3)
            self.assertAlmostEqual(float(data.get("chi2")), 0.0, delta=1.0e-2)

            rows = payload.get("rows") or []
            self.assertEqual(len(rows), len(z_vals))
            for z, row in zip(z_vals, rows):
                self.assertAlmostEqual(float(row.get("z")), z, delta=1.0e-12)
                expected_g = 1.0 / (1.0 + z)
                self.assertAlmostEqual(float(row.get("g")), expected_g, delta=2.0e-3)

            run2 = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out2 = (run2.stdout or "") + (run2.stderr or "")
            self.assertEqual(run2.returncode, 0, msg=out2)
            self.assertEqual(run1.stdout, run2.stdout)


if __name__ == "__main__":
    unittest.main()
