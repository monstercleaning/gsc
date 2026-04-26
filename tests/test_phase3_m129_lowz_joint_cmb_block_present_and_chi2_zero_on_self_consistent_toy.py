import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_joint_sigmatensor_lowz_report.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.early_time import compute_bridged_distance_priors
from gsc.measurement_model import H0_to_SI
from gsc.theory.sigmatensor_v1 import SigmaTensorV1History, SigmaTensorV1Params, solve_sigmatensor_v1_background


def _require_numpy_or_skip(tc: unittest.TestCase) -> None:
    try:
        import numpy  # noqa: F401
    except Exception:
        tc.skipTest("numpy not installed")


def _write_self_consistent_cmb_priors(
    *,
    outdir: Path,
    H0_km_s_Mpc: float,
    omega_m0: float,
    w0: float,
    lambda_: float,
    z_bridge: float,
    omega_b_h2: float,
    Tcmb_K: float = 2.7255,
    N_eff: float = 3.046,
    z_start: float = 50.0,
    eps_dlnH: float = 1.0e-5,
    n_steps_bg: int = 1024,
) -> tuple[Path, Path, float]:
    h = float(H0_km_s_Mpc) / 100.0
    omega_c_h2 = float(omega_m0 * h * h - omega_b_h2)
    if omega_c_h2 < 0.0:
        raise ValueError("toy setup requires non-negative omega_c_h2")

    z_needed = float(z_start + (1.0 + z_start) * (3.0 * eps_dlnH) + 1.0e-3)
    z_max_bg = max(float(z_bridge) + 1.0e-6, z_needed)
    params = SigmaTensorV1Params(
        H0_si=float(H0_to_SI(H0_km_s_Mpc)),
        Omega_m0=float(omega_m0),
        w_phi0=float(w0),
        lambda_=float(lambda_),
    )
    bg = solve_sigmatensor_v1_background(params, z_max=z_max_bg, n_steps=int(n_steps_bg))
    hist = SigmaTensorV1History(bg)
    pred = compute_bridged_distance_priors(
        model=hist,
        z_bridge=float(z_bridge),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(N_eff),
        Tcmb_K=float(Tcmb_K),
        integrator="trap",
        integration_eps_abs=1.0e-10,
        integration_eps_rel=1.0e-10,
        rs_star_calibration=1.0,
        dm_star_calibration=1.0,
    )

    priors_path = outdir / "toy_cmb_priors.csv"
    cov_path = outdir / "toy_cmb_priors.cov"
    rows = [
        ("R", float(pred["R"]), 1.0e-3),
        ("lA", float(pred["lA"]), 1.0e-1),
        ("omega_b_h2", float(pred["omega_b_h2"]), 1.0e-4),
    ]
    with priors_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "value", "sigma"])
        for name, value, sigma in rows:
            writer.writerow([name, f"{value:.12e}", f"{sigma:.12e}"])

    vals = [
        rows[0][2] ** 2,
        0.0,
        0.0,
        0.0,
        rows[1][2] ** 2,
        0.0,
        0.0,
        0.0,
        rows[2][2] ** 2,
    ]
    with cov_path.open("w", encoding="utf-8") as fh:
        fh.write("3\n")
        for i in range(0, len(vals), 3):
            fh.write(" ".join(f"{v:.12e}" for v in vals[i : i + 3]) + "\n")
    return priors_path, cov_path, float(omega_c_h2)


class TestPhase3M129LowzJointCmbBlockPresentAndChi2ZeroOnSelfConsistentToy(unittest.TestCase):
    def test_cmb_block_self_consistent(self) -> None:
        _require_numpy_or_skip(self)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = td_path / "out"
            priors_path, cov_path, _ = _write_self_consistent_cmb_priors(
                outdir=td_path,
                H0_km_s_Mpc=67.4,
                omega_m0=0.315,
                w0=-0.95,
                lambda_=0.4,
                z_bridge=5.0,
                omega_b_h2=0.02237,
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.315",
                    "--w0",
                    "-0.95",
                    "--lambda",
                    "0.4",
                    "--bao",
                    "0",
                    "--sn",
                    "0",
                    "--rsd",
                    "0",
                    "--compare-lcdm",
                    "0",
                    "--cmb",
                    "1",
                    "--cmb-priors",
                    str(priors_path),
                    "--cmb-cov",
                    str(cov_path),
                    "--cmb-z-bridge",
                    "5.0",
                    "--omega-b-h2",
                    "0.02237",
                    "--z-start",
                    "50",
                    "--n-steps-bg",
                    "1024",
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
            cmb = payload["blocks"]["cmb"]
            self.assertTrue(bool(cmb["enabled"]))
            self.assertLessEqual(abs(float(cmb["chi2"])), 1.0e-10)
            self.assertEqual(cmb["priors_basename"], priors_path.name)
            self.assertEqual(cmb["cov_basename"], cov_path.name)

            for rel in ("LOWZ_JOINT_REPORT.json", "LOWZ_JOINT_REPORT.md"):
                text = (outdir / rel).read_text(encoding="utf-8")
                for token in ABS_TOKENS:
                    self.assertNotIn(token, text, msg=f"absolute token leaked in {rel}: {token}")


if __name__ == "__main__":
    unittest.main()
