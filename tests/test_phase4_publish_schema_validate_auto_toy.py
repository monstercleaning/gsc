import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "phase4_build_paper2_assets.py"
JOSS_SCRIPT = ROOT / "scripts" / "phase4_joss_preflight.py"
SCHEMA_VALIDATE = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4PublishSchemaValidateAutoToy(unittest.TestCase):
    def test_assets_and_joss_reports_schema_validate_auto(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            outdir = base / "assets"
            workdir = base / "work"
            joss_json = base / "joss_report.json"

            p_build = subprocess.run(
                [
                    sys.executable,
                    str(BUILD_SCRIPT),
                    "--preset",
                    "ci_smoke",
                    "--seed",
                    "0",
                    "--workdir",
                    str(workdir),
                    "--outdir",
                    str(outdir),
                    "--format",
                    "text",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(p_build.returncode, 0, msg=(p_build.stdout or "") + (p_build.stderr or ""))

            p_joss = subprocess.run(
                [
                    sys.executable,
                    str(JOSS_SCRIPT),
                    "--repo-root",
                    ".",
                    "--out-json",
                    str(joss_json),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(p_joss.returncode, 0, msg=(p_joss.stdout or "") + (p_joss.stderr or ""))

            for report_path in (outdir / "paper2_assets_manifest.json", joss_json):
                p_val = subprocess.run(
                    [
                        sys.executable,
                        str(SCHEMA_VALIDATE),
                        "--auto",
                        "--schema-dir",
                        str(ROOT / "schemas"),
                        "--json",
                        str(report_path),
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(
                    p_val.returncode,
                    0,
                    msg=f"schema auto-validation failed for {report_path}:\n{(p_val.stdout or '')}{(p_val.stderr or '')}",
                )


if __name__ == "__main__":
    unittest.main()
