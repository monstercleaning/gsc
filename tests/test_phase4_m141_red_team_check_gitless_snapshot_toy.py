from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SCRIPT = ROOT / "scripts" / "make_repo_snapshot.py"
RED_TEAM_SCRIPT_REL = Path("v11.0.0") / "scripts" / "phase4_red_team_check.py"


class TestPhase4M141RedTeamCheckGitlessSnapshotToy(unittest.TestCase):
    def test_strict_mode_passes_in_gitless_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            snapshot_zip = td_path / "share.zip"

            proc_snapshot = subprocess.run(
                [
                    sys.executable,
                    str(SNAPSHOT_SCRIPT),
                    "--profile",
                    "review_with_data",
                    "--zip-out",
                    str(snapshot_zip),
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_snapshot.returncode, 0, msg=(proc_snapshot.stdout or "") + (proc_snapshot.stderr or ""))

            extracted = td_path / "extracted"
            extracted.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(snapshot_zip, "r") as zf:
                zf.extractall(extracted)

            snapshot_root = extracted / "GSC" / "v11.0.0"
            report_out = snapshot_root / "out" / "red_team_gitless"
            red_team_script = extracted / "GSC" / RED_TEAM_SCRIPT_REL
            self.assertTrue(red_team_script.is_file())

            proc_report = subprocess.run(
                [
                    sys.executable,
                    str(red_team_script),
                    "--repo-root",
                    str(snapshot_root),
                    "--outdir",
                    str(report_out),
                    "--strict",
                    "1",
                    "--format",
                    "json",
                ],
                cwd=str(extracted / "GSC"),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_report.returncode, 0, msg=(proc_report.stdout or "") + (proc_report.stderr or ""))

            report_json = report_out / "RED_TEAM_REPORT.json"
            self.assertTrue(report_json.is_file())
            payload = json.loads(report_json.read_text(encoding="utf-8"))
            repo_footprint = payload.get("checks", {}).get("repo_footprint", {})
            self.assertEqual(repo_footprint.get("status"), "ok")
            self.assertTrue(bool(repo_footprint.get("git_metadata_unavailable")))


if __name__ == "__main__":
    unittest.main()
