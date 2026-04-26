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

from gsc.early_time import compute_bridged_distance_priors
from gsc.measurement_model import H0_to_SI
from gsc.theory.sigmatensor_v1 import SigmaTensorV1History, SigmaTensorV1Params, solve_sigmatensor_v1_background


def _require_numpy_or_skip(tc: unittest.TestCase) -> None:
    try:
        import numpy  # noqa: F401
    except Exception:
        tc.skipTest("numpy not installed")


def _make_toy_cmb_priors_and_cov(base: Path) -> tuple[Path, Path]:
    H0 = 67.4
    omega_m0 = 0.315
    w0 = -1.0
    lambda_ = 0.0
    z_bridge = 5.0
    omega_b_h2 = 0.02237
    z_start = 50.0
    eps = 1.0e-5
    n_steps_bg = 1024

    h = H0 / 100.0
    omega_c_h2 = omega_m0 * h * h - omega_b_h2
    z_max_bg = max(z_bridge + 1.0e-6, z_start + (1.0 + z_start) * (3.0 * eps) + 1.0e-3)
    params = SigmaTensorV1Params(
        H0_si=float(H0_to_SI(H0)),
        Omega_m0=float(omega_m0),
        w_phi0=float(w0),
        lambda_=float(lambda_),
    )
    bg = solve_sigmatensor_v1_background(params, z_max=z_max_bg, n_steps=n_steps_bg)
    hist = SigmaTensorV1History(bg)
    pred = compute_bridged_distance_priors(
        model=hist,
        z_bridge=z_bridge,
        omega_b_h2=omega_b_h2,
        omega_c_h2=float(omega_c_h2),
        N_eff=3.046,
        Tcmb_K=2.7255,
    )

    priors_path = base / "toy_cmb_priors.csv"
    cov_path = base / "toy_cmb_priors.cov"
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

    mat = [
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
        for i in range(0, len(mat), 3):
            fh.write(" ".join(f"{v:.12e}" for v in mat[i : i + 3]) + "\n")
    return priors_path, cov_path


class TestPhase3M129LowzJointLcdmSelfDeltaZeroWithCmbEnabledToy(unittest.TestCase):
    def test_lcdm_self_delta_with_cmb_enabled(self) -> None:
        _require_numpy_or_skip(self)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            priors_path, cov_path = _make_toy_cmb_priors_and_cov(td_path)
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
                    "--bao",
                    "0",
                    "--sn",
                    "0",
                    "--rsd",
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
                    "--compare-lcdm",
                    "1",
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
            deltas = payload["deltas"]
            self.assertLessEqual(abs(float(deltas["delta_chi2_total"])), 1.0e-10)
            self.assertLessEqual(abs(float(deltas["delta_chi2_cmb"])), 1.0e-10)


if __name__ == "__main__":
    unittest.main()
