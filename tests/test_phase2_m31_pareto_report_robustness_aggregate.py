import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _scan_row(
    *,
    params_hash: Optional[str],
    chi2_cmb: float,
    chi2_total: float,
    drift_margin: float,
    all_positive: bool,
    params: dict[str, float],
) -> dict:
    row = {
        "model": "gsc_transition",
        "params": dict(params),
        "chi2_total": float(chi2_total),
        "chi2_parts": {
            "cmb": {"chi2": float(chi2_cmb)},
            "drift": {"min_zdot_si": float(drift_margin), "sign_ok": bool(all_positive)},
            "invariants": {"ok": True},
        },
        "drift": {
            "min_z_dot": float(drift_margin),
            "all_positive": bool(all_positive),
        },
        "drift_pass": bool(all_positive),
        "invariants_ok": True,
    }
    if params_hash is not None:
        row["params_hash"] = str(params_hash)
    return row


class TestPhase2M31ParetoReportRobustnessAggregate(unittest.TestCase):
    def test_robust_mode_uses_aggregate_and_emits_columns(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            agg_jsonl = td_path / "aggregate.jsonl"
            out_dir = td_path / "out"

            scan_rows = [
                _scan_row(
                    params_hash="hash_a",
                    chi2_cmb=11.0,
                    chi2_total=12.0,
                    drift_margin=0.10,
                    all_positive=True,
                    params={"H0": 67.0, "Omega_m": 0.31},
                ),
                _scan_row(
                    params_hash="hash_a",
                    chi2_cmb=13.0,
                    chi2_total=14.0,
                    drift_margin=0.15,
                    all_positive=True,
                    params={"H0": 67.0, "Omega_m": 0.31},
                ),
                _scan_row(
                    params_hash="hash_b",
                    chi2_cmb=4.0,
                    chi2_total=5.0,
                    drift_margin=0.50,
                    all_positive=True,
                    params={"H0": 68.0, "Omega_m": 0.29},
                ),
            ]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in scan_rows) + "\n",
                encoding="utf-8",
            )

            agg_rows = [
                {
                    "params_hash": "hash_a",
                    "n_runs": 2,
                    "chi2_cmb_min": 4.8,
                    "chi2_cmb_mean": 4.9,
                    "chi2_cmb_max": 5.0,
                    "chi2_total_min": 6.8,
                    "chi2_total_mean": 6.9,
                    "chi2_total_max": 7.0,
                    "drift_metric_min": 0.2,
                    "drift_metric_mean": 0.3,
                    "drift_metric_max": 0.4,
                    "drift_sign_consensus": True,
                    "microphysics_plausible_all": True,
                },
                {
                    "params_hash": "hash_b",
                    "n_runs": 1,
                    "chi2_cmb_min": 3.0,
                    "chi2_cmb_mean": 3.1,
                    "chi2_cmb_max": 3.2,
                    "chi2_total_min": 4.0,
                    "chi2_total_mean": 4.1,
                    "chi2_total_max": 4.2,
                    "drift_metric_min": 0.6,
                    "drift_metric_mean": 0.7,
                    "drift_metric_max": 0.8,
                    "drift_sign_consensus": True,
                    "microphysics_plausible_all": True,
                },
            ]
            agg_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in agg_rows) + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--robustness-aggregate",
                str(agg_jsonl),
                "--robustness-objective",
                "worst",
                "--robustness-min-runs",
                "2",
                "--out-dir",
                str(out_dir),
                "--top-k",
                "10",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            top_csv = out_dir / "pareto_top_positive.csv"
            self.assertTrue(top_csv.is_file())
            with top_csv.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.get("params_hash"), "hash_a")
            self.assertEqual(row.get("robust_n_runs"), "2")
            self.assertIn("robust_chi2_cmb_max", row)
            self.assertEqual(row.get("robust_chi2_cmb_max"), "5.0")

    def test_robust_mode_requires_params_hash(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan_no_hash.jsonl"
            agg_jsonl = td_path / "aggregate.jsonl"
            out_dir = td_path / "out"

            scan_jsonl.write_text(
                json.dumps(
                    _scan_row(
                        params_hash=None,
                        chi2_cmb=8.0,
                        chi2_total=9.0,
                        drift_margin=0.2,
                        all_positive=True,
                        params={"H0": 67.4, "Omega_m": 0.315},
                    ),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            agg_jsonl.write_text(json.dumps({"params_hash": "hash_a", "n_runs": 2}) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--robustness-aggregate",
                str(agg_jsonl),
                "--robustness-objective",
                "worst",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("params_hash", output)

    def test_robust_mode_accepts_csv_aggregate(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            agg_csv = td_path / "aggregate.csv"
            out_dir = td_path / "out"

            scan_jsonl.write_text(
                json.dumps(
                    _scan_row(
                        params_hash="hash_csv",
                        chi2_cmb=9.0,
                        chi2_total=10.0,
                        drift_margin=0.25,
                        all_positive=True,
                        params={"H0": 67.2, "Omega_m": 0.312},
                    ),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            with agg_csv.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "params_hash",
                        "n_present",
                        "chi2_cmb_min",
                        "chi2_cmb_max",
                        "chi2_total_min",
                        "chi2_total_max",
                        "drift_metric_min",
                        "drift_metric_max",
                        "drift_sign_consensus",
                        "microphysics_plausible_all",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "params_hash": "hash_csv",
                        "n_present": "2",
                        "chi2_cmb_min": "4.5",
                        "chi2_cmb_max": "5.5",
                        "chi2_total_min": "6.5",
                        "chi2_total_max": "7.5",
                        "drift_metric_min": "0.10",
                        "drift_metric_max": "0.30",
                        "drift_sign_consensus": "true",
                        "microphysics_plausible_all": "true",
                    }
                )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--robustness-aggregate",
                str(agg_csv),
                "--robustness-objective",
                "worst",
                "--robustness-min-runs",
                "2",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue((out_dir / "pareto_summary.json").is_file())

    def test_backward_compatible_without_robust_flags(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan_legacy.jsonl"
            out_dir = td_path / "out"

            legacy_row = {
                "model": "lcdm",
                "params": {"H0": 67.4, "Omega_m": 0.315},
                "chi2_total": 7.0,
                "chi2_parts": {
                    "cmb": {"chi2": 6.9},
                    "drift": {"min_zdot_si": -1.0e-11, "sign_ok": False},
                    "invariants": {"ok": True},
                },
                "drift": {"min_z_dot": -1.0e-11, "all_positive": False},
                "drift_pass": False,
                "invariants_ok": True,
            }
            scan_jsonl.write_text(json.dumps(legacy_row, sort_keys=True) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue((out_dir / "pareto_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
