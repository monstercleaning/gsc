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


class TestPhase2M12E2ScanSamplers(unittest.TestCase):
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

    def _run_random_scan(self, *, priors_csv: Path, out_dir: Path) -> subprocess.CompletedProcess[str]:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--sampler",
            "random",
            "--n-samples",
            "10",
            "--seed",
            "123",
            "--grid",
            "H0=67.0:67.8",
            "--grid",
            "Omega_m=0.30:0.33",
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
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_random_sampler_is_deterministic_and_writes_jsonl_contract(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            priors_csv = td_path / "cmb.csv"
            self._write_priors(priors_csv)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            proc_a = self._run_random_scan(priors_csv=priors_csv, out_dir=out_a)
            out_text_a = (proc_a.stdout or "") + (proc_a.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=out_text_a)

            proc_b = self._run_random_scan(priors_csv=priors_csv, out_dir=out_b)
            out_text_b = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_b.returncode, 0, msg=out_text_b)

            jsonl_a = out_a / "e2_scan_points.jsonl"
            jsonl_b = out_b / "e2_scan_points.jsonl"
            csv_a = out_a / "e2_scan_points.csv"
            summary_a = out_a / "e2_scan_summary.json"
            self.assertTrue(jsonl_a.is_file())
            self.assertTrue(jsonl_b.is_file())
            self.assertTrue(csv_a.is_file())
            self.assertTrue(summary_a.is_file())

            lines_a = jsonl_a.read_text(encoding="utf-8").splitlines()
            lines_b = jsonl_b.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines_a, lines_b)
            self.assertEqual(len(lines_a), 10)

            first = json.loads(lines_a[0])
            self.assertIn("params", first)
            self.assertIn("chi2_total", first)
            self.assertIn("chi2_parts", first)
            self.assertIn("cmb", first["chi2_parts"])
            self.assertIn("drift", first["chi2_parts"])
            self.assertIn("drift", first)
            self.assertIn("z_list", first["drift"])
            self.assertIn("z_dot", first["drift"])
            self.assertIn("dv_cm_s_per_yr", first["drift"])
            self.assertIn("min_z_dot", first["drift"])
            self.assertIn("cmb_pred", first)
            self.assertIn("cmb_tension", first)
            self.assertIn("microphysics", first)

            for row in (json.loads(line) for line in lines_a):
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
                self.assertAlmostEqual(float(row["microphysics_penalty"]), 0.0, places=12)
                self.assertGreaterEqual(float(row["microphysics_max_rel_dev"]), 0.0)

            summary = json.loads(summary_a.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("n_total", -1)), 10)
            cfg = summary.get("config") or {}
            self.assertEqual(cfg.get("sampler"), "random")
            self.assertEqual(int(cfg.get("seed", -1)), 123)
            sampler_cfg = cfg.get("sampler_config") or {}
            self.assertEqual(int(sampler_cfg.get("n_requested", -1)), 10)
            self.assertEqual(int(sampler_cfg.get("n_evaluated", -1)), 10)


if __name__ == "__main__":
    unittest.main()
