import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"


class TestPhase3M131ScanAnalysisSelectsBestByChi2Toy(unittest.TestCase):
    def test_selects_best_and_dedupes_plan_point(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_path = td_path / "toy.jsonl"
            outdir = td_path / "out"
            lines = [
                {
                    "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                    "status": "ok",
                    "plan_point_id": "p1",
                    "point_index": 0,
                    "chi2_total": 5.0,
                    "params": {"Omega_m": 0.31, "w0": -1.0, "lambda": 0.1, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
                    "results": {"chi2_total": 5.0, "ndof_total": 10, "chi2_blocks": {"bao": 1.0}},
                    "plan_source_sha256": "ps1",
                    "scan_config_sha256": "sc1",
                    "report_sha256": "r1",
                },
                {
                    "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                    "status": "ok",
                    "plan_point_id": "p2",
                    "point_index": 1,
                    "chi2_total": 3.0,
                    "params": {"Omega_m": 0.30, "w0": -0.95, "lambda": 0.2, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
                    "results": {"chi2_total": 3.0, "ndof_total": 11, "chi2_blocks": {"sn": 1.0}},
                    "plan_source_sha256": "ps1",
                    "scan_config_sha256": "sc1",
                    "report_sha256": "r2",
                },
                {
                    "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                    "status": "error",
                    "plan_point_id": "p3",
                    "point_index": 2,
                    "params": {"Omega_m": 0.29, "w0": -0.90, "lambda": 0.3, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
                    "error": {"returncode": 2, "message": "PHASE3_LOWZ_JOINT_FAILED"},
                    "plan_source_sha256": "ps1",
                    "scan_config_sha256": "sc1",
                },
                {
                    "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                    "status": "ok",
                    "plan_point_id": "p1",
                    "point_index": 3,
                    "chi2_total": 6.0,
                    "params": {"Omega_m": 0.315, "w0": -1.1, "lambda": 0.4, "H0_km_s_Mpc": 67.4, "Tcmb_K": 2.7255, "N_eff": 3.046, "sign_u0": 1},
                    "results": {"chi2_total": 6.0, "ndof_total": 9, "chi2_blocks": {"bao": 2.0}},
                    "plan_source_sha256": "ps1",
                    "scan_config_sha256": "sc1",
                    "report_sha256": "r3",
                },
            ]
            with in_path.open("w", encoding="utf-8", newline="\n") as fh:
                for row in lines:
                    fh.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
                    fh.write("\n")
                fh.write("{not-json}\n")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--inputs",
                    str(in_path),
                    "--outdir",
                    str(outdir),
                    "--top-k",
                    "2",
                    "--metric",
                    "chi2_total",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            analysis_path = outdir / "SCAN_ANALYSIS.json"
            self.assertTrue(analysis_path.is_file())
            self.assertTrue((outdir / "SCAN_ANALYSIS.md").is_file())
            self.assertTrue((outdir / "BEST_CANDIDATES.csv").is_file())
            self.assertTrue((outdir / "REPRODUCE_TOP_CANDIDATES.sh").is_file())

            payload = json.loads(analysis_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase3_sigmatensor_lowz_scan_analysis_v1")
            counts = payload.get("counts", {})
            self.assertEqual(int(counts.get("rows_parsed", -1)), 4)
            self.assertEqual(int(counts.get("rows_invalid_json", -1)), 1)
            self.assertEqual(int(counts.get("dedup_unique_plan_point_id", -1)), 3)

            best = payload.get("best_candidates", [])
            self.assertEqual(len(best), 2)
            self.assertEqual(best[0].get("plan_point_id"), "p2")
            self.assertAlmostEqual(float(best[0].get("chi2_total")), 3.0, places=12)
            self.assertEqual(best[1].get("plan_point_id"), "p1")
            self.assertAlmostEqual(float(best[1].get("chi2_total")), 5.0, places=12)


if __name__ == "__main__":
    unittest.main()
