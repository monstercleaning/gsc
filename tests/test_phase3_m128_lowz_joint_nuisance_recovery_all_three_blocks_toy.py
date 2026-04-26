import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_joint_sigmatensor_lowz_report.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import D_V_flat
from gsc.measurement_model import H0_to_SI, MPC_SI, distance_modulus_flat
from gsc.structure.growth_factor import growth_observables_from_solution, solve_growth_ln_a
from gsc.theory.sigmatensor_v1 import SigmaTensorV1History, SigmaTensorV1Params, solve_sigmatensor_v1_background


class TestPhase3M128LowzJointNuisanceRecoveryAllThreeBlocksToy(unittest.TestCase):
    def test_recovers_nuisances(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = td_path / "out"

            params = SigmaTensorV1Params(
                H0_si=float(H0_to_SI(67.4)),
                Omega_m0=0.3,
                w_phi0=-0.9,
                lambda_=0.4,
                Omega_r0_override=0.0,
            )
            bg = solve_sigmatensor_v1_background(params, z_max=60.0, n_steps=4096)
            hist = SigmaTensorV1History(bg)

            rd_true = 145.0 * MPC_SI
            delta_m_true = 0.11
            sigma8_true = 0.83

            bao_n = 500
            sn_n = 300
            z_start = 50.0
            n_steps_growth = 1024
            eps = 1.0e-5
            z_rsd = [0.5, 1.0, 2.0]

            bao_path = td_path / "toy_bao.csv"
            dv = D_V_flat(z=0.5, model=hist, n=bao_n)
            with bao_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["type", "z", "dv_over_rd", "sigma_dv_over_rd", "values_path", "cov_path", "survey", "label", "source"])
                writer.writerow(["DV_over_rd", "0.5", f"{(dv / rd_true):.12e}", "1.0e-2", "", "", "toy", "toy", "toy"])

            sn_path = td_path / "toy_sn.csv"
            with sn_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["z", "mu", "sigma_mu"])
                for z in (0.1, 0.2, 0.3):
                    mu = distance_modulus_flat(z=z, H_of_z=hist.H, n=sn_n) + delta_m_true
                    writer.writerow([f"{z:.6f}", f"{mu:.12e}", "5.0e-2"])

            def e_of_z(z: float) -> float:
                zz = float(z)
                if zz < 0.0:
                    zz = 0.0
                return float(hist.E(zz))

            sol = solve_growth_ln_a(
                e_of_z,
                0.3,
                z_start=z_start,
                z_targets=z_rsd,
                n_steps=n_steps_growth,
                eps_dlnH=eps,
            )
            obs = growth_observables_from_solution(sol, z_rsd)

            rsd_path = td_path / "toy_rsd.csv"
            with rsd_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["z", "fsigma8", "sigma", "omega_m_ref", "ref_key"])
                for z, g in zip(obs["z"], obs["g"]):
                    writer.writerow([f"{z:.6f}", f"{(sigma8_true * float(g)):.12e}", "1.0e-2", "0.3", "toy"])

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
                    "--bao",
                    "1",
                    "--bao-data",
                    str(bao_path),
                    "--bao-n",
                    str(bao_n),
                    "--sn",
                    "1",
                    "--sn-data",
                    str(sn_path),
                    "--sn-n",
                    str(sn_n),
                    "--rsd",
                    "1",
                    "--rsd-data",
                    str(rsd_path),
                    "--sigma8-mode",
                    "nuisance",
                    "--z-start",
                    str(z_start),
                    "--n-steps-growth",
                    str(n_steps_growth),
                    "--n-steps-bg",
                    "1024",
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

            payload = json.loads((outdir / "LOWZ_JOINT_REPORT.json").read_text(encoding="utf-8"))
            blocks = payload["blocks"]

            rd_fit = float(blocks["bao"]["rd_m_bestfit"])
            dm_fit = float(blocks["sn"]["delta_M_bestfit"])
            s8_fit = float(blocks["rsd"]["sigma8_0_bestfit"])
            chi2_total = float(payload["total"]["chi2"])

            self.assertLessEqual(abs(rd_fit - rd_true) / rd_true, 1.0e-3)
            self.assertLessEqual(abs(dm_fit - delta_m_true), 1.0e-3)
            self.assertLessEqual(abs(s8_fit - sigma8_true), 1.0e-3)
            self.assertLessEqual(abs(chi2_total), 1.0e-3)


if __name__ == "__main__":
    unittest.main()
