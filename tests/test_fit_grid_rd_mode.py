import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestFitGridRDMode(unittest.TestCase):
    def test_rd_mode_early_wires_into_output(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not available")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bao_csv = tmp / "bao.csv"
            out_dir = tmp / "out"
            bao_csv.write_text(
                "type,z,dv_over_rd,sigma_dv_over_rd,label\n"
                "DV_over_rd,0.1,3.0,0.1,T1\n"
                "DV_over_rd,0.2,4.0,0.1,T2\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "late_time_fit_grid.py"),
                "--model",
                "lcdm",
                "--bao",
                str(bao_csv),
                "--rd-mode",
                "early",
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--H0-grid",
                "67.4",
                "--Omega-m-grid",
                "0.315",
                "--n-grid",
                "600",
                "--top-k",
                "5",
                "--out-dir",
                str(out_dir),
            ]
            env = os.environ.copy()
            env.setdefault("MPLBACKEND", "Agg")
            subprocess.check_call(cmd, cwd=str(ROOT), env=env)

            p = out_dir / "lcdm_bestfit.json"
            self.assertTrue(p.exists())
            obj = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(obj.get("rd", {}).get("rd_mode"), "early")
            self.assertGreater(float(obj.get("rd", {}).get("rd_Mpc", 0.0)), 0.0)
            self.assertEqual(obj["best"]["parts"]["bao"]["rd_fit_mode"], "fixed")


if __name__ == "__main__":
    unittest.main()

