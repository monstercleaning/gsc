from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SCRIPT = ROOT / "scripts" / "make_repo_snapshot.py"
AUDIT_SCRIPT = ROOT / "scripts" / "phase4_epsilon_framework_readiness_audit.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M147EpsilonAuditGitlessSnapshotToy(unittest.TestCase):
    def test_gitless_snapshot_run_emits_portable_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            snapshot_zip = td_path / "review_with_data.zip"

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

            snapshot_repo_root = extracted / "GSC" / "v11.0.0"
            outdir = snapshot_repo_root / "out" / "epsilon_readiness_gitless"
            self.assertTrue(AUDIT_SCRIPT.is_file())

            proc_audit = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT_SCRIPT),
                    "--repo-root",
                    str(snapshot_repo_root),
                    "--outdir",
                    str(outdir),
                    "--deterministic",
                    "1",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_audit.returncode, 0, msg=(proc_audit.stdout or "") + (proc_audit.stderr or ""))

            report = outdir / "EPSILON_FRAMEWORK_READINESS_AUDIT.json"
            self.assertTrue(report.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))

            self.assertEqual(payload.get("schema"), "phase4_epsilon_framework_readiness_audit_report_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertIn("repo_snapshot_manifest_sha256", payload)
            self.assertIn("repo_snapshot_manifest_source", payload)

            text = report.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
