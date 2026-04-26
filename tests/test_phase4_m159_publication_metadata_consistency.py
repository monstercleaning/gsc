import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TAG = "v11.0.0-phase4-m159"


class TestPhase4M159PublicationMetadataConsistency(unittest.TestCase):
    def test_citation_primary_version_and_legacy_wording(self) -> None:
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn(f'version: "{EXPECTED_TAG}"', citation)
        self.assertIn("date-released:", citation)
        self.assertIn("Primary release tag", citation)
        self.assertNotIn("Canonical late-time release tag", citation)
        if "v10.1.1-late-time-r4" in citation:
            self.assertIn("historical provenance only", citation)

    def test_zenodo_version_matches_expected_tag(self) -> None:
        payload = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("version"), EXPECTED_TAG)

    def test_submission_checklists_have_required_human_steps(self) -> None:
        joss = (ROOT / "v11.0.0" / "docs" / "JOSS_SUBMISSION_CHECKLIST.md").read_text(encoding="utf-8")
        arxiv = (ROOT / "v11.0.0" / "docs" / "ARXIV_SUBMISSION_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("Mint Zenodo DOI for tag `v11.0.0-phase4-m159`", joss)
        self.assertIn("update `CITATION.cff` and `.zenodo.json`", joss)
        self.assertIn("Updated endorsement policy", arxiv)
        self.assertIn("arXiv endorsement help", arxiv)


if __name__ == "__main__":
    unittest.main()
