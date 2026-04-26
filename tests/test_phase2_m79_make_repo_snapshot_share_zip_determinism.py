import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPT = ROOT / "scripts" / "make_repo_snapshot.py"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase2M79MakeRepoSnapshotShareZipDeterminism(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT)] + args
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_share_zip_is_deterministic_and_hygienic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            snap1 = tmp / "snap1.zip"
            snap2 = tmp / "snap2.zip"

            args1 = [
                "--repo-root",
                str(REPO_ROOT),
                "--profile",
                "share",
                "--format",
                "zip",
                "--out",
                str(snap1),
            ]
            args2 = [
                "--repo-root",
                str(REPO_ROOT),
                "--profile",
                "share",
                "--format",
                "zip",
                "--out",
                str(snap2),
            ]

            p1 = self._run(args1)
            p2 = self._run(args2)

            msg1 = (p1.stdout or "") + (p1.stderr or "")
            msg2 = (p2.stdout or "") + (p2.stderr or "")
            self.assertEqual(p1.returncode, 0, msg=msg1)
            self.assertEqual(p2.returncode, 0, msg=msg2)
            self.assertTrue(snap1.is_file())
            self.assertTrue(snap2.is_file())

            self.assertEqual(_sha256_path(snap1), _sha256_path(snap2))
            budget_bytes = 50 * 1024 * 1024
            size1 = int(snap1.stat().st_size)
            size2 = int(snap2.stat().st_size)
            self.assertEqual(size1, size2)
            self.assertLessEqual(size1, budget_bytes)
            self.assertLessEqual(size2, budget_bytes)

            with zipfile.ZipFile(snap1, "r") as zf:
                names = sorted(zf.namelist())
                self.assertTrue(names)

                forbidden_fragments = (
                    ".git/",
                    "/.venv/",
                    "v11.0.0/results",
                    "v11.0.0/paper_assets",
                    "__MACOSX/",
                    ".DS_Store",
                )
                for name in names:
                    for fragment in forbidden_fragments:
                        self.assertNotIn(fragment, name, msg=name)

                expected = (
                    "GSC/GSC_ONBOARDING_NEXT_SESSION.md",
                    "GSC/v11.0.0/scripts/make_repo_snapshot.py",
                    "GSC/v11.0.0/gsc/__init__.py",
                )
                for rel in expected:
                    self.assertIn(rel, names)

    def test_symlink_entries_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "ci@example.com"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "CI"], check=True)

            (repo / "README.md").write_text("x\n", encoding="utf-8")
            (repo / "target.txt").write_text("target\n", encoding="utf-8")
            (repo / "link.txt").symlink_to("target.txt")
            subprocess.run(["git", "-C", str(repo), "add", "README.md", "target.txt", "link.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "add symlink", "-q"], check=True)

            out_zip = Path(td) / "snap.zip"
            proc = self._run(
                [
                    "--repo-root",
                    str(repo),
                    "--profile",
                    "full",
                    "--format",
                    "zip",
                    "--out",
                    str(out_zip),
                ]
            )
            self.assertEqual(proc.returncode, 1, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertIn("symlink", (proc.stderr or "").lower())


if __name__ == "__main__":
    unittest.main()
