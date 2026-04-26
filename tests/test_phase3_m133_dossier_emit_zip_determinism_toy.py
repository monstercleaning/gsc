import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZE_SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
DOSSIER_SCRIPT = ROOT / "scripts" / "phase3_make_sigmatensor_candidate_dossier_pack.py"


def _make_analysis(td_path: Path) -> Path:
    scan_jsonl = td_path / "scan.jsonl"
    analysis_dir = td_path / "analysis"
    row = {
        "schema": "phase3_sigmatensor_lowz_scan_row_v1",
        "status": "ok",
        "plan_point_id": "m133_zip_det_plan",
        "point_index": 0,
        "plan_source_sha256": "plan_sha",
        "scan_config_sha256": "scan_sha",
        "report_sha256": "report_sha",
        "results": {
            "chi2_total": 1.5,
            "ndof_total": 5,
            "chi2_blocks": {},
            "nuisances": {},
            "deltas": {},
        },
        "params": {
            "Omega_m": 0.30,
            "w0": -1.0,
            "lambda": 0.1,
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
    if proc_analysis.returncode != 0:
        raise AssertionError((proc_analysis.stdout or "") + (proc_analysis.stderr or ""))
    return analysis_dir / "SCAN_ANALYSIS.json"


class TestPhase3M133DossierEmitZipDeterminismToy(unittest.TestCase):
    def test_emit_zip_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            analysis_json = _make_analysis(td_path)

            out_a = td_path / "out_a"
            out_b = td_path / "out_b"
            zip_a = td_path / "a" / "dossier.zip"
            zip_b = td_path / "b" / "dossier.zip"

            base_cmd = [
                sys.executable,
                str(DOSSIER_SCRIPT),
                "--analysis",
                str(analysis_json),
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
                "--emit-zip",
                "1",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]

            proc_a = subprocess.run(
                [*base_cmd, "--outdir", str(out_a), "--zip-out", str(zip_a)],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            proc_b = subprocess.run(
                [*base_cmd, "--outdir", str(out_b), "--zip-out", str(zip_b)],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            self.assertEqual(zip_a.read_bytes(), zip_b.read_bytes())
            self.assertEqual(
                Path(str(zip_a) + ".sha256").read_text(encoding="utf-8"),
                Path(str(zip_b) + ".sha256").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
