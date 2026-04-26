import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_dossier_quicklook_report.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class TestPhase3M136DossierQuicklookGatesFailToy(unittest.TestCase):
    def test_gate_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            dossier = td_path / "dossier"
            dossier.mkdir(parents=True, exist_ok=True)

            manifest = {
                "schema": "phase3_sigmatensor_candidate_dossier_manifest_v1",
                "tool": "phase3_make_sigmatensor_candidate_dossier_pack",
                "created_utc": "2000-01-01T00:00:00Z",
                "analysis_input": {"basename": "SCAN_ANALYSIS.json", "sha256": "a" * 64},
                "selection": {
                    "top_k": 1,
                    "ranks": [1],
                    "joint_extra_args": [],
                    "fsigma8_extra_args": [],
                    "eft_extra_args": [],
                    "class_extra_args": [],
                },
                "counts": {"candidates_selected": 1, "candidates_ok": 1, "candidates_error": 0},
                "candidates": [
                    {
                        "rank": 1,
                        "plan_point_id": "gate_fail_candidate",
                        "outdir_rel": "candidates/cand_01_gate_fail_candidate",
                        "status": "ok",
                        "subtools": {},
                    }
                ],
                "digests": {"dossier_file_table_sha256": "b" * 64},
            }
            _write_json(dossier / "DOSSIER_MANIFEST.json", manifest)
            _write_json(
                dossier
                / "candidates/cand_01_gate_fail_candidate/class_mapping/CLASS_MAPPING_REPORT.json",
                {
                    "residuals": {
                        "E": {"max_abs_rel": 1.0e-2},
                        "w": {"rms_dw": 1.0e-3},
                        "Omega_phi": {"max_abs": 1.0e-3},
                    }
                },
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--dossier",
                    str(dossier),
                    "--outdir",
                    str(td_path / "out"),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--require-max-rel-E-le",
                    "1e-6",
                    "--format",
                    "text",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 2, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertIn("PHASE3_DOSSIER_QUICKLOOK_FAILED", (proc.stderr or ""))


if __name__ == "__main__":
    unittest.main()
