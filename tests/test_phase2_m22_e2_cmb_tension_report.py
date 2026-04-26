import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M22E2CmbTensionReport(unittest.TestCase):
    def test_cmb_tension_report_outputs_and_quantiles(self):
        script = ROOT / "scripts" / "phase2_e2_cmb_tension_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            input_jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"

            rows = [
                {
                    "ok": True,
                    "model": "gsc_transition",
                    "chi2_total": 12.0,
                    "chi2_parts": {"cmb": {"chi2": 11.0}},
                    "drift_sign_z2_5": 1.0,
                    "params": {"H0": 67.0, "Omega_m": 0.32},
                    "cmb_pred": {"R": 1.7, "lA": 300.0, "omega_b_h2": 0.0223},
                    "cmb_tension": {
                        "scale_D_from_R": 0.96,
                        "scale_rs_from_lA_given_R": 1.08,
                        "scale_rs_from_lA_only": 1.01,
                        "scale_D_from_lA_only": 0.99,
                        "delta_D_pct": -4.0,
                        "delta_rs_pct": 8.0,
                        "dR_sigma_diag": -2.0,
                        "dlA_sigma_diag": 1.4,
                        "domega_sigma_diag": -0.3,
                    },
                },
                {
                    "ok": True,
                    "model": "gsc_transition",
                    "chi2_total": 6.0,
                    "chi2_parts": {"cmb": {"chi2": 5.0}},
                    "drift_sign_z2_5": -1.0,
                    "params": {"H0": 68.0, "Omega_m": 0.31},
                    "cmb_pred": {"R": 1.74, "lA": 301.0, "omega_b_h2": 0.02237},
                    "cmb_tension": {
                        "scale_D_from_R": 1.02,
                        "scale_rs_from_lA_given_R": 0.99,
                        "scale_rs_from_lA_only": 0.97,
                        "scale_D_from_lA_only": 1.03,
                        "delta_D_pct": 2.0,
                        "delta_rs_pct": -1.0,
                        "dR_sigma_diag": 0.4,
                        "dlA_sigma_diag": -0.7,
                        "domega_sigma_diag": 0.0,
                    },
                },
                {
                    "ok": True,
                    "model": "lcdm",
                    "chi2_total": 9.0,
                    "chi2_parts": {"cmb": {"chi2": 7.0}},
                    "drift_sign_z2_5": 1.0,
                    "params": {"H0": 67.4, "Omega_m": 0.315},
                    "cmb_pred": {"R": 1.76, "lA": 302.0, "omega_b_h2": 0.02245},
                    "cmb_tension": {
                        "scale_D_from_R": 1.10,
                        "scale_rs_from_lA_given_R": 1.05,
                        "scale_rs_from_lA_only": 1.01,
                        "scale_D_from_lA_only": 0.99,
                        "delta_D_pct": 10.0,
                        "delta_rs_pct": 5.0,
                        "dR_sigma_diag": 1.1,
                        "dlA_sigma_diag": 0.8,
                        "domega_sigma_diag": 0.2,
                    },
                },
            ]

            input_jsonl.write_text(
                "\n".join(
                    [
                        json.dumps(rows[0]),
                        "{not-json",
                        json.dumps({"ok": True, "chi2_total": 1.0, "drift_sign_z2_5": 1.0}),
                        json.dumps(rows[1]),
                        json.dumps(rows[2]),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(script),
                "--in-jsonl",
                str(input_jsonl),
                "--outdir",
                str(out_dir),
                "--top-k",
                "3",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            summary_json = out_dir / "cmb_tension_summary.json"
            summary_md = out_dir / "cmb_tension_summary.md"
            topk_csv = out_dir / "cmb_tension_topk.csv"
            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())
            self.assertTrue(topk_csv.is_file())

            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            self.assertIn("counts", summary)
            self.assertIn("quantiles", summary)
            self.assertIn("fractions", summary)
            self.assertEqual(int(summary["counts"]["total_lines"]), 5)
            self.assertEqual(int(summary["counts"]["with_cmb_tension"]), 3)
            self.assertEqual(int(summary["counts"]["after_filters"]), 3)
            self.assertAlmostEqual(float(summary["quantiles"]["delta_D_pct"]["p50"]), 2.0, places=12)
            self.assertAlmostEqual(float(summary["quantiles"]["delta_rs_pct"]["p50"]), 5.0, places=12)

            md_text = summary_md.read_text(encoding="utf-8")
            self.assertIn("N_used:", md_text)

            with topk_csv.open("r", encoding="utf-8", newline="") as fh:
                rows_out = list(csv.DictReader(fh))
            self.assertEqual(len(rows_out), 3)
            self.assertEqual(rows_out[0]["chi2_total"], "6")


if __name__ == "__main__":
    unittest.main()
