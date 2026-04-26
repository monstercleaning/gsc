import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from zipfile import ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/


class TestMakeToeBundle(unittest.TestCase):
    def test_build_and_verify_toe_bundle(self):
        make_script = ROOT / "scripts" / "make_toe_bundle.py"
        verify_script = ROOT / "scripts" / "verify_toe_bundle.py"
        self.assertTrue(make_script.exists())
        self.assertTrue(verify_script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            toy_v101 = td / "v11.0.0"
            (toy_v101 / "docs" / "popular" / "sub").mkdir(parents=True, exist_ok=True)

            # Included content.
            (toy_v101 / "docs" / "popular" / "TOE_INDEX.md").write_text("index\n", encoding="utf-8")
            (toy_v101 / "docs" / "popular" / "TOE.md").write_text("toe\n", encoding="utf-8")
            (toy_v101 / "docs" / "popular" / "sub" / "Weyl.md").write_text("weyl\n", encoding="utf-8")
            (toy_v101 / "docs" / "HISTORICAL_CONTEXT.md").write_text("history\n", encoding="utf-8")

            # Junk / forbidden content in tree (must not be copied into bundle).
            (toy_v101 / "docs" / "popular" / ".DS_Store").write_text("junk\n", encoding="utf-8")
            (toy_v101 / "paper_assets").mkdir(parents=True, exist_ok=True)
            (toy_v101 / "paper_assets" / "x.txt").write_text("x\n", encoding="utf-8")

            out_zip = td / "toe_bundle_test.zip"
            r = subprocess.run(
                [
                    sys.executable,
                    str(make_script),
                    "--v101-dir",
                    str(toy_v101),
                    "--out-zip",
                    str(out_zip),
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertTrue(out_zip.is_file(), msg=out)

            with zipfile.ZipFile(out_zip, "r") as zf:
                names = zf.namelist()
                self.assertIn("manifest.json", names)
                self.assertIn("TOE_BUNDLE_README.md", names)
                self.assertIn("docs/popular/TOE_INDEX.md", names)
                self.assertIn("docs/popular/TOE.md", names)
                self.assertIn("docs/popular/sub/Weyl.md", names)
                self.assertTrue(
                    ("docs/HISTORICAL_CONTEXT.md" in names) or ("docs/historical_context.md" in names),
                    msg=f"historical context file missing in {names}",
                )
                self.assertNotIn("docs/popular/.DS_Store", names)
                for n in names:
                    self.assertFalse(n.startswith(("/", "\\")), msg=n)
                    self.assertNotIn("..", Path(n).parts, msg=n)
                    self.assertNotIn("__MACOSX", n, msg=n)
                    self.assertFalse(n.endswith(".DS_Store"), msg=n)
                    self.assertNotIn("paper_assets/", n, msg=n)

                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                self.assertEqual(manifest.get("kind"), "toe_bundle")
                self.assertTrue(manifest.get("diagnostic_only"))

            r_verify = subprocess.run(
                [sys.executable, str(verify_script), str(out_zip)],
                capture_output=True,
                text=True,
            )
            verify_out = (r_verify.stdout or "") + (r_verify.stderr or "")
            self.assertEqual(r_verify.returncode, 0, msg=verify_out)

    def test_builder_fails_without_toe_index(self):
        make_script = ROOT / "scripts" / "make_toe_bundle.py"
        self.assertTrue(make_script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            toy_v101 = td / "v11.0.0"
            (toy_v101 / "docs" / "popular").mkdir(parents=True, exist_ok=True)
            (toy_v101 / "docs" / "popular" / "OnlyNote.md").write_text("x\n", encoding="utf-8")

            out_zip = td / "toe_bundle_missing_index.zip"
            r = subprocess.run(
                [
                    sys.executable,
                    str(make_script),
                    "--v101-dir",
                    str(toy_v101),
                    "--out-zip",
                    str(out_zip),
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("TOE_INDEX", out)

    def test_verifier_rejects_non_toe_docs(self):
        verify_script = ROOT / "scripts" / "verify_toe_bundle.py"
        self.assertTrue(verify_script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            bad_zip = td / "bad_toe_bundle.zip"
            with zipfile.ZipFile(bad_zip, "w", compression=ZIP_DEFLATED) as zf:
                zf.writestr("TOE_BUNDLE_README.md", "x\n")
                zf.writestr("manifest.json", "{}\n")
                zf.writestr("docs/popular/TOE_INDEX.md", "index\n")
                zf.writestr("docs/popular/TOE_and_big_picture.md", "toe\n")
                zf.writestr("docs/early_time_e2_synthesis.md", "should-not-be-here\n")

            r = subprocess.run(
                [sys.executable, str(verify_script), str(bad_zip)],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("unexpected entry", out)

    def test_verifier_accepts_legacy_bundle_without_toe_index(self):
        verify_script = ROOT / "scripts" / "verify_toe_bundle.py"
        self.assertTrue(verify_script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            legacy_zip = td / "legacy_toe_bundle.zip"
            with zipfile.ZipFile(legacy_zip, "w", compression=ZIP_DEFLATED) as zf:
                zf.writestr("TOE_BUNDLE_README.md", "legacy\n")
                zf.writestr("manifest.json", "{}\n")
                zf.writestr("docs/popular/TOE_and_big_picture.md", "legacy-toe\n")

            r = subprocess.run(
                [sys.executable, str(verify_script), str(legacy_zip)],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("legacy ToE bundle accepted", out)


if __name__ == "__main__":
    unittest.main()
