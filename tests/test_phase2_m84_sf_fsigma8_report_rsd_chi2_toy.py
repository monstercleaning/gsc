import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_sf_fsigma8_report.py"


class TestPhase2M84SFFSigma8ReportRsdChi2Toy(unittest.TestCase):
    def test_rsd_profile_mode_recovers_sigma8_and_zero_chi2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rsd_csv = tmp / "rsd_toy.csv"

            sigma8_true = 0.8
            z_vals = [0.5, 1.0, 2.0]
            with rsd_csv.open("w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["z", "fsigma8", "sigma", "omega_m_ref", "ref_key"])
                for i, z in enumerate(z_vals):
                    g = 1.0 / (1.0 + z)
                    w.writerow([f"{z}", f"{sigma8_true * g:.12f}", "0.1", "1.0", f"toy_{i}"])

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
                "--rsd",
                "--rsd-data",
                str(rsd_csv),
                "--format",
                "json",
            ]

            run = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out = (run.stdout or "") + (run.stderr or "")
            self.assertEqual(run.returncode, 0, msg=out)

            payload = json.loads(run.stdout)
            rsd = payload.get("rsd_fsigma8") or {}
            self.assertTrue(bool(rsd.get("enabled")))
            self.assertEqual(int(rsd.get("n_points", -1)), len(z_vals))
            self.assertTrue(bool(rsd.get("fit_sigma8")))
            self.assertAlmostEqual(float(rsd.get("sigma8_0_bestfit")), sigma8_true, delta=1.0e-3)
            self.assertAlmostEqual(float(rsd.get("chi2_min")), 0.0, delta=1.0e-8)

    def test_invalid_rsd_csv_returns_exit_code_1(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rsd_csv = tmp / "bad.csv"
            rsd_csv.write_text("z,fsigma8,sigma\n0.5,0.4,0.1\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--history",
                "lcdm",
                "--H0",
                "70",
                "--Omega-m",
                "0.3",
                "--Omega-lambda",
                "0.7",
                "--rsd",
                "--rsd-data",
                str(rsd_csv),
                "--format",
                "json",
            ]

            run = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out = (run.stdout or "") + (run.stderr or "")
            self.assertEqual(run.returncode, 1, msg=out)
            self.assertIn("required columns", out)


if __name__ == "__main__":
    unittest.main()
