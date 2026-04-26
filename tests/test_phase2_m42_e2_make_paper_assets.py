import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_make_paper_assets.py"
DRIFT_DIR_NAME = "paper_assets_cmb_e2_drift_constrained_closure_bound"
KNOBS_DIR_NAME = "paper_assets_cmb_e2_closure_to_physical_knobs"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestPhase2M42E2MakePaperAssets(unittest.TestCase):
    def _write_jsonl_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "hash_a",
                "status": "ok",
                "model": "lcdm",
                "chi2_cmb": 2.0,
                "chi2": 10.0,
                "drift_metric": 0.5,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "robust_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.01,
                "params": {"H0": 67.0, "Omega_m": 0.31, "omega_b_h2": 0.0224, "omega_c_h2": 0.12, "N_eff": 3.046},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.02, "r_d_scale": 1.0},
            },
            {
                "params_hash": "hash_b",
                "status": "ok",
                "model": "lcdm",
                "chi2_cmb": 3.0,
                "chi2": 11.0,
                "drift_metric": 0.7,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "robust_ok": True,
                "microphysics_penalty": 0.1,
                "microphysics_max_rel_dev": 0.03,
                "params": {"H0": 68.0, "Omega_m": 0.30, "omega_b_h2": 0.0221, "omega_c_h2": 0.121, "N_eff": 3.10},
                "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.04, "r_d_scale": 0.99},
            },
            {
                "params_hash": "hash_c",
                "status": "ok",
                "model": "lcdm",
                "chi2_cmb": 2.5,
                "chi2": 10.5,
                "drift_metric": 0.4,
                "microphysics_plausible_ok": True,
                "robust_ok": True,
                "microphysics_penalty": 0.05,
                "microphysics_max_rel_dev": 0.02,
                "params": {"H0": 66.5, "Omega_m": 0.32, "omega_b_h2": 0.0225, "omega_c_h2": 0.119, "N_eff": 3.00},
                "microphysics_knobs": {"z_star_scale": 0.99, "r_s_scale": 1.01, "r_d_scale": 1.0},
            },
            {
                "params_hash": "hash_d",
                "status": "ok",
                "model": "lcdm",
                "chi2_cmb": 4.0,
                "chi2": 12.0,
                "drift_metric": 0.9,
                "microphysics_plausible_ok": False,
                "robust_ok": True,
                "params": {"H0": 69.0, "Omega_m": 0.29},
            },
            {
                "params_hash": "hash_e",
                "status": "ok",
                "model": "lcdm",
                "chi2_cmb": 1.8,
                "chi2": 9.5,
                "drift_metric": -0.1,
                "microphysics_plausible_ok": True,
                "robust_ok": True,
                "params": {"H0": 66.0, "Omega_m": 0.33},
            },
            {
                "params_hash": "hash_f",
                "status": "error",
                "model": "lcdm",
                "chi2_cmb": 1.0,
                "chi2": 8.0,
                "drift_metric": 0.8,
                "microphysics_plausible_ok": True,
                "robust_ok": True,
                "params": {"H0": 65.0, "Omega_m": 0.34},
            },
            {
                "params_hash": "hash_g",
                "status": "ok",
                "model": "lcdm",
                "chi2_parts": {"cmb_priors": {"chi2": 2.2}, "sn": {"chi2": 1.1}},
                "drift_metrics": {"metric": 0.6},
                "params": {"H0": 67.3, "Omega_m": 0.305, "omega_b_h2": 0.0222, "omega_c_h2": 0.1205, "N_eff": 3.20},
                "microphysics_knobs": {"z_star_scale": 1.015, "r_s_scale": 1.03, "r_d_scale": 1.01},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def test_mode_all_generates_expected_tables_and_monotonic_bound(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            outdir = td_path / "assets_all"
            self._write_jsonl_fixture(jsonl)

            proc = self._run(
                "--jsonl",
                str(jsonl),
                "--mode",
                "all",
                "--outdir",
                str(outdir),
                "--top-n",
                "4",
                "--closure-cut",
                "3.0",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            drift_dir = outdir / DRIFT_DIR_NAME
            knobs_dir = outdir / KNOBS_DIR_NAME
            self.assertTrue((drift_dir / "README.md").is_file())
            self.assertTrue((drift_dir / "manifest.json").is_file())
            self.assertTrue((drift_dir / "tables" / "pareto_front.csv").is_file())
            self.assertTrue((drift_dir / "tables" / "closure_bound_curve.csv").is_file())
            self.assertTrue((drift_dir / "tables" / "best_points_summary.csv").is_file())
            self.assertTrue((knobs_dir / "README.md").is_file())
            self.assertTrue((knobs_dir / "manifest.json").is_file())
            self.assertTrue((knobs_dir / "tables" / "top_models_knobs.csv").is_file())
            self.assertTrue((knobs_dir / "tables" / "knobs_summary_stats.csv").is_file())
            self.assertTrue((knobs_dir / "tables" / "knobs_table.tex").is_file())

            manifest = json.loads((drift_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("schema"), "phase2_e2_paper_assets_v1")
            input_paths = {str(item.get("path")) for item in manifest.get("inputs") or []}
            self.assertIn(str(jsonl.resolve()), input_paths)

            pareto_rows = _read_csv(drift_dir / "tables" / "pareto_front.csv")
            pareto_hashes = {row.get("params_hash") for row in pareto_rows}
            self.assertEqual(pareto_hashes, {"hash_a", "hash_b", "hash_g"})

            curve_rows = _read_csv(drift_dir / "tables" / "closure_bound_curve.csv")
            thresholds = [float(row["drift_threshold"]) for row in curve_rows]
            best_chi2 = [float(row["best_chi2_cmb"]) for row in curve_rows]
            self.assertEqual(thresholds, sorted(thresholds))
            for i in range(1, len(best_chi2)):
                self.assertGreaterEqual(best_chi2[i], best_chi2[i - 1] - 1e-12)

            top_rows = _read_csv(knobs_dir / "tables" / "top_models_knobs.csv")
            self.assertEqual([row["rank"] for row in top_rows], ["1", "2", "3", "4"])
            self.assertEqual(top_rows[0]["params_hash"], "hash_a")

    def test_mode_routing_and_deterministic_csv_outputs(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            self._write_jsonl_fixture(jsonl)

            drift_only = td_path / "drift_only"
            proc_drift = self._run(
                "--jsonl",
                str(jsonl),
                "--mode",
                "drift_closure_bound",
                "--outdir",
                str(drift_only),
            )
            out_drift = (proc_drift.stdout or "") + (proc_drift.stderr or "")
            self.assertEqual(proc_drift.returncode, 0, msg=out_drift)
            self.assertTrue((drift_only / "tables" / "pareto_front.csv").is_file())
            self.assertFalse((drift_only / "tables" / "top_models_knobs.csv").exists())

            knobs_only = td_path / "knobs_only"
            proc_knobs = self._run(
                "--jsonl",
                str(jsonl),
                "--mode",
                "closure_to_knobs",
                "--outdir",
                str(knobs_only),
            )
            out_knobs = (proc_knobs.stdout or "") + (proc_knobs.stderr or "")
            self.assertEqual(proc_knobs.returncode, 0, msg=out_knobs)
            self.assertTrue((knobs_only / "tables" / "top_models_knobs.csv").is_file())
            self.assertFalse((knobs_only / "tables" / "pareto_front.csv").exists())

            out_a = td_path / "all_a"
            out_b = td_path / "all_b"
            proc_a = self._run("--jsonl", str(jsonl), "--mode", "all", "--outdir", str(out_a), "--top-n", "4")
            proc_b = self._run("--jsonl", str(jsonl), "--mode", "all", "--outdir", str(out_b), "--top-n", "4")
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            compare_files = [
                out_a / DRIFT_DIR_NAME / "tables" / "pareto_front.csv",
                out_a / DRIFT_DIR_NAME / "tables" / "closure_bound_curve.csv",
                out_a / DRIFT_DIR_NAME / "tables" / "best_points_summary.csv",
                out_a / KNOBS_DIR_NAME / "tables" / "top_models_knobs.csv",
                out_a / KNOBS_DIR_NAME / "tables" / "knobs_summary_stats.csv",
                out_a / KNOBS_DIR_NAME / "tables" / "knobs_table.tex",
            ]
            for left in compare_files:
                right = Path(str(left).replace(str(out_a), str(out_b)))
                self.assertEqual(_sha256(left), _sha256(right), msg=str(left.name))


if __name__ == "__main__":
    unittest.main()
