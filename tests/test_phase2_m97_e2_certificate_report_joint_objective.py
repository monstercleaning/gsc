import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_certificate_report.py"


class TestPhase2M97E2CertificateReportJointObjective(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def test_joint_summary_and_invalid_json_counts(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            out_ok = td_path / "cert_ok_only"
            out_any = td_path / "cert_any"

            rows = [
                {
                    "params_hash": "h_ok_cmb",
                    "status": "ok",
                    "plan_point_id": "p3",
                    "chi2_total": 10.0,
                    "chi2_cmb": 2.0,
                    "microphysics_plausible_ok": True,
                },
                {
                    "params_hash": "h_joint_b",
                    "status": "ok",
                    "plan_point_id": "p2",
                    "chi2_total": 12.0,
                    "chi2_cmb": 2.3,
                    "chi2_joint_total": 4.0,
                    "rsd_chi2_field_used": "rsd_chi2_total",
                    "rsd_chi2_weight": 1.0,
                    "rsd_transfer_model": "eh98_nowiggle",
                    "rsd_primordial_ns": 0.965,
                    "rsd_primordial_k_pivot_mpc": 0.05,
                    "rsd_dataset_sha256": "a" * 64,
                    "microphysics_plausible_ok": True,
                },
                {
                    "params_hash": "h_joint_a",
                    "status": "ok",
                    "plan_point_id": "p1",
                    "chi2_total": 13.0,
                    "chi2_cmb": 2.4,
                    "chi2_joint_total": 4.0,
                    "rsd_chi2_field_used": "rsd_chi2_total",
                    "rsd_chi2_weight": 1.0,
                    "microphysics_plausible_ok": True,
                },
                {
                    "params_hash": "h_no_chi2",
                    "status": "ok",
                    "microphysics_plausible_ok": True,
                },
                {
                    "params_hash": "h_unknown",
                    "chi2_total": 9.0,
                    "chi2_cmb": 1.9,
                    "microphysics_plausible_ok": True,
                },
                {
                    "params_hash": "h_error",
                    "status": "error",
                    "error": "MISSING_RSD_CHI2_FIELD_FOR_JOINT_OBJECTIVE: no rsd field",
                },
            ]
            with jsonl.open("w", encoding="utf-8") as fh:
                fh.write("not json\n")
                for row in rows:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")

            proc_ok = self._run(
                "--jsonl",
                str(jsonl),
                "--outdir",
                str(out_ok),
                "--eligible-status",
                "ok_only",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            )
            self.assertEqual(proc_ok.returncode, 0, msg=(proc_ok.stdout or "") + (proc_ok.stderr or ""))

            payload_ok = json.loads((out_ok / "e2_certificate.json").read_text(encoding="utf-8"))
            self.assertEqual(payload_ok.get("schema"), "phase2_e2_certificate_v1")
            self.assertEqual((payload_ok.get("input_summary") or {}).get("n_records_invalid_json"), 1)
            self.assertEqual((payload_ok.get("input_summary") or {}).get("n_records_total"), 6)

            best_cmb_ok = payload_ok.get("best_cmb") or {}
            self.assertEqual(best_cmb_ok.get("params_hash"), "h_ok_cmb")
            best_joint_ok = payload_ok.get("best_joint") or {}
            self.assertEqual(best_joint_ok.get("params_hash"), "h_joint_a")
            self.assertEqual(best_joint_ok.get("plan_point_id"), "p1")
            self.assertEqual(best_joint_ok.get("rsd_chi2_field_used"), "rsd_chi2_total")
            self.assertEqual(float(best_joint_ok.get("rsd_chi2_weight")), 1.0)

            markers = [str(row.get("key")) for row in ((payload_ok.get("preconditions") or {}).get("markers_top") or [])]
            self.assertIn("MISSING_RSD_CHI2_FIELD_FOR_JOINT_OBJECTIVE", markers)

            proc_any = self._run(
                "--jsonl",
                str(jsonl),
                "--outdir",
                str(out_any),
                "--eligible-status",
                "any_eligible",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            )
            self.assertEqual(proc_any.returncode, 0, msg=(proc_any.stdout or "") + (proc_any.stderr or ""))

            payload_any = json.loads((out_any / "e2_certificate.json").read_text(encoding="utf-8"))
            best_cmb_any = payload_any.get("best_cmb") or {}
            self.assertEqual(best_cmb_any.get("params_hash"), "h_unknown")
            self.assertEqual((payload_any.get("input_summary") or {}).get("eligible_status_filter"), "any_eligible")


if __name__ == "__main__":
    unittest.main()
