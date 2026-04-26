import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preflight_share_check.py"


class TestPhase2M108PreflightShareCheckZipToy(unittest.TestCase):
    def _run(self, zip_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--path",
                str(zip_path),
                "--max-mb",
                "50",
                "--format",
                "json",
            ],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )

    def test_forbidden_zip_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad_zip = Path(td) / "bad_share.zip"
            with zipfile.ZipFile(bad_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("proj/.git/config", "[core]\n")
                zf.writestr("proj/__MACOSX/._foo", "junk")
                zf.writestr("proj/ok/readme.txt", "hello")

            proc = self._run(bad_zip)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("status"), "fail")
            self.assertGreaterEqual(int(payload.get("forbidden_match_count", 0)), 1)
            self.assertEqual(payload.get("marker"), "SHARE_PREFLIGHT_FORBIDDEN_PATHS")

    def test_clean_zip_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            good_zip = Path(td) / "good_share.zip"
            with zipfile.ZipFile(good_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("proj/docs/notes.md", "clean")
                zf.writestr("proj/data/small.txt", "ok")

            proc = self._run(good_zip)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(int(payload.get("forbidden_match_count", 0)), 0)
            self.assertTrue(bool(payload.get("size_budget_ok")))


if __name__ == "__main__":
    unittest.main()
