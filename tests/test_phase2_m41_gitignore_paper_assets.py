from pathlib import Path
import unittest


class TestPhase2M41GitignorePaperAssets(unittest.TestCase):
    def test_gitignore_contains_phase2_paper_asset_paths(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        gitignore_path = repo_root / ".gitignore"
        self.assertTrue(gitignore_path.is_file(), msg=str(gitignore_path))

        lines = {line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()}
        self.assertIn("v11.0.0/paper_assets_cmb_e2_closure_to_physical_knobs/", lines)
        self.assertIn("v11.0.0/paper_assets_cmb_e2_drift_constrained_closure_bound/", lines)


if __name__ == "__main__":
    unittest.main()
