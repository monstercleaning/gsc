import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZE_SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
DOSSIER_SCRIPT = ROOT / "scripts" / "phase3_make_sigmatensor_candidate_dossier_pack.py"
PORTABLE_LINT_SCRIPT = ROOT / "scripts" / "phase2_portable_content_lint.py"


class TestPhase3M132CandidateDossierPackPortableContentLintPassesToy(unittest.TestCase):
    def test_portable_content_lint_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            analysis_dir = td_path / "analysis"
            dossier_dir = td_path / "dossier"
            row = {
                "schema": "phase3_sigmatensor_lowz_scan_row_v1",
                "status": "ok",
                "plan_point_id": "ppid_lint_1",
                "point_index": 0,
                "results": {"chi2_total": 1.25, "ndof_total": 6, "chi2_blocks": {}, "nuisances": {}, "deltas": {}},
                "params": {
                    "Omega_m": 0.305,
                    "w0": -0.97,
                    "lambda": 0.05,
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

            proc_lint = subprocess.run(
                [
                    sys.executable,
                    str(PORTABLE_LINT_SCRIPT),
                    "--path",
                    str(dossier_dir),
                    "--format",
                    "text",
                    "--include-glob",
                    "*.json",
                    "--include-glob",
                    "*.md",
                    "--include-glob",
                    "*.csv",
                    "--include-glob",
                    "*.ini",
                    "--include-glob",
                    "*.sh",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_lint.returncode, 0, msg=(proc_lint.stdout or "") + (proc_lint.stderr or ""))


if __name__ == "__main__":
    unittest.main()
