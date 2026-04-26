import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPT = ROOT / "scripts" / "make_repo_snapshot.py"


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)] + args, cwd=str(cwd), text=True, capture_output=True)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo)] + list(args), text=True, capture_output=True, check=True)
    return proc.stdout.strip()


class TestPhase2M77MakeRepoSnapshotShareProfile(unittest.TestCase):
    def test_share_profile_excludes_bloat_paths_and_keeps_core_files(self) -> None:
        args = [
            "--repo-root",
            str(REPO_ROOT),
            "--profile",
            "share",
            "--dry-run",
            "--format",
            "json",
        ]
        p = _run(args, cwd=ROOT)
        self.assertEqual(p.returncode, 0, msg=(p.stdout or "") + (p.stderr or ""))

        payload = json.loads(p.stdout)
        self.assertEqual(payload.get("schema"), "gsc_repo_snapshot_manifest_v1")
        self.assertEqual(payload.get("profile"), "share")
        self.assertEqual(payload.get("repo_root"), ".")
        self.assertNotIn("repo_root_abs", payload)
        self.assertTrue(payload.get("git_head"))
        self.assertIsInstance(payload.get("n_files"), int)
        self.assertIsInstance(payload.get("estimated_total_bytes"), int)
        self.assertIsInstance(payload.get("denylist_hits"), list)

        paths = [str(row.get("path")) for row in payload.get("files", []) if isinstance(row, dict)]
        self.assertTrue(paths)

        expected = {
            "GSC_ONBOARDING_NEXT_SESSION.md",
            "v11.0.0/docs/early_time_e2_status.md",
            "v11.0.0/gsc/__init__.py",
            "v11.0.0/scripts/phase2_e2_scan.py",
        }
        for item in expected:
            self.assertIn(item, paths)

        forbidden_prefixes = (
            ".git/",
            "v11.0.0/results/",
            "v11.0.0/paper_assets",
            "v11.0.0/archive/",
            "v11.0.0/archive/packs/",
            "v11.0.0/B/",
            "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/",
            "v11.0.0/data/sn/",
            "v11.0.0/artifacts/",
            "__MACOSX/",
        )
        for path in paths:
            for prefix in forbidden_prefixes:
                self.assertFalse(path.startswith(prefix), msg=path)
            self.assertNotIn("/._", f"/{path}", msg=path)
            self.assertNotIn("/.venv/", f"/{path}/", msg=path)
            self.assertNotIn(".DS_Store", path, msg=path)
            self.assertFalse(path.endswith(".cov"), msg=path)
            self.assertFalse(path.endswith(".npz"), msg=path)
            self.assertFalse(path.endswith(".dat"), msg=path)

    def test_require_clean_rejects_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "toy_repo"
            repo.mkdir(parents=True, exist_ok=True)
            _git(repo, "init", "-q")
            _git(repo, "config", "user.email", "ci@example.com")
            _git(repo, "config", "user.name", "CI")

            tracked = repo / "README.md"
            tracked.write_text("base\n", encoding="utf-8")
            _git(repo, "add", "README.md")
            _git(repo, "commit", "-m", "init", "-q")

            # Dirty tracked modification.
            tracked.write_text("dirty\n", encoding="utf-8")

            proc = _run(
                [
                    "--repo-root",
                    str(repo),
                    "--profile",
                    "share",
                    "--dry-run",
                    "--format",
                    "json",
                    "--require-clean",
                    "1",
                ],
                cwd=ROOT,
            )
            self.assertEqual(proc.returncode, 2, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertIn("require-clean", (proc.stderr or "").lower())


if __name__ == "__main__":
    unittest.main()
