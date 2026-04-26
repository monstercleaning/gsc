import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _row(
    *,
    sample_id: int,
    p1: float,
    p2: float,
    chi2_cmb: float,
    chi2_total: float,
    invariants_ok: bool,
    all_positive: bool = True,
) -> dict:
    return {
        "sample_id": int(sample_id),
        "status": "ok",
        "model": "gsc_transition",
        "params_hash": f"hash_{sample_id}",
        "params": {
            "p1": float(p1),
            "p2": float(p2),
            "recombination_method": "fit",
        },
        "chi2_total": float(chi2_total),
        "chi2_parts": {
            "cmb": {"chi2": float(chi2_cmb)},
            "drift": {"min_zdot_si": 0.2 if all_positive else -0.2, "sign_ok": bool(all_positive)},
            "invariants": {"ok": bool(invariants_ok)},
        },
        "drift": {
            "min_z_dot": 0.2 if all_positive else -0.2,
            "all_positive": bool(all_positive),
        },
        "drift_pass": bool(all_positive),
        "invariants_ok": bool(invariants_ok),
        "sampler": {
            "detail": {
                "bounds": {
                    "p1": [0.0, 1.0],
                    "p2": [0.0, 1.0],
                }
            }
        },
    }


class TestPhase2M33ParetoEmitRefinePlanSensitivity(unittest.TestCase):
    def _run(self, cmd: list[str]) -> tuple[int, str]:
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
        output = (proc.stdout or "") + (proc.stderr or "")
        return int(proc.returncode), output

    def test_sensitivity_generates_downhill_points(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"
            plan_path = td_path / "plan_sensitivity.json"

            rows = [
                _row(sample_id=1, p1=0.90, p2=0.50, chi2_cmb=10.0, chi2_total=1.0, invariants_ok=True),
                _row(sample_id=2, p1=0.80, p2=0.50, chi2_cmb=9.0, chi2_total=2.0, invariants_ok=False),
                _row(sample_id=3, p1=0.70, p2=0.50, chi2_cmb=8.0, chi2_total=2.5, invariants_ok=False),
                _row(sample_id=4, p1=0.60, p2=0.50, chi2_cmb=7.0, chi2_total=3.0, invariants_ok=False),
                _row(sample_id=5, p1=0.50, p2=0.50, chi2_cmb=6.0, chi2_total=3.5, invariants_ok=False),
                _row(sample_id=6, p1=0.40, p2=0.50, chi2_cmb=5.0, chi2_total=4.0, invariants_ok=False),
                _row(sample_id=7, p1=0.30, p2=0.50, chi2_cmb=4.0, chi2_total=4.5, invariants_ok=False),
                _row(sample_id=8, p1=0.20, p2=0.50, chi2_cmb=3.0, chi2_total=5.0, invariants_ok=False),
                _row(sample_id=9, p1=0.10, p2=0.50, chi2_cmb=2.0, chi2_total=5.5, invariants_ok=False),
            ]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
                "--emit-refine-plan",
                str(plan_path),
                "--refine-top-k",
                "1",
                "--refine-n-per-seed",
                "4",
                "--refine-strategy",
                "sensitivity",
                "--refine-target-metric",
                "chi2_cmb",
                "--refine-neighbors",
                "8",
                "--refine-top-params",
                "1",
                "--refine-step-frac",
                "0.05",
                "--refine-direction",
                "downhill_only",
                "--refine-anchor-filter",
                "any",
                "--refine-hold-fixed-nonnumeric",
                "1",
            ]
            code, output = self._run(cmd)
            self.assertEqual(code, 0, msg=output)
            self.assertTrue(plan_path.is_file())

            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("plan_version"), "phase2_e2_refine_plan_v1")
            refine_meta = payload.get("refine") or {}
            self.assertEqual(refine_meta.get("strategy"), "sensitivity")
            self.assertNotIn("generated_utc", payload)

            points = payload.get("points") or []
            self.assertGreaterEqual(len(points), 1)
            has_downhill = any(float((point.get("params") or {}).get("p1", 1.0)) < 0.90 for point in points)
            self.assertTrue(has_downhill, msg=f"expected downhill p1 move; points={points}")

    def test_sensitivity_plan_is_deterministic(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"
            plan_a = td_path / "plan_a.json"
            plan_b = td_path / "plan_b.json"

            rows = [
                _row(sample_id=1, p1=0.90, p2=0.50, chi2_cmb=10.0, chi2_total=1.0, invariants_ok=True),
                _row(sample_id=2, p1=0.80, p2=0.50, chi2_cmb=9.0, chi2_total=2.0, invariants_ok=False),
                _row(sample_id=3, p1=0.70, p2=0.50, chi2_cmb=8.0, chi2_total=3.0, invariants_ok=False),
                _row(sample_id=4, p1=0.60, p2=0.50, chi2_cmb=7.0, chi2_total=4.0, invariants_ok=False),
                _row(sample_id=5, p1=0.50, p2=0.50, chi2_cmb=6.0, chi2_total=5.0, invariants_ok=False),
                _row(sample_id=6, p1=0.40, p2=0.50, chi2_cmb=5.0, chi2_total=6.0, invariants_ok=False),
                _row(sample_id=7, p1=0.30, p2=0.50, chi2_cmb=4.0, chi2_total=7.0, invariants_ok=False),
                _row(sample_id=8, p1=0.20, p2=0.50, chi2_cmb=3.0, chi2_total=8.0, invariants_ok=False),
                _row(sample_id=9, p1=0.10, p2=0.50, chi2_cmb=2.0, chi2_total=9.0, invariants_ok=False),
            ]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

            common = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
                "--refine-top-k",
                "1",
                "--refine-n-per-seed",
                "4",
                "--refine-strategy",
                "sensitivity",
                "--refine-target-metric",
                "chi2_cmb",
                "--refine-neighbors",
                "8",
                "--refine-top-params",
                "2",
                "--refine-step-frac",
                "0.03",
                "--refine-direction",
                "both",
                "--refine-anchor-filter",
                "any",
                "--refine-hold-fixed-nonnumeric",
                "1",
            ]
            cmd_a = list(common) + ["--emit-refine-plan", str(plan_a)]
            cmd_b = list(common) + ["--emit-refine-plan", str(plan_b)]
            code_a, out_a = self._run(cmd_a)
            code_b, out_b = self._run(cmd_b)
            self.assertEqual(code_a, 0, msg=out_a)
            self.assertEqual(code_b, 0, msg=out_b)
            self.assertTrue(plan_a.is_file())
            self.assertTrue(plan_b.is_file())

            sha_a = hashlib.sha256(plan_a.read_bytes()).hexdigest()
            sha_b = hashlib.sha256(plan_b.read_bytes()).hexdigest()
            self.assertEqual(sha_a, sha_b)

    def test_default_grid_strategy_remains_compatible(self):
        script = ROOT / "scripts" / "phase2_e2_pareto_report.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            out_dir = td_path / "out"
            plan_path = td_path / "plan_grid.json"

            rows = [
                _row(sample_id=1, p1=0.5, p2=0.5, chi2_cmb=2.0, chi2_total=2.1, invariants_ok=True),
                _row(sample_id=2, p1=0.6, p2=0.4, chi2_cmb=2.2, chi2_total=2.4, invariants_ok=True),
                _row(sample_id=3, p1=0.4, p2=0.6, chi2_cmb=2.4, chi2_total=2.7, invariants_ok=True),
            ]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
                "--emit-refine-plan",
                str(plan_path),
                "--refine-top-k",
                "1",
                "--refine-n-per-seed",
                "2",
            ]
            code, output = self._run(cmd)
            self.assertEqual(code, 0, msg=output)
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("plan_version"), "phase2_e2_refine_plan_v1")
            refine_meta = payload.get("refine") or {}
            self.assertEqual(refine_meta.get("strategy"), "grid")
            self.assertNotIn("target_metric", refine_meta)


if __name__ == "__main__":
    unittest.main()
