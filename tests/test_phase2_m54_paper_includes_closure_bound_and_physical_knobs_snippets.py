from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "GSC_Framework_v10_1_FINAL.tex"
MD = ROOT / "GSC_Framework_v10_1_FINAL.md"

TEX_BEGIN = "% === PHASE2_E2_SNIPPETS_BEGIN ==="
TEX_END = "% === PHASE2_E2_SNIPPETS_END ==="
MD_BEGIN = "<!-- PHASE2_E2_SNIPPETS_BEGIN -->"
MD_END = "<!-- PHASE2_E2_SNIPPETS_END -->"

TEX_AGGREGATOR = "paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.tex"
MD_AGGREGATOR = "paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.md"


def _extract_block(text: str, begin: str, end: str) -> str:
    start = text.index(begin)
    stop = text.index(end, start + len(begin))
    return text[start:stop]


class TestPhase2M54PaperIncludesClosureBoundAndPhysicalKnobsSnippets(unittest.TestCase):
    def test_tex_phase2_block_includes_three_canonical_snippets(self) -> None:
        self.assertTrue(TEX.is_file())
        text = TEX.read_text(encoding="utf-8")
        self.assertIn("\\ifdefined\\GSCWITHPHASE2E2", text)
        self.assertIn(TEX_BEGIN, text)
        self.assertIn(TEX_END, text)
        block = _extract_block(text, TEX_BEGIN, TEX_END)
        self.assertIn(TEX_AGGREGATOR, block)

    def test_md_phase2_block_mentions_three_canonical_md_snippets(self) -> None:
        self.assertTrue(MD.is_file())
        text = MD.read_text(encoding="utf-8")
        self.assertIn(MD_BEGIN, text)
        self.assertIn(MD_END, text)
        block = _extract_block(text, MD_BEGIN, MD_END)
        self.assertIn(MD_AGGREGATOR, block)


if __name__ == "__main__":
    unittest.main()
