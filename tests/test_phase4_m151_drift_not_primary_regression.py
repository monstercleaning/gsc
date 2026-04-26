from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = ROOT / "v11.0.0" / "docs"

ALLOWLIST_DOCS = {
    DOCS_ROOT / "GSC_Consolidated_Roadmap_v2.8.md",
}

REQUIRED_SUPPORTING_DOCS = (
    DOCS_ROOT / "measurement_model.md",
    DOCS_ROOT / "reviewer_faq.md",
    DOCS_ROOT / "risk_register.md",
    DOCS_ROOT / "early_time_full_history.md",
    DOCS_ROOT / "paper_sanity_checklist.md",
    DOCS_ROOT / "popular" / "TOE_and_big_picture.md",
    DOCS_ROOT / "popular" / "holographic_rg_dictionary.md",
)


class TestPhase4M151DriftNotPrimaryRegression(unittest.TestCase):
    def test_docs_denylist_has_no_primary_drift_framing(self) -> None:
        forbidden_tokens = ("golden test", "primary falsifier")
        for path in sorted(DOCS_ROOT.rglob("*.md")):
            if path in ALLOWLIST_DOCS:
                continue
            text = path.read_text(encoding="utf-8").lower()
            for token in forbidden_tokens:
                self.assertNotIn(
                    token,
                    text,
                    msg=f"forbidden token '{token}' found in {path}",
                )

    def test_supporting_or_historical_wording_present_in_updated_docs(self) -> None:
        for path in REQUIRED_SUPPORTING_DOCS:
            text = path.read_text(encoding="utf-8").lower()
            self.assertTrue(
                ("historical" in text) or ("supporting" in text),
                msg=f"expected historical/supporting framing in {path}",
            )

    def test_framework_v10_1_final_has_deprecation_banner_and_heading(self) -> None:
        text = (ROOT / "v11.0.0" / "GSC_Framework_v10_1_FINAL.md").read_text(
            encoding="utf-8"
        )
        lower = text.lower()
        self.assertIn("historical v10.1 snapshot", lower)
        self.assertIn("deprecated as primary", lower)
        self.assertIn("# 8. redshift drift (historical; deprecated as primary)", lower)


if __name__ == "__main__":
    unittest.main()
