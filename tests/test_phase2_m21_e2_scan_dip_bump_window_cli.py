import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402


class TestPhase2M21E2ScanDipBumpWindowCLI(unittest.TestCase):
    def _write_priors(self, path: Path) -> None:
        pred = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        lines = ["name,value,sigma"]
        lines.append(f"100theta_star,{100.0 * float(pred['theta_star']):.16g},1e-3")
        lines.append(f"R,{float(pred['R']):.16g},1e-3")
        lines.append(f"lA,{float(pred['lA']):.16g},1e-2")
        lines.append("omega_b_h2,0.02237,5e-4")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_scan_cli_smoke_for_dip_bump_window(self):
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            priors_csv = td_path / "cmb.csv"
            out_dir = td_path / "out"
            self._write_priors(priors_csv)

            cmd = [
                sys.executable,
                str(script),
                "--model",
                "dip_bump_window",
                "--sampler",
                "random",
                "--n-samples",
                "3",
                "--seed",
                "17",
                "--grid",
                "H0=66.0:68.0",
                "--grid",
                "Omega_m=0.30:0.33",
                "--grid",
                "A_dip=0.2:0.6",
                "--grid",
                "A_bump=0.0:1.5",
                "--cmb",
                str(priors_csv),
                "--cmb-bridge-z",
                "5.0",
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--Neff",
                "3.046",
                "--Tcmb-K",
                "2.7255",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            jsonl_path = out_dir / "e2_scan_points.jsonl"
            summary_path = out_dir / "e2_scan_summary.json"
            self.assertTrue(jsonl_path.is_file())
            self.assertTrue(summary_path.is_file())

            lines = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 3)
            self.assertTrue(any(str(row.get("model")) == "dip_bump_window" for row in lines))
            for row in lines:
                self.assertEqual(row.get("model"), "dip_bump_window")
                params = row.get("params") or {}
                self.assertIn("A_dip", params)
                self.assertIn("A_bump", params)
                self.assertIn("drift", row)
                drift = row.get("drift") or {}
                self.assertIn("z_dot", drift)
                self.assertIn("min_z_dot", drift)
                self.assertIn("integrator", row)
                pred = row.get("cmb_pred") or {}
                tension = row.get("cmb_tension") or {}
                for key in ("R", "lA", "omega_b_h2"):
                    self.assertIn(key, pred)
                    self.assertTrue(math.isfinite(float(pred[key])))
                for key in (
                    "scale_D_from_R",
                    "scale_rs_from_lA_given_R",
                    "delta_D_pct",
                    "delta_rs_pct",
                    "dR_sigma_diag",
                    "dlA_sigma_diag",
                    "domega_sigma_diag",
                ):
                    self.assertIn(key, tension)
                    self.assertTrue(math.isfinite(float(tension[key])))
                micro = row.get("microphysics") or {}
                self.assertEqual(micro.get("mode"), "none")
                self.assertTrue(math.isfinite(float(micro.get("z_star_scale"))))
                self.assertTrue(math.isfinite(float(micro.get("r_s_scale"))))
                self.assertTrue(math.isfinite(float(micro.get("r_d_scale"))))
                self.assertIn("microphysics_knobs", row)
                self.assertIn("microphysics_plausible_ok", row)
                self.assertIn("microphysics_penalty", row)
                self.assertIn("microphysics_max_rel_dev", row)
                self.assertIn("microphysics_notes", row)
                self.assertTrue(bool(row["microphysics_plausible_ok"]))
                self.assertGreaterEqual(float(row["microphysics_max_rel_dev"]), 0.0)


if __name__ == "__main__":
    unittest.main()
