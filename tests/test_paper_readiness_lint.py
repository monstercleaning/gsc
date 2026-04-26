import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))


class TestPaperReadinessLint(unittest.TestCase):
    def test_current_tex_passes(self):
        import paper_readiness_lint as lint  # noqa: E402

        tex = ROOT / "GSC_Framework_v10_1_FINAL.tex"
        md = ROOT / "GSC_Framework_v10_1_FINAL.md"
        self.assertTrue(tex.exists())
        self.assertTrue(md.exists())
        results = lint.run_lint(tex, md_path=md)
        failed = [r for r in results if not r.ok]
        self.assertEqual(failed, [], msg=f"failed checks: {[r.key for r in failed]}")

    def test_cli_reports_missing_markers(self):
        script = SCRIPTS / "paper_readiness_lint.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            bad_tex = td / "bad.tex"
            bad_tex.write_text(
                """
                \\section{Dummy}
                We discuss a model with no scope box and no drift line.
                """,
                encoding="utf-8",
            )

            r = subprocess.run(
                [sys.executable, str(script), "--tex", str(bad_tex), "--skip-md-check"],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("scope_claims_kill_box", out)
            self.assertIn("drift_sign_condition", out)

    def test_banned_reference_pattern_fails(self):
        script = SCRIPTS / "paper_readiness_lint.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            bad_tex = td / "bad_refs.tex"
            bad_tex.write_text(
                r"""
                \textbf{Scope (v11.0.0)}
                \textbf{Primary falsifier / kill test}
                \dot z > 0 and H(z) < H_0(1+z)
                Parameterized departures from universality
                \epsilon_{\rm EM}=\epsilon_{\rm QCD}=0
                not tired light
                time dilation
                Tolman
                late-time only
                referee pack includes
                Early-time/CMB closure checkpoint
                Reference: docs/popular/TOE_and_big_picture.md
                """,
                encoding="utf-8",
            )

            r = subprocess.run(
                [sys.executable, str(script), "--tex", str(bad_tex), "--skip-md-check"],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("no_popular_or_diagnostic_asset_references_in_tex", out)


if __name__ == "__main__":
    unittest.main()
