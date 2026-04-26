import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import has_numpy  # noqa: E402


class TestPhase2M16E2ScanExtendedCosmoParams(unittest.TestCase):
    def _write_priors(self, path: Path) -> None:
        from gsc.early_time import compute_lcdm_distance_priors  # local import; numpy-tier

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

    def test_tiny_grid_emits_extended_cosmo_fields_and_priors_part(self):
        if not has_numpy():
            self.skipTest("numpy not installed (skipping numpy-tier test)")

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
                "lcdm",
                "--grid",
                "H0=67.4",
                "--grid",
                "Omega_m=0.315",
                "--grid",
                "omega_b_h2=0.0221,0.02237",
                "--grid",
                "N_eff=3.046",
                "--grid",
                "Y_p=0.245",
                "--cmb",
                str(priors_csv),
                "--omega-c-h2",
                "0.1200",
                "--Tcmb-K",
                "2.7255",
                "--gaussian-prior",
                "omega_b_h2=0.02237,0.0005",
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
            self.assertEqual(len(lines), 2)
            for row in lines:
                params = row.get("params") or {}
                self.assertIn("omega_b_h2", params)
                self.assertIn("omega_c_h2", params)
                self.assertIn("N_eff", params)
                self.assertIn("Y_p", params)
                chi2_parts = row.get("chi2_parts") or {}
                self.assertIn("priors", chi2_parts)
                self.assertIn("chi2", chi2_parts.get("priors") or {})

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            cfg = summary.get("config") or {}
            gp = cfg.get("gaussian_priors") or {}
            self.assertIn("omega_b_h2", gp)

    def test_pareto_report_backward_compat_for_old_and_new_jsonl(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            old_jsonl = td_path / "old.jsonl"
            new_jsonl = td_path / "new.jsonl"
            out_dir = td_path / "out"

            old_point = {
                "model": "lcdm",
                "params": {"H0": 67.4, "Omega_m": 0.315},
                "chi2_total": 5.0,
                "chi2_parts": {
                    "cmb": {"chi2": 5.0},
                    "drift": {"min_zdot_si": -1.0e-11, "sign_ok": False},
                    "invariants": {"ok": True},
                },
                "drift_pass": False,
                "invariants_ok": True,
            }
            new_point = {
                "model": "gsc_transition",
                "params": {
                    "H0": 68.0,
                    "Omega_m": 0.31,
                    "p": 0.6,
                    "z_transition": 1.2,
                    "omega_b_h2": 0.02237,
                    "omega_c_h2": 0.1200,
                    "N_eff": 3.046,
                    "Y_p": 0.245,
                },
                "chi2_total": 12.0,
                "chi2_parts": {
                    "cmb": {"chi2": 12.0},
                    "drift": {"min_zdot_si": 2.0e-11, "sign_ok": True},
                    "priors": {"chi2": 0.3},
                    "invariants": {"ok": True},
                },
                "drift": {
                    "z_list": [2.0, 3.0, 4.0, 5.0],
                    "z_dot": [2.0e-11, 2.2e-11, 2.1e-11, 2.0e-11],
                    "dv_cm_s_per_yr": [0.1, 0.2, 0.3, 0.4],
                    "min_z_dot": 2.0e-11,
                    "all_positive": True,
                },
                "drift_pass": True,
                "invariants_ok": True,
            }

            old_jsonl.write_text(json.dumps(old_point) + "\n", encoding="utf-8")
            new_jsonl.write_text(json.dumps(new_point) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(old_jsonl),
                "--jsonl",
                str(new_jsonl),
                "--show-params",
                "omega_b_h2,omega_c_h2,N_eff,Y_p",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            summary_path = out_dir / "pareto_summary.json"
            top_csv = out_dir / "pareto_top_positive.csv"
            self.assertTrue(summary_path.is_file())
            self.assertTrue(top_csv.is_file())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("n_total", -1)), 2)
            self.assertEqual((summary.get("config") or {}).get("show_params"), ["omega_b_h2", "omega_c_h2", "N_eff", "Y_p"])

            with top_csv.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                fieldnames = reader.fieldnames or []

            self.assertIn("omega_b_h2", fieldnames)
            self.assertIn("omega_c_h2", fieldnames)
            self.assertIn("N_eff", fieldnames)
            self.assertIn("Y_p", fieldnames)
            self.assertGreaterEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
