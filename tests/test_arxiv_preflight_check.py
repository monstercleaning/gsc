import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members.items():
            zf.writestr(name, payload)


class TestArxivPreflightCheck(unittest.TestCase):
    def test_valid_bundle_passes(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zip_path = td / "submission.zip"
            _write_zip(
                zip_path,
                {
                    "GSC_Framework_v10_1_FINAL.tex": b"\\documentclass{article}",
                    "paper_assets/figures/fig_a.png": b"\x89PNG\r\n",
                    "paper_assets/tables/table_a.csv": b"k,v\n1,2\n",
                    "SUBMISSION_README.md": b"readme",
                },
            )
            rc = m.main([str(zip_path), "--skip-full-compile"])
            self.assertEqual(rc, 0)

    def test_generated_aux_fails(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zip_path = td / "submission.zip"
            _write_zip(
                zip_path,
                {
                    "GSC_Framework_v10_1_FINAL.tex": b"\\documentclass{article}",
                    "paper_assets/figures/fig_a.png": b"\x89PNG\r\n",
                    "paper_assets/tables/table_a.csv": b"k,v\n1,2\n",
                    "junk.aux": b"aux",
                },
            )
            rc = m.main([str(zip_path), "--skip-full-compile"])
            self.assertEqual(rc, 2)

    def test_symlink_entry_fails(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zip_path = td / "submission.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("GSC_Framework_v10_1_FINAL.tex", b"\\documentclass{article}")
                zf.writestr("paper_assets/figures/fig_a.png", b"\x89PNG\r\n")
                zf.writestr("paper_assets/tables/table_a.csv", b"k,v\n1,2\n")
                info = zipfile.ZipInfo("symlink_payload")
                info.external_attr = 0o120777 << 16
                zf.writestr(info, b"target")
            rc = m.main([str(zip_path), "--skip-full-compile"])
            self.assertEqual(rc, 2)

    def test_non_ascii_warns_but_passes(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zip_path = td / "submission.zip"
            _write_zip(
                zip_path,
                {
                    "GSC_Framework_v10_1_FINAL.tex": b"\\documentclass{article}",
                    "paper_assets/figures/fig_a.png": b"\x89PNG\r\n",
                    "paper_assets/tables/table_a.csv": b"k,v\n1,2\n",
                    "paper_assets/tables/таблица.csv": b"k,v\n1,2\n",
                },
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = m.main([str(zip_path), "--skip-full-compile"])
            self.assertEqual(rc, 0)
            self.assertIn("WARN: non-ASCII filename", out.getvalue())

    def test_forbidden_write18_fails(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zip_path = td / "submission.zip"
            _write_zip(
                zip_path,
                {
                    "GSC_Framework_v10_1_FINAL.tex": b"\\documentclass{article}\\immediate\\write18{echo x}",
                    "paper_assets/figures/fig_a.png": b"\x89PNG\r\n",
                    "paper_assets/tables/table_a.csv": b"k,v\n1,2\n",
                },
            )
            rc = m.main([str(zip_path), "--skip-full-compile"])
            self.assertEqual(rc, 2)

    def test_missing_tex_referenced_asset_fails(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zip_path = td / "submission.zip"
            tex = (
                b"\\documentclass{article}\n"
                b"\\newcommand{\\GSCFiguresDir}{paper_assets/figures}\n"
                b"\\GSCIncludeFigure{\\GSCFiguresDir/missing_figure.png}\n"
            )
            _write_zip(
                zip_path,
                {
                    "GSC_Framework_v10_1_FINAL.tex": tex,
                    "paper_assets/figures/fig_a.png": b"\x89PNG\r\n",
                    "paper_assets/tables/table_a.csv": b"k,v\n1,2\n",
                },
            )
            rc = m.main([str(zip_path), "--skip-full-compile"])
            self.assertEqual(rc, 2)

    def test_parse_compile_log_patterns(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        parsed = m._parse_compile_log(
            r"""
            Overfull \hbox (10.0pt too wide)
            There were undefined references.
            ! LaTeX Error: Something bad happened.
            """
        )
        self.assertTrue(parsed["fail_patterns"])
        self.assertTrue(parsed["warn_patterns"])

    def test_json_output_schema(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import arxiv_preflight_check as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zip_path = td / "submission.zip"
            json_path = td / "preflight.json"
            _write_zip(
                zip_path,
                {
                    "GSC_Framework_v10_1_FINAL.tex": b"\\documentclass{article}",
                    "paper_assets/figures/fig_a.png": b"\x89PNG\r\n",
                    "paper_assets/tables/table_a.csv": b"k,v\n1,2\n",
                },
            )
            rc = m.main([str(zip_path), "--skip-full-compile", "--json", str(json_path)])
            self.assertEqual(rc, 0)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("result"), "PASS")
            self.assertEqual(payload.get("overall_status"), "PASS")
            self.assertIn("metrics", payload)
            self.assertIn("steps", payload)
            self.assertIn("compile", payload)
            self.assertEqual(payload.get("compile", {}).get("status"), "SKIP")
            self.assertIn("compile_pdf", payload)
            self.assertFalse(payload.get("compile_pdf", {}).get("produced", True))
            self.assertEqual(payload.get("compile_pdf", {}).get("main_tex"), "GSC_Framework_v10_1_FINAL.tex")
            self.assertIn("summary", payload)


if __name__ == "__main__":
    unittest.main()
