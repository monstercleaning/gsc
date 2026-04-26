import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_pareto_report.py"


def _row(*, sample_id: int, status: str, H0: float, Omega_m: float, chi2_cmb: float, chi2_total: float, drift: float, invariants_ok: bool = True) -> dict:
    return {
        "sample_id": int(sample_id),
        "status": str(status),
        "model": "lcdm",
        "params_hash": f"m87_hash_{sample_id}",
        "params": {
            "H0": float(H0),
            "Omega_m": float(Omega_m),
            "Omega_Lambda": float(1.0 - Omega_m),
        },
        "chi2_total": float(chi2_total),
        "chi2_parts": {
            "cmb": {"chi2": float(chi2_cmb)},
            "drift": {"min_zdot_si": float(drift), "sign_ok": bool(drift > 0.0)},
            "invariants": {"ok": bool(invariants_ok)},
        },
        "drift": {
            "min_z_dot": float(drift),
            "all_positive": bool(drift > 0.0),
        },
        "invariants_ok": bool(invariants_ok),
    }


class TestPhase2M87ParetoReportRsdOverlayToy(unittest.TestCase):
    def _run(self, *args: str, cwd: Path) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)

    def test_overlay_is_optional_and_additive(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            scan_jsonl = tdp / "scan.jsonl"
            rsd_csv = tdp / "rsd.csv"
            out_off = tdp / "out_off"
            out_on = tdp / "out_on"

            rows = [
                _row(sample_id=1, status="ok", H0=67.4, Omega_m=0.315, chi2_cmb=4.5, chi2_total=5.2, drift=0.2),
                _row(sample_id=2, status="ok", H0=69.0, Omega_m=0.290, chi2_cmb=4.0, chi2_total=4.8, drift=0.1),
                _row(sample_id=3, status="skipped_drift_precheck", H0=70.0, Omega_m=0.280, chi2_cmb=6.0, chi2_total=6.5, drift=-0.1),
            ]
            scan_jsonl.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

            rsd_csv.write_text(
                "z,fsigma8,sigma,omega_m_ref,ref_key\n"
                "0.3,0.49,0.08,0.3,toy_a\n"
                "0.6,0.44,0.08,0.3,toy_b\n"
                "1.0,0.39,0.10,0.3,toy_c\n",
                encoding="utf-8",
            )

            proc_off = self._run(
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_off),
                "--status-filter",
                "ok_only",
                cwd=ROOT,
            )
            out_text_off = (proc_off.stdout or "") + (proc_off.stderr or "")
            self.assertEqual(proc_off.returncode, 0, msg=out_text_off)

            top_off = out_off / "pareto_top_positive.csv"
            self.assertTrue(top_off.is_file())
            with top_off.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                fieldnames = list(reader.fieldnames or [])
            self.assertNotIn("chi2_rsd_min", fieldnames)
            self.assertNotIn("chi2_combined", fieldnames)

            proc_on = self._run(
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_on),
                "--status-filter",
                "ok_only",
                "--rsd-overlay",
                "on",
                "--rsd-data",
                str(rsd_csv),
                "--rsd-weight",
                "1.0",
                cwd=ROOT,
            )
            out_text_on = (proc_on.stdout or "") + (proc_on.stderr or "")
            self.assertEqual(proc_on.returncode, 0, msg=out_text_on)

            top_on = out_on / "pareto_top_positive.csv"
            self.assertTrue(top_on.is_file())
            with top_on.open("r", encoding="utf-8", newline="") as fh:
                rows_csv = list(csv.DictReader(fh))
            self.assertGreaterEqual(len(rows_csv), 1)
            self.assertIn("chi2_rsd_min", rows_csv[0])
            self.assertIn("rsd_sigma8_0_best", rows_csv[0])
            self.assertIn("chi2_combined", rows_csv[0])
            self.assertIn("rsd_overlay_status", rows_csv[0])
            ok_rows = [row for row in rows_csv if str(row.get("rsd_overlay_status")) == "ok"]
            self.assertGreaterEqual(len(ok_rows), 1)
            self.assertNotEqual(str(ok_rows[0].get("chi2_combined", "")), "")

            summary = json.loads((out_on / "pareto_summary.json").read_text(encoding="utf-8"))
            overlay = summary.get("rsd_overlay") or {}
            self.assertTrue(bool(overlay.get("enabled")))
            self.assertIn("best_by_chi2_combined", overlay)

    def test_refine_score_chi2_combined_wires_refine_plan_meta(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            scan_jsonl = tdp / "scan.jsonl"
            rsd_csv = tdp / "rsd.csv"
            out_dir = tdp / "out"
            plan_out = tdp / "refine_plan.json"

            rows = [
                _row(sample_id=10, status="ok", H0=67.0, Omega_m=0.310, chi2_cmb=4.8, chi2_total=5.0, drift=0.2),
                _row(sample_id=11, status="ok", H0=68.1, Omega_m=0.300, chi2_cmb=4.9, chi2_total=4.9, drift=0.2),
            ]
            scan_jsonl.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
            rsd_csv.write_text(
                "z,fsigma8,sigma,omega_m_ref,ref_key\n"
                "0.4,0.48,0.09,0.3,toy_1\n"
                "0.9,0.40,0.10,0.3,toy_2\n",
                encoding="utf-8",
            )

            proc = self._run(
                "--jsonl",
                str(scan_jsonl),
                "--out-dir",
                str(out_dir),
                "--status-filter",
                "ok_only",
                "--rsd-overlay",
                "on",
                "--rsd-data",
                str(rsd_csv),
                "--refine-score",
                "chi2_combined",
                "--emit-refine-plan",
                str(plan_out),
                "--refine-top-k",
                "1",
                "--refine-n-per-seed",
                "1",
                cwd=ROOT,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(plan_out.read_text(encoding="utf-8"))
            selection = payload.get("selection") or {}
            self.assertTrue(bool(selection.get("rsd_overlay_enabled")))
            self.assertEqual(selection.get("refine_score"), "chi2_combined")


if __name__ == "__main__":
    unittest.main()
