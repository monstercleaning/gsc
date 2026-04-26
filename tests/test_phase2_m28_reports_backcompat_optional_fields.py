import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M28ReportsBackcompatOptionalFields(unittest.TestCase):
    def _write_old_style_jsonl(self, path: Path) -> None:
        rows = [
            {
                "ok": True,
                "model": "gsc_transition",
                "chi2_total": 8.0,
                "drift_sign_z2_5": 1.0,
                "params": {"H0": 67.0, "Omega_m": 0.31},
                "chi2_parts": {"cmb": {"chi2": 6.5}, "drift": {"chi2": 1.0}},
                "cmb_pred": {"R": 1.75, "lA": 301.0, "omega_b_h2": 0.02237},
                "cmb_tension": {
                    "scale_D_from_R": 1.01,
                    "scale_rs_from_lA_given_R": 0.99,
                    "scale_rs_from_lA_only": 0.98,
                    "scale_D_from_lA_only": 1.02,
                    "delta_D_pct": 1.0,
                    "delta_rs_pct": -1.0,
                    "dR_sigma_diag": 0.1,
                    "dlA_sigma_diag": -0.2,
                    "domega_sigma_diag": 0.0,
                },
            },
            {
                "ok": True,
                "model": "lcdm",
                "chi2_total": 5.0,
                "drift_sign_z2_5": -1.0,
                "params": {"H0": 67.4, "Omega_m": 0.315},
                "chi2_parts": {"cmb": {"chi2": 4.5}},
                "cmb_pred": {"R": 1.74, "lA": 300.5, "omega_b_h2": 0.0223},
                "cmb_tension": {
                    "scale_D_from_R": 0.99,
                    "scale_rs_from_lA_given_R": 1.02,
                    "scale_rs_from_lA_only": 1.01,
                    "scale_D_from_lA_only": 0.99,
                    "delta_D_pct": -1.0,
                    "delta_rs_pct": 2.0,
                    "dR_sigma_diag": -0.3,
                    "dlA_sigma_diag": 0.4,
                    "domega_sigma_diag": 0.1,
                },
            },
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def test_reports_accept_jsonl_without_m28_fields(self):
        pareto_script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        diag_script = ROOT / "scripts" / "phase2_e2_diagnostics_report.py"
        tension_script = ROOT / "scripts" / "phase2_e2_cmb_tension_report.py"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl_path = td_path / "old_scan.jsonl"
            self._write_old_style_jsonl(jsonl_path)

            pareto_out = td_path / "pareto"
            diag_out = td_path / "diag"
            tension_out = td_path / "tension"

            pareto_cmd = [
                sys.executable,
                str(pareto_script),
                "--jsonl",
                str(jsonl_path),
                "--out-dir",
                str(pareto_out),
            ]
            diag_cmd = [
                sys.executable,
                str(diag_script),
                "--jsonl",
                str(jsonl_path),
                "--outdir",
                str(diag_out),
            ]
            tension_cmd = [
                sys.executable,
                str(tension_script),
                "--in-jsonl",
                str(jsonl_path),
                "--outdir",
                str(tension_out),
            ]

            for cmd in (pareto_cmd, diag_cmd, tension_cmd):
                proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
                output = (proc.stdout or "") + (proc.stderr or "")
                self.assertEqual(proc.returncode, 0, msg=output)

            self.assertTrue((pareto_out / "pareto_summary.json").is_file())
            self.assertTrue((diag_out / "e2_diagnostics_summary.md").is_file())
            self.assertTrue((tension_out / "cmb_tension_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
