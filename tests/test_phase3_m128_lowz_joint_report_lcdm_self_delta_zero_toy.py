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
from gsc.measurement_model import H0_to_SI, distance_modulus_flat
from gsc.structure.growth_factor import growth_observables_from_solution, solve_growth_ln_a
from gsc.theory.sigmatensor_v1 import SigmaTensorV1History, SigmaTensorV1Params, solve_sigmatensor_v1_background


def _make_toy_lowz_datasets(base: Path) -> tuple[Path, Path, Path]:
    params = SigmaTensorV1Params(
        H0_si=float(H0_to_SI(67.4)),
        Omega_m0=0.315,
        w_phi0=-1.0,
        lambda_=0.0,
        Omega_r0_override=0.0,
    )
    bg = solve_sigmatensor_v1_background(params, z_max=60.0, n_steps=4096)
    hist = SigmaTensorV1History(bg)

    bao_path = base / "toy_bao.csv"
    dv = D_V_flat(z=0.5, model=hist, n=500)
    with bao_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["type", "z", "dv_over_rd", "sigma_dv_over_rd", "values_path", "cov_path", "survey", "label", "source"])
        writer.writerow(["DV_over_rd", "0.5", f"{(dv / 145.0):.12e}", "1.0e-2", "", "", "toy", "toy", "toy"])

    sn_path = base / "toy_sn.csv"
    with sn_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["z", "mu", "sigma_mu"])
        for z in (0.1, 0.2, 0.3):
            mu = distance_modulus_flat(z=z, H_of_z=hist.H, n=300) + 0.1
            writer.writerow([f"{z:.6f}", f"{mu:.12e}", "5.0e-2"])

    def e_of_z(z: float) -> float:
        zz = float(z)
        if zz < 0.0:
            zz = 0.0
        return float(hist.E(zz))

    sol = solve_growth_ln_a(e_of_z, 0.315, z_start=50.0, z_targets=[0.5, 1.0, 2.0], n_steps=1024, eps_dlnH=1.0e-5)
    obs = growth_observables_from_solution(sol, [0.5, 1.0, 2.0])

    rsd_path = base / "toy_rsd.csv"
    with rsd_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["z", "fsigma8", "sigma", "omega_m_ref", "ref_key"])
        for z, g in zip(obs["z"], obs["g"]):
            writer.writerow([f"{z:.6f}", f"{(0.82 * float(g)):.12e}", "1.0e-2", "0.3", "toy"])

    return bao_path, sn_path, rsd_path


class TestPhase3M128LowzJointReportLcdmSelfDeltaZeroToy(unittest.TestCase):
    def test_lcdm_self_delta_near_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bao_path, sn_path, rsd_path = _make_toy_lowz_datasets(td_path)
            outdir = td_path / "out"

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
                    "--bao",
                    "1",
                    "--bao-data",
                    str(bao_path),
                    "--bao-n",
                    "500",
                    "--sn",
                    "1",
                    "--sn-data",
                    str(sn_path),
                    "--sn-n",
                    "300",
                    "--rsd",
                    "1",
                    "--rsd-data",
                    str(rsd_path),
                    "--sigma8-mode",
                    "nuisance",
                    "--z-start",
                    "50",
                    "--n-steps-growth",
                    "1024",
                    "--n-steps-bg",
                    "1024",
                    "--compare-lcdm",
                    "1",
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
            deltas = payload["deltas"]
            self.assertLessEqual(abs(float(deltas["delta_chi2_total"])), 1.0e-10)
            self.assertLessEqual(abs(float(deltas["delta_chi2_bao"])), 1.0e-10)
            self.assertLessEqual(abs(float(deltas["delta_chi2_sn"])), 1.0e-10)
            self.assertLessEqual(abs(float(deltas["delta_chi2_rsd"])), 1.0e-10)


if __name__ == "__main__":
    unittest.main()
