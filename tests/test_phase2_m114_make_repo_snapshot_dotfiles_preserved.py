import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_repo_snapshot.py"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


class TestPhase2M114MakeRepoSnapshotDotfilesPreserved(unittest.TestCase):
    def test_dry_run_keeps_dotfile_names(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "toy_repo"
            repo.mkdir(parents=True, exist_ok=True)
            _git(repo, "init", "-q")
            _git(repo, "config", "user.email", "ci@example.com")
            _git(repo, "config", "user.name", "CI")

            (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
            (repo / ".hidden.txt").write_text("hidden\n", encoding="utf-8")
            _git(repo, "add", ".gitignore", ".hidden.txt")
            _git(repo, "commit", "-m", "add dotfiles", "-q")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(repo),
                    "--ref",
                    "HEAD",
                    "--profile",
                    "full",
                    "--dry-run",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            msg = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=msg)

            payload = json.loads(proc.stdout)
            paths = [str(row.get("path")) for row in payload.get("files", []) if isinstance(row, dict)]
            self.assertIn(".gitignore", paths)
            self.assertIn(".hidden.txt", paths)
            self.assertNotIn("gitignore", paths)
            self.assertNotIn("hidden.txt", paths)


if __name__ == "__main__":
    unittest.main()
