import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402


class TestCMBCLIStub(unittest.TestCase):
    def test_fit_grid_accepts_cmb_for_lcdm(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cmb = tmp / "cmb.csv"
            out_dir = tmp / "out"

            pred = compute_lcdm_distance_priors(
                H0_km_s_Mpc=67.4,
                Omega_m=0.315,
                omega_b_h2=0.02237,
                omega_c_h2=0.1200,
                N_eff=3.046,
                Tcmb_K=2.7255,
            )
            cmb.write_text(
                "name,value,sigma\n"
                f"theta_star,{pred['theta_star']:.16g},1e-5\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "late_time_fit_grid.py"),
                "--model",
                "lcdm",
                "--cmb",
                str(cmb),
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
                "--out-dir",
                str(out_dir),
            ]
            env = os.environ.copy()
            env.setdefault("MPLBACKEND", "Agg")
            proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)

            self.assertEqual(proc.returncode, 0, msg=f"{proc.stdout}\n{proc.stderr}")
            self.assertTrue((out_dir / "lcdm_bestfit.json").exists())

    def test_fit_grid_rejects_cmb_for_non_lcdm(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cmb = tmp / "cmb.csv"
            out_dir = tmp / "out"
            cmb.write_text(
                "name,value,sigma\n"
                "theta_star,0.0104,0.000003\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "late_time_fit_grid.py"),
                "--model",
                "gsc_transition",
                "--cmb",
                str(cmb),
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--p-grid",
                "0.8",
                "--ztrans-grid",
                "1.0",
                "--Omega-m-grid",
                "0.315",
                "--H0-grid",
                "67.4",
                "--out-dir",
                str(out_dir),
            ]
            env = os.environ.copy()
            env.setdefault("MPLBACKEND", "Agg")
            proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("--cmb-bridge-z", f"{proc.stdout}\n{proc.stderr}")

    def test_fit_grid_accepts_cmb_for_non_lcdm_with_bridge(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cmb = tmp / "cmb.csv"
            out_dir = tmp / "out"
            # Very loose prior; this is only a wiring smoke test.
            cmb.write_text(
                "name,value,sigma\n"
                "theta_star,0.0104,1.0\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "late_time_fit_grid.py"),
                "--model",
                "gsc_transition",
                "--cmb",
                str(cmb),
                "--cmb-bridge-z",
                "5.0",
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
                "--p-grid",
                "0.8",
                "--ztrans-grid",
                "1.0",
                "--Omega-m-grid",
                "0.315",
                "--H0-grid",
                "67.4",
                "--out-dir",
                str(out_dir),
            ]
            env = os.environ.copy()
            env.setdefault("MPLBACKEND", "Agg")
            proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)

            self.assertEqual(proc.returncode, 0, msg=f"{proc.stdout}\n{proc.stderr}")
            self.assertTrue((out_dir / "gsc_transition_bestfit.json").exists())

    def test_scorecard_accepts_cmb_for_lcdm(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cmb = tmp / "cmb.csv"
            pred = compute_lcdm_distance_priors(
                H0_km_s_Mpc=67.4,
                Omega_m=0.315,
                omega_b_h2=0.02237,
                omega_c_h2=0.1200,
                N_eff=3.046,
                Tcmb_K=2.7255,
            )
            cmb.write_text(
                "name,value,sigma\n"
                f"theta_star,{pred['theta_star']:.16g},1e-5\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "late_time_scorecard.py"),
                "--model",
                "lcdm",
                "--cmb",
                str(cmb),
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--Neff",
                "3.046",
                "--Tcmb-K",
                "2.7255",
            ]
            env = os.environ.copy()
            env.setdefault("MPLBACKEND", "Agg")
            proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True)

            self.assertEqual(proc.returncode, 0, msg=f"{proc.stdout}\n{proc.stderr}")
            self.assertIn("cmb: chi2=", proc.stdout)


if __name__ == "__main__":
    unittest.main()
