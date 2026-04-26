from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "GSC_Framework_v10_1_FINAL.tex"
MD = ROOT / "GSC_Framework_v10_1_FINAL.md"

TEX_BEGIN = "% === PHASE2_E2_SNIPPETS_BEGIN ==="
TEX_END = "% === PHASE2_E2_SNIPPETS_END ==="
MD_BEGIN = "<!-- PHASE2_E2_SNIPPETS_BEGIN -->"
MD_END = "<!-- PHASE2_E2_SNIPPETS_END -->"


def _extract_block(text: str, begin: str, end: str) -> str:
    start = text.index(begin)
    stop = text.index(end, start + len(begin))
    return text[start:stop]


class TestPhase2M98PaperIncludesRgSnippets(unittest.TestCase):
    def test_tex_phase2_block_mentions_rg_snippets(self) -> None:
        self.assertTrue(TEX.is_file())
        text = TEX.read_text(encoding="utf-8")
        block = _extract_block(text, TEX_BEGIN, TEX_END)
        self.assertIn("phase2\\_sf\\_fsigma8.tex", block)
        self.assertIn("phase2\\_rg\\_flow\\_table.tex", block)
        self.assertIn("phase2\\_rg\\_pade\\_fit.tex", block)

    def test_md_phase2_block_mentions_rg_snippets(self) -> None:
        self.assertTrue(MD.is_file())
        text = MD.read_text(encoding="utf-8")
        block = _extract_block(text, MD_BEGIN, MD_END)
        self.assertIn("phase2_sf_fsigma8.tex", block)
        self.assertIn("phase2_rg_flow_table.tex", block)
        self.assertIn("phase2_rg_pade_fit.tex", block)


if __name__ == "__main__":
    unittest.main()
