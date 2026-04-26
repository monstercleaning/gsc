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
                "release_url": "https://github.com/org/repo/releases/tag/vL",
                "asset": asset_name,
                "sha256": sha,
            },
            "submission": {
                "type": "submission",
                "tier": "frozen",
                "tag": "vS",
                "release_url": "https://github.com/org/repo/releases/tag/vS",
                "asset": asset_name,
                "sha256": sha,
            },
            "referee_pack": {
                "type": "referee",
                "tier": "recommended",
                "tag": "vR",
                "release_url": "https://github.com/org/repo/releases/tag/vR",
                "asset": asset_name,
                "sha256": sha,
            },
            "toe_bundle": {
                "type": "toe",
                "tier": "recommended",
                "tag": "vT",
                "release_url": "https://github.com/org/repo/releases/tag/vT",
                "asset": asset_name,
                "sha256": sha,
            },
        },
    }
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


class TestOperatorColdstartSmoke(unittest.TestCase):
    def test_missing_assets_show_actionable_fix_commands(self):
        script = SCRIPTS / "operator_one_button.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            catalog = td / "catalog.json"
            _write_catalog(catalog, asset_name="missing.zip", sha=("a" * 64))

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog),
                    "--artifacts-dir",
                    str(td),
                    "--fetch-missing",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("Missing required canonical artifacts", out)
            self.assertIn("curl_cmd:", out)
            self.assertIn("verify_cmd:", out)
            self.assertIn("fetch_canonical_artifacts.sh", out)

    def test_dry_run_with_fake_artifacts_writes_report_schema(self):
        script = SCRIPTS / "operator_one_button.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toy.zip"
            asset.write_bytes(b"toy")
            sha = _sha256_file(asset)
            catalog = td / "catalog.json"
            report = td / "report.json"
            _write_catalog(catalog, asset_name=asset.name, sha=sha)

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog),
                    "--artifacts-dir",
                    str(td),
                    "--dry-run",
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertTrue(report.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("overall_status"), "PASS")
            self.assertIn("steps", payload)
            self.assertIn("summary", payload)
            self.assertEqual(len(payload.get("artifacts", [])), 4)

    def test_outdir_resolves_relative_report_and_is_forwarded_to_rc_check(self):
        script = SCRIPTS / "operator_one_button.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toy.zip"
            asset.write_bytes(b"toy")
            sha = _sha256_file(asset)
            catalog = td / "catalog.json"
            out_root = td / "out_root"
            _write_catalog(catalog, asset_name=asset.name, sha=sha)

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog),
                    "--artifacts-dir",
                    str(td),
                    "--dry-run",
                    "--out-dir",
                    str(out_root),
                    "--report",
                    "reports/operator.json",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn(f"[info] OUTDIR={out_root.resolve()}", out)
            self.assertIn("release_candidate_check.py", out)
            self.assertIn("--print-required", out)
            self.assertIn("--out-dir", out)

            report_path = out_root / "reports" / "operator.json"
            self.assertTrue(report_path.is_file())


if __name__ == "__main__":
    unittest.main()
