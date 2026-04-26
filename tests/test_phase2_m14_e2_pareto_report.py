import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _point(*, chi2: float, margin: float, all_positive: bool, invariants_ok: bool, params: dict[str, float], model: str = "gsc_transition") -> dict:
    return {
        "model": model,
        "params": params,
        "chi2_total": float(chi2),
        "chi2_parts": {
            "cmb": {"chi2": float(chi2)},
            "drift": {"min_zdot_si": float(margin), "sign_ok": bool(all_positive)},
            "invariants": {"ok": bool(invariants_ok)},
        },
        "drift": {
            "z_list": [2.0, 3.0, 4.0, 5.0],
            "z_dot": [float(margin), float(margin), float(margin), float(margin)],
            "dv_cm_s_per_yr": [0.0, 0.0, 0.0, 0.0],
            "min_z_dot": float(margin),
            "all_positive": bool(all_positive),
        },
        "drift_pass": bool(all_positive),
        "invariants_ok": bool(invariants_ok),
    }


class TestPhase2M14E2ParetoReport(unittest.TestCase):
    def test_pareto_report_outputs_and_expected_best_points(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"

            points = [
                _point(chi2=10.0, margin=1.0, all_positive=True, invariants_ok=True, params={"H0": 67.0, "p": 0.65}),
                _point(chi2=12.0, margin=2.0, all_positive=True, invariants_ok=True, params={"H0": 68.0, "p": 0.66}),
                _point(chi2=9.0, margin=0.5, all_positive=True, invariants_ok=True, params={"H0": 69.0, "p": 0.67}),
                _point(chi2=15.0, margin=3.0, all_positive=True, invariants_ok=True, params={"H0": 70.0, "p": 0.68}),
                _point(chi2=8.0, margin=-0.2, all_positive=False, invariants_ok=True, params={"H0": 71.0, "p": 0.69}),
                _point(chi2=11.0, margin=1.5, all_positive=True, invariants_ok=False, params={"H0": 72.0, "p": 0.70}),
                _point(chi2=14.0, margin=1.1, all_positive=True, invariants_ok=True, params={"H0": 73.0, "p": 0.71}),
                {
                    "model": "lcdm",
                    "params": {"H0": 67.4, "Omega_m": 0.315},
                    "chi2_parts": {"cmb": {"chi2": 7.0}, "invariants": {"ok": True}},
                    "invariants_ok": True,
                },
            ]
            in_jsonl.write_text("\n".join(json.dumps(p, sort_keys=True) for p in points) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(in_jsonl),
                "--top-k",
                "3",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            summary_path = out_dir / "pareto_summary.json"
            frontier_path = out_dir / "pareto_frontier.csv"
            top_path = out_dir / "pareto_top_positive.csv"
            report_path = out_dir / "pareto_report.md"

            self.assertTrue(summary_path.is_file())
            self.assertTrue(frontier_path.is_file())
            self.assertTrue(top_path.is_file())
            self.assertTrue(report_path.is_file())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("n_total", -1)), 8)
            self.assertEqual(int(summary.get("n_with_invariants_ok", -1)), 7)
            self.assertEqual(int(summary.get("n_with_cmb", -1)), 8)
            self.assertEqual(int(summary.get("n_with_drift_metrics", -1)), 7)
            self.assertEqual(int(summary.get("n_all_positive", -1)), 6)

            best_overall = summary.get("best_overall") or {}
            self.assertAlmostEqual(float(best_overall.get("chi2_cmb")), 7.0, places=9)
            best_positive = summary.get("best_positive") or {}
            self.assertAlmostEqual(float(best_positive.get("chi2_cmb")), 9.0, places=9)

            with frontier_path.open("r", encoding="utf-8", newline="") as fh:
                frontier_rows = list(csv.DictReader(fh))
            self.assertEqual(len(frontier_rows), 5)

            with top_path.open("r", encoding="utf-8", newline="") as fh:
                top_rows = list(csv.DictReader(fh))
            self.assertEqual(len(top_rows), 3)
            self.assertAlmostEqual(float(top_rows[0]["chi2_cmb"]), 9.0, places=9)
            self.assertIn("chi2_parts_json", top_rows[0])


if __name__ == "__main__":
    unittest.main()
