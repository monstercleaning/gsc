import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZE_SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
DOSSIER_SCRIPT = ROOT / "scripts" / "phase3_make_sigmatensor_candidate_dossier_pack.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _make_analysis(td_path: Path) -> Path:
    scan_jsonl = td_path / "scan.jsonl"
    analysis_dir = td_path / "analysis"
    row = {
        "schema": "phase3_sigmatensor_lowz_scan_row_v1",
        "status": "ok",
        "plan_point_id": "ppid_det_0001",
        "point_index": 0,
        "results": {"chi2_total": 2.0, "ndof_total": 7, "chi2_blocks": {}, "nuisances": {}, "deltas": {}},
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


class TestPhase3M132CandidateDossierPackDeterminismToy(unittest.TestCase):
    def test_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            analysis_json = _make_analysis(td_path)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

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
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]

            proc_a = subprocess.run([*base_cmd, "--outdir", str(out_a)], cwd=str(ROOT.parent), text=True, capture_output=True)
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            proc_b = subprocess.run([*base_cmd, "--outdir", str(out_b)], cwd=str(ROOT.parent), text=True, capture_output=True)
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            self.assertEqual(_sha256(out_a / "DOSSIER_MANIFEST.json"), _sha256(out_b / "DOSSIER_MANIFEST.json"))
            self.assertEqual(_sha256(out_a / "DOSSIER_MANIFEST.md"), _sha256(out_b / "DOSSIER_MANIFEST.md"))
            self.assertEqual(_sha256(out_a / "REPRODUCE_ALL.sh"), _sha256(out_b / "REPRODUCE_ALL.sh"))

            cand_a = sorted((out_a / "candidates").glob("cand_01_*"))[0]
            cand_b = sorted((out_b / "candidates").glob("cand_01_*"))[0]
            self.assertEqual(
                _sha256(cand_a / "joint" / "LOWZ_JOINT_REPORT.json"),
                _sha256(cand_b / "joint" / "LOWZ_JOINT_REPORT.json"),
            )

            for rel in ("DOSSIER_MANIFEST.json", "DOSSIER_MANIFEST.md", "REPRODUCE_ALL.sh"):
                text = (out_a / rel).read_text(encoding="utf-8")
                for token in ABS_TOKENS:
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
