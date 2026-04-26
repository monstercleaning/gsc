import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

DOC = ROOT / "docs" / "external_reviewer_feedback.md"


class TestPhase2M99DocsExternalReviewerFeedbackCoverage(unittest.TestCase):
    def test_doc_exists_and_default_lint_coverage_includes_it(self) -> None:
        import docs_claims_lint as lint  # noqa: E402

        self.assertTrue(DOC.is_file())
        self.assertIn("docs/external_reviewer_feedback.md", set(lint.DEFAULT_REL_FILES))

    def test_doc_contains_claim_safe_scope_disclaimers(self) -> None:
        text = " ".join(DOC.read_text(encoding="utf-8").lower().split())
        self.assertIn("compressed cmb priors", text)
        self.assertIn("shift parameters", text)
        self.assertIn("not compute full cmb anisotropy spectra", text)
        self.assertIn("conceptual motivation only", text)
        self.assertIn("do not claim dark matter is solved", text)
        self.assertIn("linear-theory", text)
        self.assertIn("approximate diagnostics", text)

    def test_repo_docs_claims_lint_passes(self) -> None:
        script = SCRIPTS / "docs_claims_lint.py"
        run = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        out = (run.stdout or "") + (run.stderr or "")
        self.assertEqual(run.returncode, 0, msg=out)


if __name__ == "__main__":
    unittest.main()
