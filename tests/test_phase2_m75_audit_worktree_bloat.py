import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_worktree_bloat.py"


def _write_bytes(path: Path, n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * int(n))


class TestPhase2M75AuditWorktreeBloat(unittest.TestCase):
    def test_json_output_sorted_and_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_bytes(root / "a" / "f1.bin", 1000)
            _write_bytes(root / "a" / "f2.bin", 2000)
            _write_bytes(root / "b" / "c" / "f3.bin", 3000)
            _write_bytes(root / "skip_me" / "f4.bin", 4000)

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(root),
                "--format",
                "json",
                "--git-mode",
                "off",
                "--exclude",
                "skip_me",
                "--top-n",
                "10",
                "--max-depth",
                "3",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("schema"), "gsc_worktree_bloat_report_v1")
            self.assertEqual(int(payload.get("total_bytes", 0)), 6000)
            self.assertEqual(int(payload.get("n_files", 0)), 3)
            categories = payload.get("category_bytes")
            self.assertIsInstance(categories, dict)
            for key in (
                "git_dir_bytes",
                "venv_bytes",
                "results_bytes",
                "paper_assets_bytes",
                "data_cov_npz_bytes",
                "other_ignored_bytes",
            ):
                self.assertIn(key, categories)
                self.assertEqual(int(categories.get(key, 0)), 0)

            top_files = payload.get("top_files", [])
            self.assertTrue(isinstance(top_files, list) and len(top_files) >= 3)
            self.assertEqual(top_files[0].get("path"), "b/c/f3.bin")
            self.assertEqual(int(top_files[0].get("bytes", 0)), 3000)
            self.assertEqual(top_files[1].get("path"), "a/f2.bin")
            self.assertEqual(int(top_files[1].get("bytes", 0)), 2000)
            self.assertEqual(top_files[2].get("path"), "a/f1.bin")
            self.assertEqual(int(top_files[2].get("bytes", 0)), 1000)

            top_dirs = payload.get("top_dirs", [])
            self.assertTrue(any(row.get("path") == "a" and int(row.get("bytes", 0)) == 3000 for row in top_dirs))
            self.assertTrue(any(row.get("path") == "b/c" and int(row.get("bytes", 0)) == 3000 for row in top_dirs))

            all_paths = [row.get("path") for row in top_files]
            self.assertNotIn("skip_me/f4.bin", all_paths)

    def test_dotfile_paths_preserve_leading_dot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_bytes(root / ".gitignore", 16)
            _write_bytes(root / "plain.txt", 8)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--format",
                    "json",
                    "--git-mode",
                    "off",
                    "--top-n",
                    "10",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)

            payload = json.loads(proc.stdout)
            top_paths = [str(row.get("path")) for row in payload.get("top_files", []) if isinstance(row, dict)]
            self.assertIn(".gitignore", top_paths)
            self.assertNotIn("gitignore", top_paths)


if __name__ == "__main__":
    unittest.main()
