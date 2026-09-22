"""The preprint renderer takes citations and references from paper.bib, and fails on an unknown key."""

import re
import sys
import unittest
from pathlib import Path

JOSS = Path(__file__).resolve().parents[1] / "papers" / "paper_D_methodology" / "joss"
sys.path.insert(0, str(JOSS))
import render_preprint  # noqa: E402


class TestPreprintRender(unittest.TestCase):
    def setUp(self):
        self.md = (JOSS / "paper.md").read_text(encoding="utf-8")
        self.bib = (JOSS / "paper.bib").read_text(encoding="utf-8")

    def test_every_citation_resolves_and_every_reference_is_cited(self):
        tex = render_preprint.render(self.md, self.bib)
        cited = []
        for group in re.findall(r"\[([^\]]*@[^\]]+)\]", self.md):
            for key in (k.strip().lstrip("@") for k in group.split(";")):
                if key not in cited:
                    cited.append(key)
        references = tex.split(r"\section*{References}", 1)[1]
        self.assertEqual(references.count(r"\item "), len(cited))
        self.assertNotRegex(tex, r"\[@|\(@")
        self.assertIn(r"pdfauthor={Dimitar Baev}", tex)

    def test_an_unknown_citation_key_is_an_error(self):
        with self.assertRaises(KeyError):
            render_preprint.render(self.md + "\n\nSee [@NoSuchWork2099].\n", self.bib)


if __name__ == "__main__":
    unittest.main()
