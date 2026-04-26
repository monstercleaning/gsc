import csv
import json
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
from gsc.structure.growth_factor import growth_observables_from_solution, solve_growth_ln_a
from gsc.theory.sigmatensor_v1 import SigmaTensorV1History, SigmaTensorV1Params, solve_sigmatensor_v1_background


class TestPhase3M127RsdNuisanceProfileRecoversScaleToy(unittest.TestCase):
    def test_nuisance_profile_recovers_known_scale(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            data_csv = td_path / "toy_rsd.csv"
            outdir = td_path / "report"

            z_points = [0.5, 1.0, 2.0]
            s_true = 0.82
            sigma = 0.01

            params = SigmaTensorV1Params(
                H0_si=float(H0_to_SI(67.4)),
                Omega_m0=0.3,
                w_phi0=-0.9,
                lambda_=0.4,
                Omega_r0_override=0.0,
            )
            bg = solve_sigmatensor_v1_background(params, z_max=50.01, n_steps=2048)
            hist = SigmaTensorV1History(bg)

            def e_of_z(z: float) -> float:
                zz = float(z)
                if zz < 0.0:
                    zz = 0.0
                return float(hist.E(zz))

            sol = solve_growth_ln_a(
                e_of_z,
                0.3,
                z_start=50.0,
                z_targets=z_points,
                n_steps=600,
                eps_dlnH=1.0e-5,
            )
            obs = growth_observables_from_solution(sol, z_points)

            with data_csv.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["z", "fsigma8", "sigma", "omega_m_ref", "ref_key"])
                for z, g in zip(obs["z"], obs["g"]):
                    writer.writerow([f"{z:.6f}", f"{(s_true * float(g)):.12e}", f"{sigma:.12e}", "0.3", "toy"])

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.3",
                    "--w0",
                    "-0.9",
                    "--lambda",
                    "0.4",
                    "--Omega-r0-override",
                    "0.0",
                    "--sigma8-mode",
                    "nuisance",
                    "--rsd",
                    "1",
                    "--data",
                    str(data_csv),
                    "--ap-correction",
                    "0",
                    "--z-start",
                    "50",
                    "--n-steps-growth",
                    "600",
                    "--n-steps-bg",
                    "2048",
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
            sigma8_best = float(report["sigma8"]["sigma8_0_bestfit"])
            chi2 = float(report["rsd"]["chi2"])
            self.assertLessEqual(abs(sigma8_best - s_true), 5.0e-6)
            self.assertLessEqual(abs(chi2), 1.0e-6)


if __name__ == "__main__":
    unittest.main()
