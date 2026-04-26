import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _point(
    *,
    sid: int,
    chi2_cmb: float,
    chi2_total: float,
    drift_margin: float,
    all_positive: bool,
    plausible: bool,
    params: dict,
) -> dict:
    return {
        "sample_id": sid,
        "model": "lcdm",
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
        "microphysics_plausible_ok": bool(plausible),
        "params": dict(params),
        "sampler": {
            "detail": {
                "bounds": {
                    "H0": [60.0, 80.0],
                    "Omega_m": [0.20, 0.50],
                }
            }
        },
    }


class TestPhase2M26ParetoEmitRefinePlan(unittest.TestCase):
    def test_emit_refine_plan_is_deterministic(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"
            plan_a = td_path / "refine_a.json"
            plan_b = td_path / "refine_b.json"

            rows = [
                _point(
                    sid=1,
                    chi2_cmb=4.2,
                    chi2_total=4.4,
                    drift_margin=0.2,
                    all_positive=True,
                    plausible=True,
                    params={"H0": 67.1, "Omega_m": 0.31},
                ),
                _point(
                    sid=2,
                    chi2_cmb=3.8,
                    chi2_total=4.0,
                    drift_margin=0.4,
                    all_positive=True,
                    plausible=True,
                    params={"H0": 67.5, "Omega_m": 0.29},
                ),
                _point(
                    sid=3,
                    chi2_cmb=5.6,
                    chi2_total=5.9,
                    drift_margin=-0.1,
                    all_positive=False,
                    plausible=True,
                    params={"H0": 66.8, "Omega_m": 0.33},
                ),
                _point(
                    sid=4,
                    chi2_cmb=2.9,
                    chi2_total=3.1,
                    drift_margin=0.7,
                    all_positive=True,
                    plausible=False,
                    params={"H0": 68.0, "Omega_m": 0.28},
                ),
                _point(
                    sid=5,
                    chi2_cmb=6.2,
                    chi2_total=6.5,
                    drift_margin=0.1,
                    all_positive=True,
                    plausible=True,
                    params={"H0": 67.9, "Omega_m": 0.30},
                ),
            ]
            jsonl.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")
            expected_sha = hashlib.sha256(jsonl.read_bytes()).hexdigest()

            base_cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(jsonl),
                "--out-dir",
                str(out_dir),
                "--emit-refine-plan",
                str(plan_a),
                "--refine-top-k",
                "2",
                "--refine-n-per-seed",
                "3",
                "--refine-radius-rel",
                "0.05",
                "--refine-seed",
                "17",
                "--refine-sampler",
                "lhs",
            ]
            proc_a = subprocess.run(base_cmd, cwd=str(ROOT), text=True, capture_output=True)
            output_a = (proc_a.stdout or "") + (proc_a.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=output_a)
            self.assertTrue(plan_a.is_file())

            payload_a = json.loads(plan_a.read_text(encoding="utf-8"))
            self.assertEqual(payload_a.get("plan_version"), "phase2_e2_refine_plan_v1")
            self.assertEqual((payload_a.get("source") or {}).get("jsonl_sha256"), expected_sha)
            self.assertEqual(len(payload_a.get("points") or []), 6)

            cmd_b = list(base_cmd)
            cmd_b[cmd_b.index(str(plan_a))] = str(plan_b)
            proc_b = subprocess.run(cmd_b, cwd=str(ROOT), text=True, capture_output=True)
            output_b = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_b.returncode, 0, msg=output_b)
            self.assertTrue(plan_b.is_file())

            payload_b = json.loads(plan_b.read_text(encoding="utf-8"))
            self.assertEqual(payload_b.get("global_bounds"), payload_a.get("global_bounds"))
            self.assertEqual(payload_b.get("selection"), payload_a.get("selection"))
            self.assertEqual(payload_b.get("refine"), payload_a.get("refine"))
            self.assertEqual(payload_b.get("points"), payload_a.get("points"))


if __name__ == "__main__":
    unittest.main()
