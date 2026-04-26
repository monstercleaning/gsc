import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_pareto_report.py"
sys.path.insert(0, str(ROOT))
from gsc.early_time.refine_plan_v1 import validate_refine_plan_v1  # noqa: E402


def _row(
    *,
    sample_id: int,
    chi2_cmb: float,
    chi2_total: float,
    drift_margin: float,
    status: str = "ok",
    rsd_chi2_total: Optional[float] = None,
    h0: float,
    omega_m: float,
) -> dict:
    payload = {
        "sample_id": int(sample_id),
        "status": str(status),
        "model": "lcdm",
        "params_hash": f"m94_hash_{sample_id}",
        "params": {
            "H0": float(h0),
            "Omega_m": float(omega_m),
        },
        "chi2_total": float(chi2_total),
        "chi2_parts": {
            "cmb": {"chi2": float(chi2_cmb)},
            "drift": {
                "min_zdot_si": float(drift_margin),
                "sign_ok": bool(drift_margin > 0.0),
            },
            "invariants": {"ok": True},
        },
        "drift": {
            "min_z_dot": float(drift_margin),
            "all_positive": bool(drift_margin > 0.0),
        },
        "invariants_ok": True,
        "sampler": {
            "detail": {
                "bounds": {
                    "H0": [60.0, 80.0],
                    "Omega_m": [0.2, 0.5],
                }
            }
        },
    }
    if rsd_chi2_total is not None:
        payload["rsd_chi2_total"] = float(rsd_chi2_total)
    return payload


class TestPhase2M94ParetoEmitRefinePlanJointRank(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )

    def test_joint_rank_reorders_refine_plan_seed(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            scan_jsonl = tdp / "scan.jsonl"
            out_cmb = tdp / "out_cmb"
            out_joint = tdp / "out_joint"
            plan_cmb = tdp / "plan_cmb.json"
            plan_joint = tdp / "plan_joint.json"

            rows = [
                _row(
                    sample_id=1,
                    chi2_cmb=4.0,
                    chi2_total=4.0,
                    drift_margin=0.2,
                    rsd_chi2_total=10.0,
                    h0=66.1,
                    omega_m=0.31,
                ),
                _row(
                    sample_id=2,
                    chi2_cmb=4.2,
                    chi2_total=5.0,
                    drift_margin=0.2,
                    rsd_chi2_total=1.0,
                    h0=67.2,
                    omega_m=0.30,
                ),
                _row(
                    sample_id=3,
                    chi2_cmb=4.4,
                    chi2_total=6.0,
                    drift_margin=0.2,
                    rsd_chi2_total=2.0,
                    h0=68.3,
                    omega_m=0.29,
                ),
                _row(
                    sample_id=4,
                    chi2_cmb=4.5,
                    chi2_total=6.5,
                    drift_margin=0.2,
                    rsd_chi2_total=None,
                    h0=69.0,
                    omega_m=0.28,
                ),
            ]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

            proc_cmb = self._run(
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_cmb),
                "--emit-refine-plan",
                str(plan_cmb),
                "--refine-top-k",
                "1",
                "--refine-n-per-seed",
                "1",
                "--refine-radius-rel",
                "0.02",
                "--refine-seed",
                "13",
                "--rank-by",
                "cmb",
            )
            cmb_output = (proc_cmb.stdout or "") + (proc_cmb.stderr or "")
            self.assertEqual(proc_cmb.returncode, 0, msg=cmb_output)

            proc_joint = self._run(
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_joint),
                "--emit-refine-plan",
                str(plan_joint),
                "--refine-top-k",
                "1",
                "--refine-n-per-seed",
                "1",
                "--refine-radius-rel",
                "0.02",
                "--refine-seed",
                "13",
                "--rank-by",
                "joint",
            )
            joint_output = (proc_joint.stdout or "") + (proc_joint.stderr or "")
            self.assertEqual(proc_joint.returncode, 0, msg=joint_output)

            payload_cmb = json.loads(plan_cmb.read_text(encoding="utf-8"))
            payload_joint = json.loads(plan_joint.read_text(encoding="utf-8"))
            validate_refine_plan_v1(payload_cmb)
            validate_refine_plan_v1(payload_joint)

            first_seed_cmb = str((payload_cmb.get("points") or [{}])[0].get("seed_params_hash", ""))
            first_seed_joint = str((payload_joint.get("points") or [{}])[0].get("seed_params_hash", ""))
            self.assertNotEqual(first_seed_cmb, "")
            self.assertNotEqual(first_seed_joint, "")
            self.assertNotEqual(first_seed_cmb, first_seed_joint)

    def test_rank_by_joint_without_rsd_fields_returns_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            scan_jsonl = tdp / "scan_missing_rsd.jsonl"
            out_dir = tdp / "out"

            rows = [
                _row(
                    sample_id=11,
                    chi2_cmb=5.0,
                    chi2_total=5.1,
                    drift_margin=0.2,
                    rsd_chi2_total=None,
                    h0=67.0,
                    omega_m=0.31,
                ),
                _row(
                    sample_id=12,
                    chi2_cmb=4.9,
                    chi2_total=5.3,
                    drift_margin=0.2,
                    rsd_chi2_total=None,
                    h0=67.3,
                    omega_m=0.30,
                ),
            ]
            scan_jsonl.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

            proc = self._run(
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
                "--rank-by",
                "joint",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("MISSING_RSD_CHI2_FIELD", output)


if __name__ == "__main__":
    unittest.main()
