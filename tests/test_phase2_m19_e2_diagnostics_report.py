import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M19E2DiagnosticsReport(unittest.TestCase):
    def test_diagnostics_report_outputs_and_contract(self):
        script = ROOT / "scripts" / "phase2_e2_diagnostics_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_a = td_path / "scan_a.jsonl"
            in_b = td_path / "scan_b.jsonl"
            out_dir = td_path / "out"

            rows_a = [
                {
                    "ok": True,
                    "model": "gsc_transition",
                    "chi2_total": 5.0,
                    "drift_sign_z2_5": 1.0,
                    "params": {"H0": 67.0, "p": 0.6, "omega_b_h2": 0.02237},
                    "chi2_parts": {"cmb": {"chi2": 4.2}, "drift": {"chi2": 0.5}, "priors": {"chi2": 0.3}},
                },
                {
                    "ok": True,
                    "model": "gsc_transition",
                    "chi2_total": 9.0,
                    "drift_sign_z2_5": -1.0,
                    "params": {"H0": 69.0, "p": 0.7, "omega_b_h2": 0.02210},
                    "chi2_parts": {"cmb": {"chi2": 8.0}, "drift": {"chi2": 1.0}},
                },
                {"ok": False, "chi2_total": 99.0, "drift_sign_z2_5": 1.0},
            ]
            in_a.write_text(
                "\n".join([json.dumps(rows_a[0]), "{not-json", json.dumps(rows_a[1]), json.dumps(rows_a[2])]) + "\n",
                encoding="utf-8",
            )

            rows_b = [
                {
                    "ok": True,
                    "model_id": "lcdm",
                    "result": {"chi2_total": 3.5},
                    "metrics": {"dzdt_z3": 2.5e-11},
                    "params": {"H0": 67.4, "Omega_m": 0.315},
                    "chi2_parts": {"cmb": {"chi2": 3.5}},
                },
                {
                    "ok": True,
                    "family": "lcdm",
                    "metrics": {"chi2_total": 12.0, "dzdt_z3": -3.0e-11},
                    "params": {"H0": 70.0, "Omega_m": 0.29},
                    "chi2_parts": {"cmb": {"chi2": 12.0}},
                },
            ]
            in_b.write_text("\n".join([json.dumps(rows_b[0]), "[]", json.dumps(rows_b[1])]) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(in_a),
                "--jsonl",
                str(in_b),
                "--outdir",
                str(out_dir),
                "--top",
                "3",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            summary = out_dir / "e2_diagnostics_summary.md"
            best = out_dir / "e2_best_points.csv"
            envelope = out_dir / "e2_tradeoff_envelope.csv"
            corr = out_dir / "e2_param_correlations.csv"

            self.assertTrue(summary.is_file())
            self.assertTrue(best.is_file())
            self.assertTrue(envelope.is_file())
            self.assertTrue(corr.is_file())

            summary_text = summary.read_text(encoding="utf-8")
            self.assertIn("N_used:", summary_text)
            self.assertIn("Input SHA256", summary_text)

            with envelope.open("r", encoding="utf-8", newline="") as fh:
                env_rows = list(csv.DictReader(fh))
            self.assertEqual(len(env_rows), 5)
            self.assertEqual({row["mode"] for row in env_rows}, {"require_drift", "require_chi2"})

            with best.open("r", encoding="utf-8", newline="") as fh:
                best_rows = list(csv.DictReader(fh))
            self.assertTrue(best_rows)
            criteria = {row["criterion"] for row in best_rows}
            self.assertTrue({"chi2", "drift", "pareto"}.issubset(criteria))


if __name__ == "__main__":
    unittest.main()
