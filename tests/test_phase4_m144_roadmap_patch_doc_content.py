from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
# v12.6: relocated into archive/legacy_docs/ (see CHANGELOG)
PATCH_DOC = ROOT / "archive" / "legacy_docs" / "GSC_Consolidated_Roadmap_v2.8.1_patch.md"


class TestPhase4M144RoadmapPatchDocContent(unittest.TestCase):
    def test_contains_required_referee_safe_phrases(self) -> None:
        text = PATCH_DOC.read_text(encoding="utf-8")
        self.assertIn("DR2 BAO/cosmology products", text)
        self.assertIn("Avoid fixing a calendar date", text)


if __name__ == "__main__":
    unittest.main()
