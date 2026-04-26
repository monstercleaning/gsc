import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
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
                "tag": "vR1",
                "release_url": "https://example.com/R1",
                "asset": asset_name,
                "sha256": sha,
            },
            "toe_bundle": {
                "type": "toe",
                "tier": "recommended",
                "tag": "vT1",
                "release_url": "https://example.com/T1",
                "asset": asset_name,
                "sha256": sha,
            },
        },
    }
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


class TestReleaseCandidateCheckSmoke(unittest.TestCase):
    def test_rc_check_fails_when_catalog_sha_is_wrong(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=("0" * 64))

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td),
                    "--skip-status-doc-check",
                    "--skip-pointer-sot-lint",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("verify_all_canonical_artifacts", out)
            self.assertIn("sha256 mismatch", out)

    def test_rc_check_reports_missing_artifact_with_sha(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toy.zip"
            asset.write_bytes(b"toy")
            sha = _sha256_file(asset)
            catalog_path = td / "catalog.json"
            _write_catalog(catalog_path, asset_name="missing.zip", sha=sha)

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td),
                    "--skip-status-doc-check",
                    "--skip-pointer-sot-lint",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("missing required canonical artifact", out)
            self.assertIn("expected_asset: missing.zip", out)
            self.assertIn(f"expected_sha256: {sha}", out)
            self.assertIn("fetch_canonical_artifacts.sh", out)

    def test_rc_check_dry_run_succeeds_for_valid_toy_catalog(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toy.zip"
            asset.write_bytes(b"toy")
            sha = _sha256_file(asset)
            catalog_path = td / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=sha)

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td),
                    "--skip-status-doc-check",
                    "--skip-pointer-sot-lint",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("RC OK (dry-run)", out)

    def test_rc_check_json_report_written(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toy.zip"
            asset.write_bytes(b"toy")
            sha = _sha256_file(asset)
            catalog_path = td / "catalog.json"
            json_path = td / "rc.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=sha)

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td),
                    "--skip-status-doc-check",
                    "--skip-pointer-sot-lint",
                    "--dry-run",
                    "--json",
                    str(json_path),
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertTrue(json_path.is_file())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("overall_status"), "PASS")
            self.assertIn("required", payload)
            self.assertEqual(len(payload.get("required", [])), 4)
            self.assertIn("summary", payload)


if __name__ == "__main__":
    unittest.main()
