import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_portable_content_lint.py"


class TestPhase2M117PortableContentLintDetectsAbsolutePathsToy(unittest.TestCase):
    def _run(self, target: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--path",
                str(target),
                "--format",
                "json",
            ],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )

    def test_detects_absolute_path_tokens_in_json_and_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "a.json").write_text(
                json.dumps({"source": "/Users/demo/foo"}, sort_keys=True),
                encoding="utf-8",
            )
            (td_path / "b.jsonl").write_text(
                "{\"path\":\"/home/demo/bar\"}\n",
                encoding="utf-8",
            )

            proc = self._run(td_path)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("schema"), "phase2_portable_content_lint_v1")
            self.assertEqual(payload.get("status"), "fail")
            self.assertGreaterEqual(int(payload.get("offending_file_count", 0)), 2)
            offenders = payload.get("offending_files", [])
            self.assertIsInstance(offenders, list)
            offender_paths = {str(row.get("path")) for row in offenders if isinstance(row, dict)}
            self.assertIn("a.json", offender_paths)
            self.assertIn("b.jsonl", offender_paths)


if __name__ == "__main__":
    unittest.main()
