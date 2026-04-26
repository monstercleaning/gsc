import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"


class TestOperatorOneButtonAssets(unittest.TestCase):
    def test_materialize_paper_assets_from_release_zip(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import operator_one_button as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            zip_path = tdp / "paper_assets_v10.1.1-late-time-r4.zip"
            assets_dir = tdp / "paper_assets"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("paper_assets/figures/fig_a.png", b"\x89PNG\r\n")
                zf.writestr("paper_assets/tables/table_a.csv", b"k,v\n1,2\n")
                zf.writestr("paper_assets/manifest.json", b"{}\n")

            copied = m._materialize_paper_assets_from_release_zip(zip_path, assets_dir)
            self.assertGreaterEqual(copied, 3)
            self.assertTrue((assets_dir / "figures" / "fig_a.png").is_file())
            self.assertTrue((assets_dir / "tables" / "table_a.csv").is_file())
            self.assertTrue((assets_dir / "manifest.json").is_file())
            self.assertTrue(m._paper_assets_ready(assets_dir))

    def test_materialize_rejects_unsafe_entry(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        import operator_one_button as m  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            zip_path = tdp / "bad.zip"
            assets_dir = tdp / "paper_assets"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("../evil.txt", b"bad")
                zf.writestr("paper_assets/figures/fig_a.png", b"\x89PNG\r\n")

            with self.assertRaises(RuntimeError):
                m._materialize_paper_assets_from_release_zip(zip_path, assets_dir)


if __name__ == "__main__":
    unittest.main()
