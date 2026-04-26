import fnmatch
import subprocess
from pathlib import Path
import unittest


FORBIDDEN_GLOBS = (
    "referee_pack_*.zip",
    "submission_bundle_*.zip",
    "toe_bundle_*.zip",
    "paper_assets_*.zip",
    "paper_assets_v10.1.1-*.zip",
    "v11.0.0/archive/packs/*",
)


class TestPhase2M88RepoHygieneNoTrackedDerivedBundles(unittest.TestCase):
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

    def test_forbidden_derived_bundle_patterns_not_tracked(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        tracked = self._tracked_files_or_skip(repo_root)
        offenders = []
        for rel in tracked:
            for pattern in FORBIDDEN_GLOBS:
                if fnmatch.fnmatch(rel, pattern):
                    offenders.append(rel)
                    break
        self.assertEqual([], offenders, msg=f"tracked derived bundles found: {offenders}")


if __name__ == "__main__":
    unittest.main()
