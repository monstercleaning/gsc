import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _point(*, sid: int, chi2: float, margin: float, all_positive: bool, params: dict[str, float]) -> dict:
    return {
        "sample_id": sid,
        "model": "gsc_transition",
        "params": params,
        "chi2_total": float(chi2) + 0.25,
        "chi2_parts": {
            "cmb": {"chi2": float(chi2)},
            "drift": {"min_zdot_si": float(margin), "sign_ok": bool(all_positive)},
            "invariants": {"ok": True},
        },
        "drift": {
            "z_list": [2.0, 3.0, 4.0, 5.0],
            "z_dot": [float(margin)] * 4,
            "dv_cm_s_per_yr": [0.0, 0.0, 0.0, 0.0],
            "min_z_dot": float(margin),
            "all_positive": bool(all_positive),
        },
        "drift_pass": bool(all_positive),
        "invariants_ok": True,
    }


class TestPhase2M18ParetoRefineOutputs(unittest.TestCase):
    def test_emits_summary_refine_bounds_and_seed_points(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"
            summary_out = td_path / "summary_machine.json"
            bounds_out = td_path / "refine_bounds.json"
            seeds_out = td_path / "seed_points.jsonl"

            points = [
                _point(sid=1, chi2=5.0, margin=1.2, all_positive=True, params={"H0": 67.2, "Omega_m": 0.31, "p": 0.62}),
                _point(sid=2, chi2=4.5, margin=0.8, all_positive=True, params={"H0": 67.8, "Omega_m": 0.32, "p": 0.64}),
                _point(sid=3, chi2=9.5, margin=1.8, all_positive=True, params={"H0": 68.1, "Omega_m": 0.33, "p": 0.66}),
                _point(sid=4, chi2=3.8, margin=-0.1, all_positive=False, params={"H0": 66.7, "Omega_m": 0.30, "p": 0.60}),
            ]
            jsonl.write_text("\n".join(json.dumps(p, sort_keys=True) for p in points) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(jsonl),
                "--top-k",
                "2",
                "--chi2-cmb-threshold",
                "6.0",
                "--json-summary",
                str(summary_out),
                "--emit-refine-bounds",
                str(bounds_out),
                "--emit-seed-points",
                str(seeds_out),
                "--refine-top-k",
                "3",
                "--refine-score",
                "drift_then_chi2",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            self.assertTrue(summary_out.is_file())
            self.assertTrue(bounds_out.is_file())
            self.assertTrue(seeds_out.is_file())
            self.assertTrue((out_dir / "pareto_frontier.csv").is_file())
            self.assertTrue((out_dir / "pareto_top_positive.csv").is_file())

            summary = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("n_total", -1)), 4)
            self.assertEqual(int(summary.get("n_joint_positive_and_cmb_ok", -1)), 2)
            self.assertEqual(float(summary.get("chi2_cmb_threshold", float("nan"))), 6.0)

            bounds_payload = json.loads(bounds_out.read_text(encoding="utf-8"))
            self.assertEqual(bounds_payload.get("schema"), "gsc.phase2.e2.refine_bounds.v1")
            self.assertEqual(int(bounds_payload.get("top_k", -1)), 3)
            bounds = bounds_payload.get("bounds") or {}
            self.assertIn("H0", bounds)
            self.assertIn("Omega_m", bounds)
            self.assertLess(float(bounds["H0"]["min"]), float(bounds["H0"]["max"]))

            seed_lines = [json.loads(line) for line in seeds_out.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(seed_lines), 2)
            self.assertIn("params", seed_lines[0])
            self.assertIn("chi2_parts", seed_lines[0])


if __name__ == "__main__":
    unittest.main()
