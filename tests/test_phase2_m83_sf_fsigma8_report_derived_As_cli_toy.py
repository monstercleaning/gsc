import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_sf_fsigma8_report.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.structure.power_spectrum_linear import sigma8_0_from_As  # noqa: E402


class TestPhase2M83SFFSigma8ReportDerivedAsCliToy(unittest.TestCase):
    def test_derived_as_mode_chi2_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            csv_path = tmp / "toy.csv"

            As = 2.1e-9
            ns = 0.965
            kmin = 1.0e-4
            kmax = 1.0e1
            nk = 768

            def E_of_z(z: float) -> float:
                return (1.0 + float(z)) ** 1.5

            sigma8_true = sigma8_0_from_As(
                As=As,
                ns=ns,
                omega_m0=1.0,
                h=0.7,
                omega_b0=0.049,
                kmin=kmin,
                kmax=kmax,
                nk=nk,
                E_of_z=E_of_z,
                z_start=80.0,
                n_steps=3200,
            )

            z_vals = [0.0, 0.5, 1.0, 2.0, 3.0]
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["z", "fsigma8", "sigma"])
                for z in z_vals:
                    g = 1.0 / (1.0 + z)
                    w.writerow([f"{z}", f"{sigma8_true * g:.12f}", "0.1"])

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
                "--sigma8-mode",
                "derived_As",
                "--As",
                f"{As}",
                "--ns",
                f"{ns}",
                "--kmin",
                f"{kmin}",
                "--kmax",
                f"{kmax}",
                "--nk",
                f"{nk}",
                "--z-start",
                "80",
                "--n-steps",
                "3200",
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
            sigma8_meta = payload.get("sigma8") or {}
            self.assertEqual(sigma8_meta.get("mode"), "derived_As")
            self.assertIn("kmin", sigma8_meta)
            self.assertIn("kmax", sigma8_meta)
            self.assertIn("nk", sigma8_meta)

            data = payload.get("data") or {}
            self.assertEqual(int(data.get("n_points", -1)), len(z_vals))
            self.assertAlmostEqual(float(data.get("chi2", 1.0)), 0.0, delta=1.0e-6)
            self.assertTrue(math.isfinite(float(data.get("sigma8"))))

            rows = payload.get("rows") or []
            self.assertEqual(len(rows), len(z_vals))
            for z, row in zip(z_vals, rows):
                expected_g = 1.0 / (1.0 + z)
                self.assertAlmostEqual(float(row.get("z")), z, delta=1.0e-12)
                self.assertAlmostEqual(float(row.get("g")), expected_g, delta=2.0e-3)

            run2 = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out2 = (run2.stdout or "") + (run2.stderr or "")
            self.assertEqual(run2.returncode, 0, msg=out2)
            self.assertEqual(run1.stdout, run2.stdout)

    def test_invalid_data_columns_exit_code_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bad_csv = tmp / "bad.csv"
            bad_csv.write_text("z,fsigma8\n0.0,0.4\n", encoding="utf-8")

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
                "--sigma8-mode",
                "derived_As",
                "--As",
                "2.1e-9",
                "--ns",
                "0.965",
                "--data",
                str(bad_csv),
                "--format",
                "json",
            ]

            run = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            msg = (run.stdout or "") + (run.stderr or "")
            self.assertEqual(run.returncode, 2, msg=msg)
            self.assertIn("z,fsigma8,sigma", msg)


if __name__ == "__main__":
    unittest.main()
