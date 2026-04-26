import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _sample(*, chi2: float, plausible: bool, penalty: float, note: str) -> dict:
    return {
        "ok": True,
        "model": "gsc_transition",
        "params": {"H0": 67.4, "Omega_m": 0.315, "p": 0.62},
        "chi2_total": float(chi2),
        "chi2_parts": {
            "cmb": {"chi2": float(chi2)},
            "drift": {"min_zdot_si": 1.0e-11, "sign_ok": True},
            "invariants": {"ok": True},
        },
        "drift": {
            "z_list": [2.0, 3.0, 4.0, 5.0],
            "z_dot": [1.0e-11, 1.0e-11, 1.0e-11, 1.0e-11],
            "min_z_dot": 1.0e-11,
            "all_positive": True,
        },
        "drift_pass": True,
        "invariants_ok": True,
        "microphysics": {
            "mode": "knobs",
            "z_star_scale": 1.0,
            "r_s_scale": 1.0,
            "r_d_scale": 1.0,
        },
        "microphysics_plausible_ok": bool(plausible),
        "microphysics_penalty": float(penalty),
        "microphysics_max_rel_dev": float(0.0 if plausible else 0.08),
        "microphysics_notes": [] if plausible else [note],
    }


class TestPhase2M25ReportsMicrophysicsPlausibility(unittest.TestCase):
    def test_pareto_filter_and_diagnostics_summary(self):
        pareto_script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        diagnostics_script = ROOT / "scripts" / "phase2_e2_diagnostics_report.py"
        self.assertTrue(pareto_script.is_file())
        self.assertTrue(diagnostics_script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            out_any = td_path / "out_any"
            out_plausible = td_path / "out_plausible"
            out_diag = td_path / "out_diag"

            rows = [
                _sample(chi2=5.0, plausible=True, penalty=0.0, note=""),
                _sample(chi2=1.0, plausible=False, penalty=10.0, note="z_star_scale outside plausible"),
            ]
            in_jsonl.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")

            cmd_any = [
                sys.executable,
                str(pareto_script),
                "--jsonl",
                str(in_jsonl),
                "--top-k",
                "5",
                "--out-dir",
                str(out_any),
            ]
            proc_any = subprocess.run(cmd_any, cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(proc_any.returncode, 0, msg=(proc_any.stdout or "") + (proc_any.stderr or ""))

            cmd_plausible = [
                sys.executable,
                str(pareto_script),
                "--jsonl",
                str(in_jsonl),
                "--top-k",
                "5",
                "--plausibility",
                "plausible_only",
                "--out-dir",
                str(out_plausible),
            ]
            proc_plausible = subprocess.run(cmd_plausible, cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(
                proc_plausible.returncode,
                0,
                msg=(proc_plausible.stdout or "") + (proc_plausible.stderr or ""),
            )

            with (out_any / "pareto_top_positive.csv").open("r", encoding="utf-8", newline="") as fh:
                rows_any = list(csv.DictReader(fh))
            with (out_plausible / "pareto_top_positive.csv").open("r", encoding="utf-8", newline="") as fh:
                rows_plausible = list(csv.DictReader(fh))

            self.assertEqual(len(rows_any), 2)
            self.assertEqual(len(rows_plausible), 1)
            self.assertAlmostEqual(float(rows_plausible[0]["chi2_cmb"]), 5.0, places=9)
            self.assertEqual(rows_plausible[0]["microphysics_plausible_ok"], "True")

            cmd_diag = [
                sys.executable,
                str(diagnostics_script),
                "--jsonl",
                str(in_jsonl),
                "--outdir",
                str(out_diag),
                "--top",
                "3",
            ]
            proc_diag = subprocess.run(cmd_diag, cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(proc_diag.returncode, 0, msg=(proc_diag.stdout or "") + (proc_diag.stderr or ""))

            summary_text = (out_diag / "e2_diagnostics_summary.md").read_text(encoding="utf-8")
            self.assertIn("N_plausible:", summary_text)
            self.assertIn("fraction_plausible:", summary_text)
            self.assertIn("best_overall_non_plausible_penalty:", summary_text)
            self.assertIn("best_overall_non_plausible_notes:", summary_text)


if __name__ == "__main__":
    unittest.main()
