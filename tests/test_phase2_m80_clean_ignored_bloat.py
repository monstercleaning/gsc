import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "clean_ignored_bloat.py"


def _write_bytes(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"a" * int(size))


class TestPhase2M80CleanIgnoredBloat(unittest.TestCase):
    def _run(self, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT)] + args
        return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)

    def test_report_emit_script_and_clean_modes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir(parents=True, exist_ok=True)

            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "ci@example.com"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "CI"], check=True)

            (repo / ".gitignore").write_text(".venv/\nresults/\n.claude/\n", encoding="utf-8")
            (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "init", "-q"], check=True)

            _write_bytes(repo / ".venv/lib/site-packages/foo.bin", 2 * 1024 * 1024)
            _write_bytes(repo / "results/out.bin", 1024 * 1024)
            _write_bytes(repo / ".claude/state.bin", 512 * 1024)

            report = self._run(
                [
                    "--root",
                    str(repo),
                    "--mode",
                    "report",
                    "--min-mb",
                    "0.25",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
            )
            self.assertEqual(report.returncode, 0, msg=(report.stdout or "") + (report.stderr or ""))
            payload = json.loads(report.stdout)
            self.assertGreaterEqual(int(payload.get("n_candidates_over_threshold", 0)), 1)
            top_paths = [str(row.get("path")) for row in payload.get("top_items", []) if isinstance(row, dict)]
            self.assertTrue(any(path.startswith(".venv") for path in top_paths), msg=str(top_paths))
            self.assertGreater(float(payload.get("total_reclaimable_mb", 0.0)), 0.0)

            script_path = repo / "cleanup.sh"
            emit = self._run(
                [
                    "--root",
                    str(repo),
                    "--mode",
                    "emit_script",
                    "--min-mb",
                    "0",
                    "--script-out",
                    str(script_path),
                ],
                cwd=ROOT,
            )
            self.assertEqual(emit.returncode, 0, msg=(emit.stdout or "") + (emit.stderr or ""))
            self.assertTrue(script_path.is_file())
            text = script_path.read_text(encoding="utf-8")
            self.assertIn("rm -rf -- \".venv\"", text)
            self.assertIn("rm -rf -- \"results\"", text)

            refuse = self._run(
                [
                    "--root",
                    str(repo),
                    "--mode",
                    "clean",
                    "--min-mb",
                    "0",
                ],
                cwd=ROOT,
            )
            self.assertEqual(refuse.returncode, 2, msg=(refuse.stdout or "") + (refuse.stderr or ""))

            clean = self._run(
                [
                    "--root",
                    str(repo),
                    "--mode",
                    "clean",
                    "--min-mb",
                    "0",
                    "--yes",
                ],
                cwd=ROOT,
            )
            self.assertEqual(clean.returncode, 0, msg=(clean.stdout or "") + (clean.stderr or ""))

            self.assertFalse((repo / ".venv").exists())
            self.assertFalse((repo / "results").exists())
            self.assertFalse((repo / ".claude").exists())
            self.assertTrue((repo / "tracked.txt").is_file())


if __name__ == "__main__":
    unittest.main()
