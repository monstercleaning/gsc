from pathlib import Path
import unittest


class TestPhase2M74GitignoreHygieneEntries(unittest.TestCase):
    def test_gitignore_contains_hygiene_patterns(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        gitignore_path = repo_root / ".gitignore"
        self.assertTrue(gitignore_path.is_file(), msg=str(gitignore_path))

        lines = {line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()}
        self.assertIn("__MACOSX/", lines)
        self.assertIn("._*", lines)
        self.assertIn(".claude/", lines)
        self.assertIn(".cursor/", lines)
        self.assertIn(".aider*", lines)
        self.assertIn(".vscode/", lines)
        self.assertIn(".idea/", lines)
        self.assertIn(".pytest_cache/", lines)
        self.assertIn(".mypy_cache/", lines)
        self.assertIn(".coverage", lines)
        self.assertIn("htmlcov/", lines)
        self.assertIn(".tox/", lines)
        self.assertIn(".ruff_cache/", lines)
        self.assertIn(".ipynb_checkpoints/", lines)
        self.assertIn(".venv/", lines)
        self.assertIn("**/.venv/", lines)
        self.assertIn("error", lines)
        self.assertIn("skipped_drift", lines)
        self.assertIn("repo_snapshot/", lines)
        self.assertIn("repo_snapshot_*.zip", lines)
        self.assertIn("repo_snapshot_*.tar.gz", lines)
        self.assertIn("gsc_snapshot_*.zip", lines)
        self.assertIn("gsc_snapshot_*.tar.gz", lines)
        self.assertIn("reviewer_pack*.zip", lines)
        self.assertIn("reviewer_pack_out*/", lines)
        self.assertIn("reviewer_pack_staging*/", lines)
        self.assertIn("worktree_bloat_report*.json", lines)
        self.assertIn("zip_bloat_report*.json", lines)
        self.assertIn("v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/", lines)
        self.assertIn("v11.0.0/archive/packs/", lines)


if __name__ == "__main__":
    unittest.main()
