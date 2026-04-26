import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time import compute_lcdm_shift_params  # noqa: E402


def _write_cmb_csv(path: Path, rows: list[tuple[str, float, float]]) -> None:
    lines = ["name,value,sigma"]
    for key, value, sigma in rows:
        lines.append(f"{key},{value:.16g},{sigma:.16g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_fit_grid(*, cmb_csv: Path, out_dir: Path) -> dict:
    script = ROOT / "scripts" / "late_time_fit_grid.py"
    cmd = [
        sys.executable,
        str(script),
        "--model",
        "lcdm",
        "--cmb",
        str(cmb_csv),
        "--cmb-mode",
        "theta_star",
        "--omega-b-h2",
        "0.02237",
        "--omega-c-h2",
        "0.1200",
        "--Neff",
        "3.046",
        "--Tcmb-K",
        "2.7255",
        "--H0-grid",
        "67.4",
        "--Omega-m-grid",
        "0.315",
        "--n-grid",
        "512",
        "--top-k",
        "1",
        "--out-dir",
        str(out_dir),
    ]
    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise AssertionError(out)
    bestfit = out_dir / "lcdm_bestfit.json"
    if not bestfit.is_file():
        raise AssertionError(f"missing bestfit output: {bestfit}")
    return json.loads(bestfit.read_text(encoding="utf-8"))


def _run_early_time_cli(*, cmb_csv: Path, out_dir: Path) -> dict:
    script = ROOT / "scripts" / "early_time_cmb_priors_chi2.py"
    cmd = [
        sys.executable,
        str(script),
        "--cmb",
        str(cmb_csv),
        "--omega-b-h2",
        "0.02237",
        "--omega-c-h2",
        "0.1200",
        "--out-dir",
        str(out_dir),
    ]
    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise AssertionError(out)
    report = out_dir / "early_time" / "cmb_priors_report.json"
    if not report.is_file():
        raise AssertionError(f"missing report output: {report}")
    return json.loads(report.read_text(encoding="utf-8"))


class TestPhase2M3CMBPriorsIntegration(unittest.TestCase):
    def test_fit_grid_writes_cmb_predicted_keys_and_values(self):
        pred = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cmb_csv = tmp / "cmb.csv"
            out_dir = tmp / "out"
            _write_cmb_csv(
                cmb_csv,
                [
                    ("theta_star", float(pred["theta_star"]), 1e-5),
                    ("R", float(pred["R"]), 1e-3),
                ],
            )
            payload = _run_fit_grid(cmb_csv=cmb_csv, out_dir=out_dir)

        cmb = payload["best"]["parts"]["cmb"]
        self.assertIn("predicted", cmb)
        self.assertIn("keys_used", cmb)
        self.assertEqual(cmb["keys_used"], ["theta_star", "R"])
        self.assertIn("theta_star", cmb["predicted"])
        self.assertIn("R", cmb["predicted"])
        self.assertTrue(float(cmb["chi2"]) < 1.0e-10)
        self.assertEqual(int(cmb["ndof"]), 2)
        self.assertEqual(cmb["method"], "diag")

    def test_fit_grid_supports_100theta_star_alias_end_to_end(self):
        pred = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cmb_csv = tmp / "cmb_alias.csv"
            out_dir = tmp / "out"
            _write_cmb_csv(
                cmb_csv,
                [
                    ("100theta_star", 100.0 * float(pred["theta_star"]), 1e-3),
                ],
            )
            payload = _run_fit_grid(cmb_csv=cmb_csv, out_dir=out_dir)

        cmb = payload["best"]["parts"]["cmb"]
        self.assertEqual(cmb["keys_used"], ["100theta_star"])
        self.assertIn("100theta_star", cmb["predicted"])
        self.assertTrue(float(cmb["chi2"]) < 1.0e-10)
        self.assertEqual(int(cmb["ndof"]), 1)

    def test_fit_grid_and_early_time_cli_agree_for_same_priors(self):
        pred = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cmb_csv = tmp / "cmb.csv"
            _write_cmb_csv(
                cmb_csv,
                [
                    ("theta_star", float(pred["theta_star"]), 1e-5),
                    ("R", float(pred["R"]), 1e-3),
                ],
            )
            fit_payload = _run_fit_grid(cmb_csv=cmb_csv, out_dir=tmp / "fit")
            cli_payload = _run_early_time_cli(cmb_csv=cmb_csv, out_dir=tmp / "early")

        fit_chi2 = float(fit_payload["best"]["parts"]["cmb"]["chi2"])
        cli_chi2 = float(cli_payload["result"]["chi2"])
        self.assertAlmostEqual(fit_chi2, cli_chi2, places=12)


if __name__ == "__main__":
    unittest.main()
