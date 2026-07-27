from pathlib import Path
import unittest

from tests._v12_layout import RETIRED_TREES, retired_artifact_skip_reason


ROOT = Path(__file__).resolve().parents[1]

# v12.6 reconciliation: the outreach/ pack was consciously retired from the
# v12 layout (declared in tests/_v12_layout.RETIRED_TREES; see CHANGELOG).
# The branding doc itself was relocated into archive/legacy_docs/ and still
# ships. This test now guards both facts: the shipped file is present and
# non-empty, and the retired tree stays absent — a half-restored outreach/
# directory must be consciously re-listed, not silently reintroduced.
SHIPPED_FILES = (
    ROOT / "archive" / "legacy_docs" / "AFFILIATION_AND_BRANDING.md",
)

RETIRED_OUTREACH = ROOT / "outreach"


class TestPhase4PublishBrandingPackPresentAndNonempty(unittest.TestCase):
    def test_files_exist_and_nonempty(self) -> None:
        for path in SHIPPED_FILES:
            self.assertTrue(path.is_file(), msg=f"missing required branding file: {path}")
            self.assertGreater(path.stat().st_size, 0, msg=f"expected non-empty file: {path}")
        self.assertIn("outreach/", RETIRED_TREES)
        self.assertFalse(
            RETIRED_OUTREACH.exists(),
            msg=(
                "outreach/ exists but is declared retired — either remove it or "
                "consciously un-retire it (tests/_v12_layout.RETIRED_TREES + this test)."
            ),
        )

    def test_transparency_key_phrases(self) -> None:
        reason = retired_artifact_skip_reason(
            ROOT, "outreach/labs_site_copy/labs_transparency.md"
        )
        if reason:
            self.skipTest(reason)
        text = (ROOT / "outreach" / "labs_site_copy" / "labs_transparency.md").read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("non-claims", lowered)
        self.assertIn("μ-running ≠ time variation", text)
        self.assertIn("white-hat", lowered)


if __name__ == "__main__":
    unittest.main()
