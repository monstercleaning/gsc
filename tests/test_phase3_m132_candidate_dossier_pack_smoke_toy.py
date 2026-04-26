import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZE_SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
DOSSIER_SCRIPT = ROOT / "scripts" / "phase3_make_sigmatensor_candidate_dossier_pack.py"


def _write_toy_scan_jsonl(path: Path) -> None:
    row = {
        "schema": "phase3_sigmatensor_lowz_scan_row_v1",
        "status": "ok",
        "plan_point_id": "abcDEF1234567890",
        "point_index": 0,
        "plan_source_sha256": "ps_toy",
        "scan_config_sha256": "sc_toy",
        "report_sha256": "rep_toy",
        "results": {
            "chi2_total": 1.0,
            "ndof_total": 4,
            "chi2_blocks": {},
            "nuisances": {},
            "deltas": {},
        },
        "params": {
            "Omega_m": 0.31,
            "w0": -0.95,
            "lambda": 0.2,
            "H0_km_s_Mpc": 67.4,
            "Tcmb_K": 2.7255,
            "N_eff": 3.046,
            "Omega_r0_override": 0.0,
            "sign_u0": 1,
        },
    }
    path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")


class TestPhase3M132CandidateDossierPackSmokeToy(unittest.TestCase):
    def test_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            analysis_dir = td_path / "analysis"
            dossier_dir = td_path / "dossier"
            _write_toy_scan_jsonl(scan_jsonl)

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
                    "--joint-extra-arg",
                    "--n-steps-bg",
                    "--joint-extra-arg",
                    "128",
                    "--fsigma8-extra-arg",
                    "--rsd",
                    "--fsigma8-extra-arg",
                    "0",
                    "--fsigma8-extra-arg",
                    "--n-steps-bg",
                    "--fsigma8-extra-arg",
                    "128",
                    "--fsigma8-extra-arg",
                    "--n-steps-growth",
                    "--fsigma8-extra-arg",
                    "128",
                    "--eft-extra-arg",
                    "--n-steps",
                    "--eft-extra-arg",
                    "128",
                    "--class-extra-arg",
                    "--n-steps",
                    "--class-extra-arg",
                    "128",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_dossier.returncode, 0, msg=(proc_dossier.stdout or "") + (proc_dossier.stderr or ""))

            self.assertTrue((dossier_dir / "DOSSIER_MANIFEST.json").is_file())
            self.assertTrue((dossier_dir / "DOSSIER_MANIFEST.md").is_file())
            self.assertTrue((dossier_dir / "REPRODUCE_ALL.sh").is_file())

            cand_dirs = sorted((dossier_dir / "candidates").glob("cand_01_*"))
            self.assertEqual(len(cand_dirs), 1)
            cand = cand_dirs[0]
            self.assertTrue((cand / "joint" / "LOWZ_JOINT_REPORT.json").is_file())
            self.assertTrue((cand / "fsigma8" / "FSIGMA8_REPORT.json").is_file())
            self.assertTrue((cand / "eft" / "EFT_EXPORT_SUMMARY.json").is_file())
            self.assertTrue((cand / "class" / "EXPORT_SUMMARY.json").is_file())


if __name__ == "__main__":
    unittest.main()
