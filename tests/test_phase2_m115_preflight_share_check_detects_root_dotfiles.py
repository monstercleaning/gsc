import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preflight_share_check.py"


class TestPhase2M115PreflightShareCheckDetectsRootDotfiles(unittest.TestCase):
    def test_root_dot_store_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / ".DS_Store").write_text("junk", encoding="utf-8")
            (td_path / "README.txt").write_text("ok", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--path",
                    str(td_path),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)

            payload = json.loads(proc.stdout)
            self.assertGreaterEqual(int(payload.get("forbidden_match_count", 0)), 1)
            hits = [str(x) for x in (payload.get("forbidden_matches") or [])]
            self.assertTrue(any(".DS_Store" in row for row in hits), msg=str(hits))


if __name__ == "__main__":
    unittest.main()
