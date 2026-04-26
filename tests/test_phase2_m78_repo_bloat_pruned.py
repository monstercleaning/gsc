from pathlib import Path
import os
import subprocess
import unittest


FORBIDDEN_TRACKED_PREFIXES = (
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/",
    "v11.0.0/archive/packs/",
)

MAX_TRACKED_V101_BYTES = 25 * 1024 * 1024


class TestPhase2M78RepoBloatPruned(unittest.TestCase):
    def _tracked_files_or_skip(self, repo_root: Path) -> list[str]:
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

    def test_redundant_legacy_trees_not_tracked(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        tracked = self._tracked_files_or_skip(repo_root)

        for rel in tracked:
            for prefix in FORBIDDEN_TRACKED_PREFIXES:
                self.assertFalse(rel.startswith(prefix), msg=f"tracked forbidden prefix: {rel}")

    def test_tracked_v101_size_budget(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        tracked = self._tracked_files_or_skip(repo_root)

        total_bytes = 0
        for rel in tracked:
            if not rel.startswith("v11.0.0/"):
                continue
            full = repo_root / rel
            if not full.is_file():
                continue
            total_bytes += int(os.path.getsize(full))

        self.assertLess(
            int(total_bytes),
            int(MAX_TRACKED_V101_BYTES),
            msg=f"tracked v11.0.0 bytes too large: {total_bytes} >= {MAX_TRACKED_V101_BYTES}",
        )


if __name__ == "__main__":
    unittest.main()
