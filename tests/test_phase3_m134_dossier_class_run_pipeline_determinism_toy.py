import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANALYZE_SCRIPT = ROOT / "scripts" / "phase3_analyze_sigmatensor_lowz_scan.py"
DOSSIER_SCRIPT = ROOT / "scripts" / "phase3_make_sigmatensor_candidate_dossier_pack.py"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _write_toy_scan_jsonl(path: Path) -> None:
    row = {
        "schema": "phase3_sigmatensor_lowz_scan_row_v1",
        "status": "ok",
        "plan_point_id": "m134_det_plan_id_0001",
        "point_index": 0,
        "plan_source_sha256": "plan_sha",
        "scan_config_sha256": "scan_sha",
        "report_sha256": "report_sha",
        "results": {
            "chi2_total": 1.1,
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
    path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")


def _write_fake_class_bin(path: Path) -> None:
    script = """#!/usr/bin/env python3
import pathlib
import sys

_ = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
out = pathlib.Path("output")
out.mkdir(parents=True, exist_ok=True)
rows = [
    (2, 1000.0, 50.0, 100.0),
    (10, 3000.0, 120.0, 200.0),
    (100, 5000.0, 1000.0, 2000.0),
    (220, 6000.0, 800.0, 1200.0),
    (500, 4000.0, 600.0, 700.0),
    (1000, 1000.0, 300.0, 200.0),
]
lines = ["# l TT EE TE"]
for row in rows:
    lines.append(f"{row[0]} {row[1]:.6f} {row[2]:.6f} {row[3]:.6f}")
(out / "cl.dat").write_text("\\n".join(lines) + "\\n", encoding="utf-8")
print("fake_class_ok")
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _run_dossier(analysis_json: Path, outdir: Path, fake_class: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GSC_CLASS_BIN"] = str(fake_class)
    return subprocess.run(
        [
            sys.executable,
            str(DOSSIER_SCRIPT),
            "--analysis",
            str(analysis_json),
            "--outdir",
            str(outdir),
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
            "--fsigma8-extra-arg",
            "--z-start",
            "--fsigma8-extra-arg",
            "20",
            "--eft-extra-arg",
            "--n-steps",
            "--eft-extra-arg",
            "128",
            "--class-extra-arg",
            "--n-steps",
            "--class-extra-arg",
            "128",
            "--class-extra-arg",
            "--z-max",
            "--class-extra-arg",
            "5",
            "--include-class-run",
            "1",
            "--class-runner",
            "native",
            "--created-utc",
            "2000-01-01T00:00:00Z",
        ],
        cwd=str(ROOT.parent),
        text=True,
        capture_output=True,
        env=env,
    )


class TestPhase3M134DossierClassRunPipelineDeterminismToy(unittest.TestCase):
    def test_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            analysis_dir = td_path / "analysis"
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"
            fake_class = td_path / "fake_class.py"
            _write_toy_scan_jsonl(scan_jsonl)
            _write_fake_class_bin(fake_class)

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
            analysis_json = analysis_dir / "SCAN_ANALYSIS.json"

            proc_a = _run_dossier(analysis_json, out_a, fake_class)
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            proc_b = _run_dossier(analysis_json, out_b, fake_class)
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            cand_a = sorted((out_a / "candidates").glob("cand_01_*"))[0]
            cand_b = sorted((out_b / "candidates").glob("cand_01_*"))[0]

            self.assertEqual(_sha256(out_a / "DOSSIER_MANIFEST.json"), _sha256(out_b / "DOSSIER_MANIFEST.json"))
            self.assertEqual(_sha256(cand_a / "class_run" / "RUN_METADATA.json"), _sha256(cand_b / "class_run" / "RUN_METADATA.json"))
            self.assertEqual(
                _sha256(cand_a / "class_results" / "RESULTS_SUMMARY.json"),
                _sha256(cand_b / "class_results" / "RESULTS_SUMMARY.json"),
            )
            self.assertEqual(
                _sha256(cand_a / "spectra_sanity" / "SPECTRA_SANITY_REPORT.json"),
                _sha256(cand_b / "spectra_sanity" / "SPECTRA_SANITY_REPORT.json"),
            )


if __name__ == "__main__":
    unittest.main()
