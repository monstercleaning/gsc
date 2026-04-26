from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZE_SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M131ScanAnalysisSchemaValidateAutoToy(unittest.TestCase):
    def test_schema_validate_auto(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_path = td_path / "scan.jsonl"
            outdir = td_path / "out"
            in_path.write_text(
                (
                    '{"schema":"phase3_sigmatensor_lowz_scan_row_v1","status":"ok","plan_point_id":"p1",'
                    '"point_index":0,"results":{"chi2_total":1.0,"ndof_total":5},'
                    '"params":{"Omega_m":0.3,"w0":-1.0,"lambda":0.0,"H0_km_s_Mpc":67.4,"Tcmb_K":2.7255,"N_eff":3.046,"sign_u0":1}}\n'
                ),
                encoding="utf-8",
            )

            proc_report = subprocess.run(
                [
                    sys.executable,
                    str(ANALYZE_SCRIPT),
                    "--inputs",
                    str(in_path),
                    "--outdir",
                    str(outdir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_report.returncode, 0, msg=(proc_report.stdout or "") + (proc_report.stderr or ""))

            proc_validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_SCRIPT),
                    "--auto",
                    "--json",
                    str(outdir / "SCAN_ANALYSIS.json"),
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_validate.returncode, 0, msg=(proc_validate.stdout or "") + (proc_validate.stderr or ""))


if __name__ == "__main__":
    unittest.main()
