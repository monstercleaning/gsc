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


def _write_toy_scan_jsonl(path: Path) -> None:
    row = {
        "schema": "phase3_sigmatensor_lowz_scan_row_v1",
        "status": "ok",
        "plan_point_id": "m134_smoke_plan_id_0001",
        "point_index": 0,
        "plan_source_sha256": "plan_sha",
        "scan_config_sha256": "scan_sha",
        "report_sha256": "report_sha",
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


class TestPhase3M134DossierClassRunPipelineSmokeToy(unittest.TestCase):
    def test_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            scan_jsonl = td_path / "scan.jsonl"
            analysis_dir = td_path / "analysis"
            dossier_dir = td_path / "dossier"
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

            env = os.environ.copy()
            env["GSC_CLASS_BIN"] = str(fake_class)

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
            self.assertEqual(proc_dossier.returncode, 0, msg=(proc_dossier.stdout or "") + (proc_dossier.stderr or ""))

            cand_dirs = sorted((dossier_dir / "candidates").glob("cand_01_*"))
            self.assertEqual(len(cand_dirs), 1)
            cand = cand_dirs[0]

            self.assertTrue((cand / "class_run" / "RUN_METADATA.json").is_file())
            self.assertTrue((cand / "class_results" / "RESULTS_SUMMARY.json").is_file())
            self.assertTrue((cand / "spectra_sanity" / "SPECTRA_SANITY_REPORT.json").is_file())

            sanity_payload = json.loads((cand / "spectra_sanity" / "SPECTRA_SANITY_REPORT.json").read_text(encoding="utf-8"))
            tt_metrics = sanity_payload.get("tt_metrics")
            self.assertIsInstance(tt_metrics, dict)
            self.assertIs(tt_metrics.get("has_tt"), True)


if __name__ == "__main__":
    unittest.main()
