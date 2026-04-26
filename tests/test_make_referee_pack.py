import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/


class TestMakeRefereePack(unittest.TestCase):
    def test_builder_creates_expected_zip_structure(self):
        builder = ROOT / "scripts" / "make_referee_pack.py"
        verifier = ROOT / "scripts" / "verify_referee_pack.py"
        self.assertTrue(builder.exists())
        self.assertTrue(verifier.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            # Toy v11.0.0 tree so the builder can copy the required docs/scripts.
            toy_v101 = td / "v11.0.0"
            (toy_v101 / "docs").mkdir(parents=True, exist_ok=True)
            (toy_v101 / "data" / "cmb").mkdir(parents=True, exist_ok=True)
            (toy_v101 / "scripts").mkdir(parents=True, exist_ok=True)
            (toy_v101 / "referee_pack_figures").mkdir(parents=True, exist_ok=True)

            required_docs = [
                "diagnostics_index.md",
                "early_time_e2_synthesis.md",
                "early_time_e2_executive_summary.md",
                "early_time_e2_drift_constrained_bound.md",
                "early_time_e2_drift_bound_analytic.md",
                "early_time_e2_closure_to_physical_knobs.md",
                "reviewer_faq.md",
                "risk_register.md",
                "precision_constraints_translator.md",
                "early_time_bridge.md",
                "early_time_e2_closure_requirements.md",
                "sn_two_pass_sensitivity.md",
                "paper_sanity_checklist.md",
                "early_time_drift_cmb_correlation.md",
                "gw_standard_sirens.md",
                "early_time_e2_plan.md",
                "redshift_drift_beyond_flrw.md",
                "reproducibility.md",
                "measurement_model.md",
            ]
            for name in required_docs:
                (toy_v101 / "docs" / name).write_text(f"# {name}\n", encoding="utf-8")
            (toy_v101 / "data" / "cmb" / "README.md").write_text("cmb\n", encoding="utf-8")
            (toy_v101 / "referee_pack_figures" / "closure_requirements.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (toy_v101 / "referee_pack_figures" / "e2_drift_constrained_bound.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (toy_v101 / "referee_pack_figures" / "e2_closure_to_physical_knobs.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            # Minimal placeholder scripts (not executed by the builder).
            required_scripts = [
                "verify_release_bundle.py",
                "make_submission_bundle.py",
                "cmb_distance_budget_diagnostic.py",
                "verify_submission_bundle.py",
                "e2_drift_bound_analytic.py",
            ]
            for name in required_scripts:
                (toy_v101 / "scripts" / name).write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            # Minimal nested submission bundle zip that passes verify_submission_bundle.py.
            submission_zip = td / "submission_bundle_v10.1.1-late-time-r3.zip"
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
            with zipfile.ZipFile(submission_zip, "w") as zf:
                zf.writestr("GSC_Framework_v10_1_FINAL.tex", tex.lstrip())
                zf.writestr("SUBMISSION_README.md", "readme\n")
                zf.writestr("paper_assets/tables/bestfit_summary.tex", "table\n")
                zf.writestr("paper_assets/figures/figure_A.png", b"\x89PNG\r\n\x1a\n")

            # Fake canonical assets zip (provenance only for this test).
            assets_zip = td / "paper_assets_v10.1.1-late-time-r3.zip"
            assets_zip.write_bytes(b"fake assets\n")

            out_zip = td / "referee_pack.zip"
            r = subprocess.run(
                [
                    sys.executable,
                    str(builder),
                    "--assets-zip",
                    str(assets_zip),
                    "--submission-zip",
                    str(submission_zip),
                    "--out-zip",
                    str(out_zip),
                    "--v101-dir",
                    str(toy_v101),
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertTrue(out_zip.is_file())

            with zipfile.ZipFile(out_zip, "r") as zf:
                names = zf.namelist()

            # Required content.
            self.assertIn("REFEREE_PACK_README.md", names)
            self.assertIn("manifest.json", names)
            self.assertIn("data/cmb/README.md", names)
            self.assertIn("referee_pack_figures/closure_requirements.png", names)
            self.assertIn("referee_pack_figures/e2_drift_constrained_bound.png", names)
            self.assertIn("referee_pack_figures/e2_closure_to_physical_knobs.png", names)
            for name in required_docs:
                self.assertIn(f"docs/{name}", names)
            self.assertIn(f"paper/{submission_zip.name}", names)

            # Safety: no absolute paths or path traversal.
            for n in names:
                self.assertFalse(n.startswith(("/", "\\")), msg=n)
                self.assertNotIn("..", Path(n).parts, msg=n)

            # Verifier should accept the produced pack.
            r2 = subprocess.run([sys.executable, str(verifier), str(out_zip)], capture_output=True, text=True)
            out2 = (r2.stdout or "") + (r2.stderr or "")
            self.assertEqual(r2.returncode, 0, msg=out2)
            self.assertIn("OK: referee pack verified", out2)


if __name__ == "__main__":
    unittest.main()
