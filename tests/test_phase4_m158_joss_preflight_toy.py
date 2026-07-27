from pathlib import Path
import subprocess
import sys
import unittest

from tests._v12_layout import nested_working_repo_skip_reason


ROOT = Path(__file__).resolve().parents[1]

# v12.6: cross-version working-repo invariant — runs fully in the nested
# repo; skips with documented reason in single-package layouts (see
# tests/_v12_layout.py and CHANGELOG).
_NESTED_SKIP = nested_working_repo_skip_reason(Path(__file__).resolve().parents[1])
SCRIPT = ROOT / "scripts" / "phase4_joss_preflight.py"


@unittest.skipIf(bool(_NESTED_SKIP), _NESTED_SKIP or "")
class TestPhase4M158JossPreflightToy(unittest.TestCase):
    def test_joss_preflight_passes(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(ROOT.parent),
                "--format",
                "text",
            ],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
        self.assertIn("status=ok", proc.stdout or "")


if __name__ == "__main__":
    unittest.main()
