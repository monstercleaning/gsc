from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests._v12_layout import nested_working_repo_skip_reason


ROOT = Path(__file__).resolve().parents[1]

# v12.6: cross-version working-repo invariant — runs fully in the nested
# repo; skips with documented reason in single-package layouts (see
# tests/_v12_layout.py and CHANGELOG).
_NESTED_SKIP = nested_working_repo_skip_reason(Path(__file__).resolve().parents[1])
RED_TEAM_SCRIPT = ROOT / "scripts" / "phase4_red_team_check.py"
VALIDATOR = ROOT / "scripts" / "phase2_schema_validate.py"


@unittest.skipIf(bool(_NESTED_SKIP), _NESTED_SKIP or "")
class TestPhase4M141SchemaValidateAutoToy(unittest.TestCase):
    def test_red_team_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "red_team"

            proc_report = subprocess.run(
                [
                    sys.executable,
                    str(RED_TEAM_SCRIPT),
                    "--repo-root",
                    str(ROOT),
                    "--outdir",
                    str(outdir),
                    "--strict",
                    "1",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_report.returncode, 0, msg=(proc_report.stdout or "") + (proc_report.stderr or ""))

            report_json = outdir / "RED_TEAM_REPORT.json"
            self.assertTrue(report_json.is_file())

            proc_validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--auto",
                    "--schema-dir",
                    str(ROOT / "schemas"),
                    "--json",
                    str(report_json),
                    "--format",
                    "text",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_validate.returncode, 0, msg=(proc_validate.stdout or "") + (proc_validate.stderr or ""))


if __name__ == "__main__":
    unittest.main()
