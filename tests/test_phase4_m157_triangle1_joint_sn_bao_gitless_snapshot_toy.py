from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class TestPhase4M157Triangle1JointSnBaoGitlessSnapshotToy(unittest.TestCase):
    def test_gitless_snapshot_run_emits_portable_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            extracted = td_path / "extracted"
            snap_root = extracted / "GSC" / "v11.0.0"
            snap_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ROOT, snap_root)

            script = snap_root / "scripts" / "phase4_triangle1_sn_bao_planck_thetastar.py"
            outdir = snap_root / "out" / "triangle1_gitless"

            py = shutil.which("python3")
            self.assertIsNotNone(py)
            proc = subprocess.run(
                [
                    str(py),
                    str(script),
                    "--repo-root",
                    str(snap_root),
                    "--outdir",
                    str(outdir),
                    "--deterministic",
                    "1",
                    "--toy",
                    "1",
                    "--omega-m-steps",
                    "7",
                    "--epsilon-steps",
                    "7",
                    "--integration-n",
                    "256",
                    "--format",
                    "json",
                ],
                cwd=str(extracted / "GSC"),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            report = outdir / "TRIANGLE1_SN_BAO_PLANCK_REPORT.json"
            self.assertTrue(report.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_triangle1_report_v1")
            self.assertEqual(payload.get("status"), "ok")
            self.assertTrue(bool(payload.get("paths_redacted")))

            text = report.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
