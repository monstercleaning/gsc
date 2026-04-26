import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "external_reviewer_feedback.md"


class TestPhase2M101ExternalReviewerFeedbackResponseMap(unittest.TestCase):
    def test_doc_has_required_sections_and_mappings(self) -> None:
        self.assertTrue(DOC.is_file())
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("## External expert feedback (Feb 2026)", text)
        self.assertIn("## Feedback summary", text)
        self.assertIn("## Response / current status mapping", text)
        self.assertIn("## Remaining gaps / next milestones", text)

        self.assertIn("docs/early_time_e2_status.md", text)
        self.assertIn("docs/structure_formation_status.md", text)
        self.assertIn("docs/sigma_field_origin_status.md", text)
        self.assertIn("docs/project_status_and_roadmap.md", text)
        self.assertIn("scripts/phase2_e2_scan.py", text)

    def test_docs_claims_lint_passes(self) -> None:
        script = ROOT / "scripts" / "docs_claims_lint.py"
        run = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        out = (run.stdout or "") + (run.stderr or "")
        self.assertEqual(run.returncode, 0, msg=out)


if __name__ == "__main__":
    unittest.main()
