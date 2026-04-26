import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestVerifyAllCanonicalArtifacts(unittest.TestCase):
    def test_catalog_schema_and_keys_are_valid(self):
        import verify_all_canonical_artifacts as m  # noqa: E402

        catalog = m.load_catalog(ROOT / "canonical_artifacts.json")
        self.assertEqual(catalog.get("schema_version"), 2)

        artifacts = catalog.get("artifacts")
        self.assertIsInstance(artifacts, dict)
        self.assertEqual(set(artifacts.keys()), {"late_time", "submission", "referee_pack", "toe_bundle"})

        normalized = catalog.get("_normalized_artifacts")
        self.assertIsInstance(normalized, list)
        self.assertEqual(len(normalized), 4)

        types = {a["type"] for a in normalized}
        self.assertIn("late-time", types)
        self.assertIn("submission", types)
        self.assertIn("referee", types)
        self.assertIn("toe", types)

        re_sha = re.compile(r"^[0-9a-f]{64}$")
        re_asset_base = re.compile(
            r"^(paper_assets_.*\.zip|submission_bundle_.*\.zip|referee_pack_.*\.zip|toe_bundle_.*\.zip)$"
        )
        for art in normalized:
            self.assertRegex(art["sha256"], re_sha)
            self.assertRegex(Path(str(art["asset"])).name, re_asset_base)

    def test_cli_dry_run_reports_missing_asset(self):
        script = SCRIPTS / "verify_all_canonical_artifacts.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            catalog = {
                "schema_version": 2,
                "artifacts": {
                    "late_time": {
                        "type": "late-time",
                        "tier": "frozen",
                        "tag": "vL",
                        "release_url": "https://example.com/L",
                        "asset": "paper_assets_late.zip",
                        "sha256": "0" * 64,
                    },
                    "submission": {
                        "type": "submission",
                        "tier": "frozen",
                        "tag": "vS",
                        "release_url": "https://example.com/S",
                        "asset": "submission_bundle_s.zip",
                        "sha256": "0" * 64,
                    },
                    "referee_pack": {
                        "type": "referee",
                        "tier": "recommended",
                        "tag": "vR1",
                        "release_url": "https://example.com/R1",
                        "asset": "referee_pack_r1.zip",
                        "sha256": "0" * 64,
                    },
                    "toe_bundle": {
                        "type": "toe",
                        "tier": "recommended",
                        "tag": "vT1",
                        "release_url": "https://example.com/T1",
                        "asset": "missing_toe.zip",
                        "sha256": "0" * 64,
                    },
                },
            }
            catalog_path = td / "catalog.json"
            catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td),
                    "--dry-run",
                    "--skip-status-doc-check",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("missing asset file", out)

    def test_cli_dry_run_succeeds_for_valid_toy_catalog(self):
        script = SCRIPTS / "verify_all_canonical_artifacts.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toe_bundle_toy.zip"
            asset.write_bytes(b"toe")
            sha = _sha256_file(asset)

            catalog = {
                "schema_version": 2,
                "artifacts": {
                    "late_time": {
                        "type": "late-time",
                        "tier": "frozen",
                        "tag": "vL",
                        "release_url": "https://example.com/L",
                        "asset": asset.name,
                        "sha256": sha,
                    },
                    "submission": {
                        "type": "submission",
                        "tier": "frozen",
                        "tag": "vS",
                        "release_url": "https://example.com/S",
                        "asset": asset.name,
                        "sha256": sha,
                    },
                    "referee_pack": {
                        "type": "referee",
                        "tier": "recommended",
                        "tag": "vR1",
                        "release_url": "https://example.com/R1",
                        "asset": asset.name,
                        "sha256": sha,
                    },
                    "toe_bundle": {
                        "type": "toe",
                        "tier": "recommended",
                        "tag": "vT1",
                        "release_url": "https://example.com/T1",
                        "asset": asset.name,
                        "sha256": sha,
                    },
                },
            }
            catalog_path = td / "catalog.json"
            catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog_path),
                    "--artifacts-dir",
                    str(td),
                    "--dry-run",
                    "--skip-status-doc-check",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("[ok] sha256 toe_bundle", out)


if __name__ == "__main__":
    unittest.main()
