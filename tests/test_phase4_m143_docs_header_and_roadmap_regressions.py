from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

PHASE4_DOCS = (
    ROOT / "archive" / "legacy_docs" / "REVIEW_START_HERE.md",
    ROOT / "docs" / "VERIFICATION_MATRIX.md",
    ROOT / "docs" / "FRAMES_UNITS_INVARIANTS.md",
    ROOT / "archive" / "legacy_docs" / "DM_DECISION_MEMO.md",
)

# v12.6: relocated into archive/legacy_docs/ (see CHANGELOG)
ROADMAP = ROOT / "archive" / "legacy_docs" / "GSC_Consolidated_Roadmap_v2.8.md"


class TestPhase4M143DocsHeaderAndRoadmapRegressions(unittest.TestCase):
    def test_phase4_docs_do_not_pin_m139_in_titles(self) -> None:
        for path in PHASE4_DOCS:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("(Phase-4 M139)", text, msg=f"stale milestone pin in {path.name}")

    def test_roadmap_contains_phase4_v28_anchor_terms(self) -> None:
        text = ROADMAP.read_text(encoding="utf-8")
        self.assertIn("Changelog v2.8", text)
        self.assertIn("CosmoFalsify", text)


if __name__ == "__main__":
    unittest.main()
