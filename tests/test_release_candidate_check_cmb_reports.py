import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_catalog(path: Path, *, asset_name: str, sha: str) -> None:
    catalog = {
        "schema_version": 2,
        "artifacts": {
            "late_time": {
                "type": "late-time",
                "tier": "frozen",
                "tag": "vL",
                "release_url": "https://example.com/L",
                "asset": asset_name,
                "sha256": sha,
            },
            "submission": {
                "type": "submission",
                "tier": "frozen",
                "tag": "vS",
                "release_url": "https://example.com/S",
                "asset": asset_name,
                "sha256": sha,
            },
            "referee_pack": {
                "type": "referee",
                "tier": "recommended",
                "tag": "vR",
                "release_url": "https://example.com/R",
                "asset": asset_name,
                "sha256": sha,
            },
            "toe_bundle": {
                "type": "toe",
                "tier": "recommended",
                "tag": "vT",
                "release_url": "https://example.com/T",
                "asset": asset_name,
                "sha256": sha,
            },
        },
    }
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


class TestReleaseCandidateCheckCMBReports(unittest.TestCase):
    def test_require_cmb_reports_fails_when_missing(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            out_root = td_p / "out"
            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td_p),
                    "--skip-status-doc-check",
                    "--skip-pointer-sot-lint",
                    "--dry-run",
                    "--out-dir",
                    str(out_root),
                    "--require-cmb-reports",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("required early-time CMB reports are missing", out)

    def test_require_cmb_reports_passes_with_valid_files(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            out_root = td_p / "out"
            early_time = out_root / "early_time"
            early_time.mkdir(parents=True, exist_ok=True)
            (early_time / "cmb_priors_report.json").write_text(
                json.dumps(
                    {
                        "schema_version": "phase2.m4.cmb_priors_report.v1",
                        "summary": {"model_count": 1},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (early_time / "cmb_priors_table.csv").write_text(
                "model_id,bestfit_file,key,prior,sigma,sigma_theory,pred,diag_pull,diag_contrib,chi2_model,ndof,method\n"
                "lcdm,/tmp/lcdm_bestfit.json,theta_star,0.01,1e-5,0,0.01,0,0,0,1,diag\n",
                encoding="utf-8",
            )

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td_p),
                    "--skip-status-doc-check",
                    "--skip-pointer-sot-lint",
                    "--dry-run",
                    "--out-dir",
                    str(out_root),
                    "--require-cmb-reports",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("validate_early_time_cmb_reports", out)


if __name__ == "__main__":
    unittest.main()
