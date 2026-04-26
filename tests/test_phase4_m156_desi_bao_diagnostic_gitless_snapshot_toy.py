from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M156DesiBaoDiagnosticGitlessSnapshotToy(unittest.TestCase):
    def test_gitless_snapshot_run_emits_portable_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            extracted = td_path / "extracted"
            snapshot_repo_root = extracted / "GSC" / "v11.0.0"
            snapshot_repo_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ROOT, snapshot_repo_root)

            script = snapshot_repo_root / "scripts" / "phase4_desi_bao_epsilon_or_rd_diagnostic.py"
            outdir = snapshot_repo_root / "out" / "desi_bao_triangle1_gitless"

            py = shutil.which("python3")
            self.assertIsNotNone(py)
            proc = subprocess.run(
                [
                    str(py),
                    str(script),
                    "--repo-root",
                    str(snapshot_repo_root),
                    "--outdir",
                    str(outdir),
                    "--deterministic",
                    "1",
                    "--format",
                    "json",
                    "--toy",
                    "1",
                    "--omega-m-n",
                    "7",
                    "--epsilon-n",
                    "7",
                ],
                cwd=str(extracted / "GSC"),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            report = outdir / "DESI_BAO_TRIANGLE1_REPORT.json"
            self.assertTrue(report.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_desi_bao_triangle1_report_v1")
            self.assertEqual(payload.get("status"), "ok")
            self.assertTrue(bool(payload.get("paths_redacted")))

            text = report.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
