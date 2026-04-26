import json
from pathlib import Path
import subprocess
import unittest


FORBIDDEN_SNIPPETS = (
    "/Users/",
    "GoogleDrive-morfikus",
    "Library/CloudStorage",
)

LEGACY_PREFIXES = ("v11.0.0/B/", "v11.0.0/archive/")
TEXT_SUFFIXES = (".md", ".txt", ".ini", ".json", ".yaml", ".yml", ".tex", ".sh", ".py")


class TestPhase2M76RepoHygieneNoAbsolutePathsInLegacyPacks(unittest.TestCase):
    def _tracked_files(self) -> list[str]:
        repo_root = Path(__file__).resolve().parents[2]
        top = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
            text=True,
        )
        if top.returncode != 0:
            stderr = (top.stderr or "").lower()
            if "not a git repository" in stderr:
                self.skipTest("git metadata unavailable in extracted snapshot; skipping tracked-file hygiene check")
            raise RuntimeError(f"git rev-parse failed: {stderr.strip()}")

        # In extracted snapshots under a parent git worktree, git may resolve to
        # the parent repository. Treat that as gitless for this local-tree check.
        if Path((top.stdout or "").strip()).resolve() != repo_root.resolve():
            self.skipTest("current tree is not its own git toplevel; skipping tracked-file hygiene check")

        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").lower()
            if "not a git repository" in stderr:
                self.skipTest("git metadata unavailable in extracted snapshot; skipping tracked-file hygiene check")
            raise RuntimeError(f"git ls-files failed: {stderr.strip()}")
        return [item.decode("utf-8") for item in proc.stdout.split(b"\0") if item]

    def test_no_machine_local_paths(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        checked = 0
        for rel in self._tracked_files():
            if not rel.startswith(LEGACY_PREFIXES):
                continue
            if not rel.endswith(TEXT_SUFFIXES):
                continue
            path = repo_root / rel
            if not path.is_file():
                continue
            checked += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in FORBIDDEN_SNIPPETS:
                self.assertNotIn(marker, text, msg=f"{path} contains forbidden marker: {marker}")

        self.assertGreater(checked, 0, msg="No legacy tracked text files found to validate")

    def test_metadata_paths_are_portable(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        for rel in self._tracked_files():
            if not rel.startswith(LEGACY_PREFIXES):
                continue
            if not rel.endswith("phase10_metadata.json"):
                continue
            path = repo_root / rel
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))

            mochi_dir = str(payload.get("mochi_dir", ""))
            self.assertFalse(mochi_dir.startswith("/"), msg=f"{path}: mochi_dir must be portable")
            self.assertNotIn("Users", mochi_dir, msg=f"{path}: mochi_dir must not contain local user path")

            outdir = str(payload.get("outdir", ""))
            self.assertIn(outdir, {"output_ext", "."}, msg=f"{path}: outdir must be relative portable path")

            files = payload.get("files")
            self.assertIsInstance(files, dict, msg=f"{path}: files must be a dict")

            smg = str(files.get("smg_table", ""))
            ini = str(files.get("ini", ""))
            self.assertTrue(smg and not smg.startswith("/") and "Users" not in smg, msg=f"{path}: bad smg_table")
            self.assertTrue(ini and not ini.startswith("/") and "Users" not in ini, msg=f"{path}: bad ini")


if __name__ == "__main__":
    unittest.main()
