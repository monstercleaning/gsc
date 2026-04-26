import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestVerifyReleaseBundle(unittest.TestCase):
    def test_verifier_accepts_toy_bundle(self):
        script = ROOT / "scripts" / "verify_release_bundle.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = td / "paper_assets_v10.1.1-late-time-r2.zip"

            manifest = {"inputs_sha256": {"v11.0.0/data/foo.txt": "00" * 32}}
            with zipfile.ZipFile(zp, "w") as zf:
                zf.writestr("paper_assets/manifest.json", json.dumps(manifest) + "\n")
                zf.writestr("paper_assets/tables/test.txt", "table\n")
                zf.writestr("paper_assets/figures/test.txt", "figure\n")

            expected = _sha256_file(zp)
            r = subprocess.run(
                [sys.executable, str(script), str(zp), "--expected-sha256", expected],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("OK:", out)

    def test_verifier_rejects_absolute_zip_entries(self):
        script = ROOT / "scripts" / "verify_release_bundle.py"

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = td / "bad.zip"

            manifest = {"inputs_sha256": {"v11.0.0/data/foo.txt": "00" * 32}}
            with zipfile.ZipFile(zp, "w") as zf:
                zf.writestr("paper_assets/manifest.json", json.dumps(manifest) + "\n")
                zf.writestr("paper_assets/tables/test.txt", "table\n")
                zf.writestr("paper_assets/figures/test.txt", "figure\n")
                zf.writestr("/abs.txt", "oops\n")

            expected = _sha256_file(zp)
            r = subprocess.run(
                [sys.executable, str(script), str(zp), "--expected-sha256", expected],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("absolute path", out)

    def test_verifier_rejects_users_path_in_manifest(self):
        script = ROOT / "scripts" / "verify_release_bundle.py"

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = td / "bad_manifest.zip"

            # Must be rejected (machine-specific absolute path).
            manifest = {"cwd": "/Users/example/repo", "inputs_sha256": {"v11.0.0/data/foo.txt": "00" * 32}}
            with zipfile.ZipFile(zp, "w") as zf:
                zf.writestr("paper_assets/manifest.json", json.dumps(manifest) + "\n")
                zf.writestr("paper_assets/tables/test.txt", "table\n")
                zf.writestr("paper_assets/figures/test.txt", "figure\n")

            expected = _sha256_file(zp)
            r = subprocess.run(
                [sys.executable, str(script), str(zp), "--expected-sha256", expected],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("/Users/", out)


if __name__ == "__main__":
    unittest.main()
