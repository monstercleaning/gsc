import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_sf_sigmatensor_fsigma8_report.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI
from gsc.structure.power_spectrum_linear import fsigma8, sigma8_0_from_As
from gsc.theory.sigmatensor_v1 import SigmaTensorV1History, SigmaTensorV1Params, solve_sigmatensor_v1_background


class TestPhase3M127Fsigma8MatchesPowerSpectrumLinearHelperLCDMLimitToy(unittest.TestCase):
    def test_matches_helper_in_lcdm_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = td_path / "report"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.315",
                    "--w0",
                    "-1.0",
                    "--lambda",
                    "0.0",
                    "--Omega-r0-override",
                    "0.0",
                    "--sigma8-mode",
                    "derived_As",
                    "--As",
                    "2.1e-9",
                    "--ns",
                    "0.965",
                    "--transfer-model",
                    "bbks",
                    "--z-start",
                    "50",
                    "--n-steps-growth",
                    "600",
                    "--n-steps-bg",
                    "2048",
                    "--rsd",
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

            report = json.loads((outdir / "FSIGMA8_REPORT.json").read_text(encoding="utf-8"))
            rows = report["grids"]["rows"]
            z1_row = next(row for row in rows if abs(float(row["z"]) - 1.0) < 1.0e-12)
            fs8_report = float(z1_row["fsigma8"])

            z_max_bg = float(report["background_summary"]["z_max_bg_effective"])
            params = SigmaTensorV1Params(
                H0_si=float(H0_to_SI(67.4)),
                Omega_m0=0.315,
                w_phi0=-1.0,
                lambda_=0.0,
                Omega_r0_override=0.0,
            )
            bg = solve_sigmatensor_v1_background(params, z_max=z_max_bg, n_steps=2048)
            hist = SigmaTensorV1History(bg)

            def e_of_z(z: float) -> float:
                zz = float(z)
                if zz < 0.0:
                    zz = 0.0
                return float(hist.E(zz))

            sigma8_0 = sigma8_0_from_As(
                As=2.1e-9,
                ns=0.965,
                omega_m0=0.315,
                h=0.674,
                transfer_model="bbks",
                omega_b0=0.049,
                k0_mpc=0.05,
                E_of_z=e_of_z,
                z_start=50.0,
                n_steps=600,
                eps_dlnH=1.0e-5,
            )
            fs8_helper = fsigma8(
                1.0,
                sigma8_0=sigma8_0,
                omega_m0=0.315,
                E_of_z=e_of_z,
                z_start=50.0,
                n_steps=600,
                eps_dlnH=1.0e-5,
            )

            rel = abs(fs8_report - fs8_helper) / max(abs(fs8_helper), 1.0e-15)
            self.assertLessEqual(rel, 1.0e-5)


if __name__ == "__main__":
    unittest.main()
