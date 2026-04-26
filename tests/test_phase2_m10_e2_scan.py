import csv
import json
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


class TestPhase2M10E2Scan(unittest.TestCase):
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
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_scan_writes_points_csv_and_summary_json(self):
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            priors_csv = td_p / "cmb.csv"
            self._write_priors(priors_csv)
            out_dir = td_p / "out"

            cmd = [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--grid",
                "H0=67.4",
                "--grid",
                "Omega_m=0.315",
                "--cmb",
                str(priors_csv),
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

            points = out_dir / "e2_scan_points.csv"
            summary = out_dir / "e2_scan_summary.json"
            self.assertTrue(points.is_file())
            self.assertTrue(summary.is_file())

            with points.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                rows = list(reader)

            required = {
                "model",
                "chi2_cmb",
                "drift_pass",
                "H0",
                "Omega_m",
                "p",
                "z_transition",
                "cmb_bridge_z",
                "theta_star",
                "lA",
                "R",
                "z_star",
                "r_s_star_Mpc",
                "D_M_star_Mpc",
                "bridge_H_ratio",
            }
            self.assertTrue(required.issubset(set(fieldnames)))
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(float(rows[0]["chi2_cmb"]), 0.0, places=6)

            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(int(payload.get("n_total", -1)), 1)
            self.assertEqual(int(payload.get("n_drift_pass", -1)), 0)
            self.assertIsNotNone(payload.get("best_overall"))
            self.assertIsNone(payload.get("best_drift_pass"))
            self.assertIsNotNone(payload.get("best_drift_fail"))


if __name__ == "__main__":
    unittest.main()
