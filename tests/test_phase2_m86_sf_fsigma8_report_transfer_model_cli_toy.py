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


class TestPhase2M86SFFSigma8ReportTransferModelCliToy(unittest.TestCase):
    def test_derived_as_with_eh98_transfer_alias(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            csv_path = tmp / "toy_eh98.csv"

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
                transfer_model="eh98_nowiggle",
                omega_b0=0.049,
                kmin=kmin,
                kmax=kmax,
                nk=nk,
                E_of_z=E_of_z,
                z_start=80.0,
                n_steps=3200,
            )

            z_vals = [0.0, 0.5, 1.0, 2.0]
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
                "--transfer-model",
                "eh98",
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
            self.assertEqual(payload.get("transfer_model"), "eh98_nowiggle")

            sigma8_meta = payload.get("sigma8") or {}
            self.assertEqual(sigma8_meta.get("transfer_model"), "eh98_nowiggle")
            self.assertIn("no-wiggle", str(sigma8_meta.get("transfer_model_notes", "")))

            data = payload.get("data") or {}
            self.assertEqual(int(data.get("n_points", -1)), len(z_vals))
            self.assertAlmostEqual(float(data.get("chi2", 1.0)), 0.0, delta=1.0e-6)
            self.assertTrue(math.isfinite(float(data.get("sigma8"))))

            run2 = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out2 = (run2.stdout or "") + (run2.stderr or "")
            self.assertEqual(run2.returncode, 0, msg=out2)
            self.assertEqual(run1.stdout, run2.stdout)


if __name__ == "__main__":
    unittest.main()

