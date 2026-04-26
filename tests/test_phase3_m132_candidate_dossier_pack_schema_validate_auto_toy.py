import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZE_SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
DOSSIER_SCRIPT = ROOT / "scripts" / "phase3_make_sigmatensor_candidate_dossier_pack.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M132CandidateDossierPackSchemaValidateAutoToy(unittest.TestCase):
    def test_schema_validate_auto(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            analysis_dir = td_path / "analysis"
            dossier_dir = td_path / "dossier"
            row = {
                "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                "status": "ok",
                "plan_point_id": "ppid_schema_1",
                "point_index": 0,
                "results": {"chi2_total": 1.0, "ndof_total": 4, "chi2_blocks": {}, "nuisances": {}, "deltas": {}},
                "params": {
                    "Omega_m": 0.3,
                    "w0": -1.0,
                    "lambda": 0.0,
                    "H0_km_s_Mpc": 67.4,
                    "Tcmb_K": 2.7255,
                    "N_eff": 3.046,
                    "Omega_r0_override": 0.0,
                    "sign_u0": 1,
                },
            }
            scan_jsonl.write_text(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")

            proc_analysis = subprocess.run(
                [
                    sys.executable,
                    str(ANALYZE_SCRIPT),
                    "--inputs",
                    str(scan_jsonl),
                    "--outdir",
                    str(analysis_dir),
                    "--top-k",
                    "1",
                    "--emit-reproduce",
                    "0",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_analysis.returncode, 0, msg=(proc_analysis.stdout or "") + (proc_analysis.stderr or ""))

            proc_dossier = subprocess.run(
                [
                    sys.executable,
                    str(DOSSIER_SCRIPT),
                    "--analysis",
                    str(analysis_dir / "SCAN_ANALYSIS.json"),
                    "--outdir",
                    str(dossier_dir),
                    "--top-k",
                    "1",
                    "--joint-extra-arg",
                    "--bao",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--sn",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--rsd",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--cmb",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--compare-lcdm",
                    "--joint-extra-arg",
                    "0",
                    "--fsigma8-extra-arg",
                    "--rsd",
                    "--fsigma8-extra-arg",
                    "0",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_dossier.returncode, 0, msg=(proc_dossier.stdout or "") + (proc_dossier.stderr or ""))

            proc_validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_SCRIPT),
                    "--auto",
                    "--json",
                    str(dossier_dir / "DOSSIER_MANIFEST.json"),
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_validate.returncode, 0, msg=(proc_validate.stdout or "") + (proc_validate.stderr or ""))


if __name__ == "__main__":
    unittest.main()
