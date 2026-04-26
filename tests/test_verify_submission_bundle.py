import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/


class TestVerifySubmissionBundle(unittest.TestCase):
    def test_verifier_accepts_toy_submission_bundle(self):
        script = ROOT / "scripts" / "verify_submission_bundle.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = td / "submission.zip"

            # Minimal TeX that uses the same macros our verifier expands.
            tex = r"""
\documentclass{article}
\usepackage{graphicx}
\providecommand{\GSCAssetsDir}{paper_assets}
\providecommand{\GSCFiguresDir}{\GSCAssetsDir/figures}
\providecommand{\GSCTablesDir}{\GSCAssetsDir/tables}
\newcommand{\GSCInputAsset}[1]{\input{#1}}
\newcommand{\GSCIncludeFigure}[2][]{\includegraphics{#2}}
\begin{document}
\GSCInputAsset{\GSCTablesDir/bestfit_summary.tex}
\GSCIncludeFigure{\GSCFiguresDir/figure_A.png}
\end{document}
"""

            manifest = {"inputs_sha256": {"v11.0.0/data/foo.txt": "00" * 32}}
            with zipfile.ZipFile(zp, "w") as zf:
                zf.writestr("GSC_Framework_v10_1_FINAL.tex", tex.lstrip())
                zf.writestr("SUBMISSION_README.md", "readme\n")
                zf.writestr("paper_assets/manifest.json", json.dumps(manifest) + "\n")
                zf.writestr("paper_assets/tables/bestfit_summary.tex", "table\n")
                zf.writestr("paper_assets/figures/figure_A.png", b"\x89PNG\r\n\x1a\n")  # header only

            r = subprocess.run(
                [sys.executable, str(script), str(zp)],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("OK: submission bundle verified", out)

    def test_verifier_rejects_docs_popular(self):
        script = ROOT / "scripts" / "verify_submission_bundle.py"

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = td / "bad.zip"

            tex = r"\documentclass{article}\begin{document}x\end{document}"
            with zipfile.ZipFile(zp, "w") as zf:
                zf.writestr("GSC_Framework_v10_1_FINAL.tex", tex)
                zf.writestr("paper_assets/tables/a.txt", "t\n")
                zf.writestr("paper_assets/figures/a.txt", "f\n")
                zf.writestr("docs/popular/TOE_and_big_picture.md", "nope\n")

            r = subprocess.run([sys.executable, str(script), str(zp)], capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("docs/popular", out)

    def test_verifier_rejects_macos_junk(self):
        script = ROOT / "scripts" / "verify_submission_bundle.py"

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = td / "bad_macos.zip"

            tex = r"\documentclass{article}\begin{document}x\end{document}"
            with zipfile.ZipFile(zp, "w") as zf:
                zf.writestr("GSC_Framework_v10_1_FINAL.tex", tex)
                zf.writestr("paper_assets/tables/a.txt", "t\n")
                zf.writestr("paper_assets/figures/a.txt", "f\n")
                zf.writestr("__MACOSX/._junk", "x\n")

            r = subprocess.run([sys.executable, str(script), str(zp)], capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("macOS junk", out)


if __name__ == "__main__":
    unittest.main()

