from pathlib import Path
import subprocess
import unittest


REMOVED_ZIP_PATHS = (
    "GSC_v8.2_COMPLETE.zip",
    "GSC_v10_sims.zip",
    "v11.0.0/GSC_v10_1_release.zip",
    "v11.0.0/GSC_v10_1_simulations.zip",
    "v11.0.0/archive/legacy/branch_A_v10.1/GSC_v10_1_release.zip",
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE.zip",
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/phase10_upload.zip",
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/phase10_upload_20260131_232127.zip",
)


class TestPhase2M76RepoHygieneNoRedundantTrackedZips(unittest.TestCase):
    def _tracked_files_or_skip(self, repo_root: Path) -> set[str]:
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
        return {item.decode("utf-8") for item in proc.stdout.split(b"\0") if item}

    def test_redundant_zips_are_not_tracked(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        tracked = self._tracked_files_or_skip(repo_root)
        for rel in REMOVED_ZIP_PATHS:
            self.assertNotIn(rel, tracked, msg=f"still tracked: {rel}")


if __name__ == "__main__":
    unittest.main()
