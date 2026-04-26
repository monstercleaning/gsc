import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_dossier_quicklook_report.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _build_toy_dossier(path: Path) -> None:
    dossier = path
    cand1_rel = "candidates/cand_01_alpha12345678"
    cand2_rel = "candidates/cand_02_beta12345678"

    manifest = {
        "schema": "phase3_sigmatensor_candidate_dossier_manifest_v1",
        "tool": "phase3_make_sigmatensor_candidate_dossier_pack",
        "created_utc": "2000-01-01T00:00:00Z",
        "analysis_input": {"basename": "SCAN_ANALYSIS.json", "sha256": "x" * 64},
        "selection": {
            "top_k": 2,
            "ranks": [1, 2],
            "joint_extra_args": [],
            "fsigma8_extra_args": [],
            "eft_extra_args": [],
            "class_extra_args": [],
        },
        "counts": {"candidates_selected": 2, "candidates_ok": 1, "candidates_error": 1},
        "candidates": [
            {
                "rank": 1,
                "plan_point_id": "alpha1234567890",
                "outdir_rel": cand1_rel,
                "status": "ok",
                "subtools": {},
                "errors": [],
            },
            {
                "rank": 2,
                "plan_point_id": "beta1234567890",
                "outdir_rel": cand2_rel,
                "status": "error",
                "subtools": {},
                "errors": [{"tool": "joint", "marker": "", "message": "toy"}],
            },
        ],
        "digests": {"dossier_file_table_sha256": "y" * 64},
    }
    _write_json(dossier / "DOSSIER_MANIFEST.json", manifest)

    _write_json(
        dossier / cand1_rel / "joint" / "LOWZ_JOINT_REPORT.json",
        {
            "total": {"chi2": 12.0, "ndof": 8},
            "deltas": {"delta_chi2_total": -1.5},
            "blocks": {
                "bao": {"chi2": 2.0},
                "sn": {"chi2": 5.0},
                "cmb": {"chi2": 1.0},
                "rsd": {"chi2": 4.0},
            },
        },
    )
    _write_json(
        dossier / cand1_rel / "fsigma8" / "FSIGMA8_REPORT.json",
        {
            "rsd": {"chi2": 3.5},
            "sigma8": {"sigma8_0_used": 0.81, "sigma8_0_bestfit": 0.805},
        },
    )
    _write_json(
        dossier / cand1_rel / "class_mapping" / "CLASS_MAPPING_REPORT.json",
        {
            "residuals": {
                "E": {"max_abs_rel": 1.2e-3},
                "w": {"rms_dw": 2.3e-3},
                "Omega_phi": {"max_abs": 3.4e-3},
            },
            "gates": {"pass": True},
        },
    )
    _write_json(
        dossier / cand1_rel / "spectra_sanity" / "SPECTRA_SANITY_REPORT.json",
        {
            "tt_metrics": {"has_tt": True, "ell_max": 2500, "peak1_ell": 220.0},
        },
    )

    _write_json(
        dossier / cand2_rel / "joint" / "LOWZ_JOINT_REPORT.json",
        {
            "total": {"chi2": 20.0, "ndof": 10},
            "deltas": {"delta_chi2_total": 3.0},
            "blocks": {
                "bao": {"chi2": 6.0},
                "sn": {"chi2": 9.0},
            },
        },
    )


class TestPhase3M136DossierQuicklookReportDeterminismToy(unittest.TestCase):
    def test_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            dossier = td_path / "dossier"
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"
            dossier.mkdir(parents=True, exist_ok=True)
            _build_toy_dossier(dossier)

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--dossier",
                        str(dossier),
                        "--outdir",
                        str(outdir),
                        "--created-utc",
                        "2000-01-01T00:00:00Z",
                        "--format",
                        "json",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            for name in ("DOSSIER_QUICKLOOK.json", "DOSSIER_QUICKLOOK.csv", "DOSSIER_QUICKLOOK.md"):
                self.assertEqual(
                    _sha256(out_a / name),
                    _sha256(out_b / name),
                    msg=f"non-deterministic output for {name}",
                )

            text = (out_a / "DOSSIER_QUICKLOOK.json").read_text(encoding="utf-8") + (
                out_a / "DOSSIER_QUICKLOOK.md"
            ).read_text(encoding="utf-8")
            for token in ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\"):
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
