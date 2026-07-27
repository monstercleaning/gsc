import json
import subprocess
import sys
from pathlib import Path
import unittest

from tests._v12_layout import nested_working_repo_skip_reason


ROOT = Path(__file__).resolve().parents[1]

# v12.6: cross-version working-repo invariant — runs fully in the nested
# repo; skips with documented reason in single-package layouts (see
# tests/_v12_layout.py and CHANGELOG).
_NESTED_SKIP = nested_working_repo_skip_reason(Path(__file__).resolve().parents[1])
SCRIPT = ROOT / "scripts" / "phase4_joss_preflight.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


@unittest.skipIf(bool(_NESTED_SKIP), _NESTED_SKIP or "")
class TestPhase4PublishJossPreflightDeterminismToy(unittest.TestCase):
    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                ".",
                "--format",
                "json",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )

    def test_joss_preflight_json_is_deterministic(self) -> None:
        p1 = self._run()
        p2 = self._run()
        self.assertEqual(p1.returncode, 0, msg=(p1.stdout or "") + (p1.stderr or ""))
        self.assertEqual(p2.returncode, 0, msg=(p2.stdout or "") + (p2.stderr or ""))
        self.assertEqual(p1.stdout, p2.stdout)

        payload = json.loads(p1.stdout)
        self.assertEqual(payload.get("schema"), "phase4_joss_preflight_report_v1")
        self.assertEqual(payload.get("status"), "ok")

        for tok in ABS_TOKENS:
            self.assertNotIn(tok, p1.stdout)


if __name__ == "__main__":
    unittest.main()
