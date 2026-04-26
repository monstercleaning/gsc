import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M32E2SensitivityReport(unittest.TestCase):
    def _run(self, args):
        script = ROOT / "scripts" / "phase2_e2_sensitivity_report.py"
        self.assertTrue(script.is_file())
        cmd = [sys.executable, str(script)] + list(args)
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output

    def _read_corr(self, csv_path: Path):
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        out = {}
        for row in rows:
            out[(row["param_key"], row["metric_key"])] = row
        return out

    def test_monotonic_and_anticorrelation(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            out_md = td_path / "report.md"
            out_csv = td_path / "corr.csv"
            out_json = td_path / "corr.json"

            rows = []
            for i in range(1, 11):
                rows.append(
                    {
                        "status": "ok",
                        "params": {"a": float(i), "b": float(11 - i)},
                        "chi2_total": float(2 * i),
                        "chi2_parts": {"cmb_priors": {"chi2": float(i)}},
                        "drift_z_min": float(i - 6),
                    }
                )
            in_jsonl.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")

            rc, output = self._run(
                [
                    str(in_jsonl),  # positional input path
                    "--out-md",
                    str(out_md),
                    "--out-csv",
                    str(out_csv),
                    "--out-json",
                    str(out_json),
                    "--metrics",
                    "chi2_total",
                    "--top-k",
                    "5",
                ]
            )
            self.assertEqual(rc, 0, msg=output)
            self.assertTrue(out_md.is_file())
            self.assertTrue(out_csv.is_file())
            self.assertTrue(out_json.is_file())

            by_pair = self._read_corr(out_csv)
            row_a = by_pair[("a", "chi2_total")]
            row_b = by_pair[("b", "chi2_total")]

            self.assertEqual(int(row_a["n"]), 10)
            self.assertEqual(int(row_b["n"]), 10)
            self.assertAlmostEqual(float(row_a["pearson_r"]), 1.0, places=12)
            self.assertAlmostEqual(float(row_a["spearman_r"]), 1.0, places=12)
            self.assertAlmostEqual(float(row_b["pearson_r"]), -1.0, places=12)
            self.assertAlmostEqual(float(row_b["spearman_r"]), -1.0, places=12)

    def test_ties_do_not_crash_and_have_valid_n(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan_ties.jsonl"
            out_md = td_path / "report_ties.md"
            out_csv = td_path / "corr_ties.csv"

            a_vals = [1, 1, 2, 2, 3, 3]
            y_vals = [1, 2, 2, 3, 3, 4]
            rows = []
            for a, y in zip(a_vals, y_vals):
                rows.append({"status": "ok", "params": {"a": float(a)}, "chi2_total": float(y)})
            in_jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

            rc, output = self._run(
                [
                    "--in-jsonl",
                    str(in_jsonl),
                    "--out-md",
                    str(out_md),
                    "--out-csv",
                    str(out_csv),
                    "--metrics",
                    "chi2_total",
                ]
            )
            self.assertEqual(rc, 0, msg=output)
            by_pair = self._read_corr(out_csv)
            row = by_pair[("a", "chi2_total")]
            self.assertEqual(int(row["n"]), 6)
            self.assertNotEqual(row["spearman_r"], "")
            self.assertNotEqual(row["spearman_r"], "NA")

    def test_filters_and_backward_compat_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan_filters.jsonl"
            out_md = td_path / "report_filters.md"
            out_csv = td_path / "corr_filters.csv"

            rows = [
                {
                    "status": "ok",
                    "params": {"a": 1.0},
                    "chi2_total": 1.0,
                    "drift_z_min": 0.1,
                    "microphysics_plausible_ok": True,
                },
                {
                    "status": "ok",
                    "params": {"a": 2.0},
                    "chi2_total": 2.0,
                    "drift_z_min": 0.2,
                    "microphysics_plausible_ok": False,
                },
                {
                    "status": "error",
                    "params": {"a": 3.0},
                    "chi2_total": 3.0,
                    "drift_z_min": 0.3,
                    "microphysics_plausible_ok": True,
                },
                {
                    # Backward-compatible row: missing status + plausibility fields.
                    "params": {"a": 4.0},
                    "chi2_total": 4.0,
                    "drift_z_min": 0.4,
                },
                {
                    # Missing requested drift filter metric.
                    "status": "ok",
                    "params": {"a": 5.0},
                    "chi2_total": 5.0,
                    "microphysics_plausible_ok": True,
                },
            ]
            in_jsonl.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")

            rc, output = self._run(
                [
                    "--in-jsonl",
                    str(in_jsonl),
                    "--out-md",
                    str(out_md),
                    "--out-csv",
                    str(out_csv),
                    "--plausibility",
                    "plausible_only",
                    "--require-drift-positive",
                    "drift_z_min",
                    "--metrics",
                    "chi2_total",
                ]
            )
            self.assertEqual(rc, 0, msg=output)

            text = out_md.read_text(encoding="utf-8")
            self.assertIn("N_used: `2`", text)
            self.assertIn("status_filter: `1`", text)
            self.assertIn("plausibility_filter: `1`", text)
            self.assertIn("missing_drift_filter_metric: `1`", text)

    def test_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan_det.jsonl"
            out_md_a = td_path / "report_a.md"
            out_md_b = td_path / "report_b.md"
            out_csv_a = td_path / "corr_a.csv"
            out_csv_b = td_path / "corr_b.csv"

            rows = []
            for i in range(1, 8):
                rows.append({"status": "ok", "params": {"x": float(i), "y": float(i * i)}, "chi2_total": float(i)})
            in_jsonl.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")

            args_common = [
                "--in-jsonl",
                str(in_jsonl),
                "--metrics",
                "chi2_total",
                "--top-k",
                "5",
                "--quantile-metric",
                "chi2_total",
            ]
            rc_a, output_a = self._run(args_common + ["--out-md", str(out_md_a), "--out-csv", str(out_csv_a)])
            rc_b, output_b = self._run(args_common + ["--out-md", str(out_md_b), "--out-csv", str(out_csv_b)])
            self.assertEqual(rc_a, 0, msg=output_a)
            self.assertEqual(rc_b, 0, msg=output_b)

            self.assertEqual(out_md_a.read_bytes(), out_md_b.read_bytes())
            self.assertEqual(out_csv_a.read_bytes(), out_csv_b.read_bytes())


if __name__ == "__main__":
    unittest.main()
