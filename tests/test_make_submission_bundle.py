import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from tests._v12_layout import retired_artifact_skip_reason
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/

# v12.6: the v10.1 monolithic paper was consciously retired from the v12
# layout; this guard skips iff the retirement is declared (an undeclared
# absence raises). The v11 tree runs the same guard against the real file.
_RETIRED_SKIP = retired_artifact_skip_reason(ROOT, "GSC_Framework_v10_1_FINAL.tex")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@unittest.skipIf(bool(_RETIRED_SKIP), _RETIRED_SKIP or "")
class TestMakeSubmissionBundle(unittest.TestCase):
    def test_builder_creates_expected_zip_structure(self):
        script = ROOT / "scripts" / "make_submission_bundle.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            assets_zip = td / "paper_assets_fake.zip"
            out_zip = td / "submission.zip"

            manifest = {"inputs_sha256": {"v11.0.0/data/foo.txt": "00" * 32}}
            with zipfile.ZipFile(assets_zip, "w") as zf:
                zf.writestr("paper_assets/manifest.json", json.dumps(manifest) + "\n")
                zf.writestr("paper_assets/tables/test_table.txt", "table\n")
                zf.writestr("paper_assets/figures/test_figure.txt", "figure\n")

            expected_sha = _sha256_file(assets_zip)
            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    str(assets_zip),
                    str(out_zip),
                    "--expected-sha256",
                    expected_sha,
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)

            self.assertTrue(out_zip.is_file())
            with zipfile.ZipFile(out_zip, "r") as zf:
                names = zf.namelist()

            # Required top-level files.
            self.assertIn("GSC_Framework_v10_1_FINAL.tex", names)
            self.assertIn("SUBMISSION_README.md", names)

            # Required assets subtrees.
            self.assertIn("paper_assets/figures/test_figure.txt", names)
            self.assertIn("paper_assets/tables/test_table.txt", names)
            self.assertIn("paper_assets/manifest.json", names)

            # Safety: no absolute paths or path traversal.
            for n in names:
                self.assertFalse(n.startswith(("/", "\\")), msg=n)
                self.assertNotIn("..", Path(n).parts, msg=n)


if __name__ == "__main__":
    unittest.main()

