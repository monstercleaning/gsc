from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    ROOT / "docs" / "AFFILIATION_AND_BRANDING.md",
    ROOT / "outreach" / "labs_site_copy" / "labs_index.md",
    ROOT / "outreach" / "labs_site_copy" / "labs_gsc.md",
    ROOT / "outreach" / "labs_site_copy" / "labs_paper2.md",
    ROOT / "outreach" / "labs_site_copy" / "labs_cosmofalsify.md",
    ROOT / "outreach" / "labs_site_copy" / "labs_transparency.md",
    ROOT / "outreach" / "labs_site_copy" / "labs_press_kit.md",
    ROOT / "outreach" / "templates" / "email_researcher_feedback.md",
    ROOT / "outreach" / "templates" / "email_oss_maintainer_feedback.md",
    ROOT / "outreach" / "templates" / "email_journalist_pitch.md",
)


class TestPhase4PublishBrandingPackPresentAndNonempty(unittest.TestCase):
    def test_files_exist_and_nonempty(self) -> None:
        for path in REQUIRED_FILES:
            self.assertTrue(path.is_file(), msg=f"missing required branding/outreach file: {path}")
            self.assertGreater(path.stat().st_size, 0, msg=f"expected non-empty file: {path}")

    def test_transparency_key_phrases(self) -> None:
        text = (ROOT / "outreach" / "labs_site_copy" / "labs_transparency.md").read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("non-claims", lowered)
        self.assertIn("μ-running ≠ time variation", text)
        self.assertIn("white-hat", lowered)


if __name__ == "__main__":
    unittest.main()
