import tempfile
import unittest
import zipfile
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import bundle_tex_drift_detector as btd  # noqa: E402


def _make_submission_zip(path: Path, tex_content: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("GSC_Framework_v10_1_FINAL.tex", tex_content)


class TestBundleTexDriftDetector(unittest.TestCase):
    def test_match_has_no_warning(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            tex = td / "repo.tex"
            tex.write_text("% same\n", encoding="utf-8")
            bundle = td / "submission.zip"
            _make_submission_zip(bundle, "% same\n")

            out = btd.compare_bundle_tex_vs_repo(bundle, tex)
            self.assertTrue(out["match"])
            self.assertEqual(out["sha_bundle"], out["sha_repo"])
            self.assertIsNone(out["warning"])

    def test_mismatch_warns_and_has_hint_cmds(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            tex = td / "repo.tex"
            tex.write_text("% repo\n", encoding="utf-8")
            bundle = td / "submission.zip"
            _make_submission_zip(bundle, "% bundle\n")

            out = btd.compare_bundle_tex_vs_repo(bundle, tex)
            self.assertFalse(out["match"])
            self.assertNotEqual(out["sha_bundle"], out["sha_repo"])
            self.assertIn("differs", str(out["warning"]))
            hints = out.get("hint_cmds", [])
            self.assertGreaterEqual(len(hints), 2)
            self.assertTrue(any("diff -u" in h for h in hints))
            self.assertTrue(any("unzip -p" in h for h in hints))


if __name__ == "__main__":
    unittest.main()

