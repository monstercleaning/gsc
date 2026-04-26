from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "GSC_Framework_v10_1_FINAL.tex"
MD = ROOT / "GSC_Framework_v10_1_FINAL.md"
SUMMARY_SNIPPET_PATH = "paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.tex"


class TestPhase2M48PaperIncludesPhase2E2SummarySnippet(unittest.TestCase):
    def test_tex_has_phase2_gated_include_for_e2_summary_snippet(self) -> None:
        self.assertTrue(TEX.is_file())
        text = TEX.read_text(encoding="utf-8")
        self.assertIn("\\ifdefined\\GSCWITHPHASE2E2", text)
        self.assertIn(SUMMARY_SNIPPET_PATH, text)

    def test_md_mentions_phase2_summary_snippet(self) -> None:
        self.assertTrue(MD.is_file())
        text = MD.read_text(encoding="utf-8")
        self.assertIn("--phase2-e2-bundle", text)
        self.assertIn(SUMMARY_SNIPPET_PATH, text)


if __name__ == "__main__":
    unittest.main()
