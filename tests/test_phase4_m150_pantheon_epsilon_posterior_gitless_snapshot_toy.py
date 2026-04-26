from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SCRIPT = ROOT / "scripts" / "make_repo_snapshot.py"
POSTERIOR_SCRIPT = ROOT / "scripts" / "phase4_pantheon_plus_epsilon_posterior.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M150PantheonEpsilonPosteriorGitlessSnapshotToy(unittest.TestCase):
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
            outdir = snapshot_repo_root / "out" / "pantheon_eps_gitless"

            proc_report = subprocess.run(
                [
                    sys.executable,
                    str(POSTERIOR_SCRIPT),
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
                    "--integration-n",
                    "256",
                ],
                cwd=str(extracted / "GSC"),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_report.returncode, 0, msg=(proc_report.stdout or "") + (proc_report.stderr or ""))

            report = outdir / "PANTHEON_EPSILON_POSTERIOR_REPORT.json"
            self.assertTrue(report.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))

            self.assertEqual(payload.get("schema"), "phase4_pantheon_plus_epsilon_posterior_report_v2")
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("run_mode"), "demo")
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertEqual(payload.get("covariance_mode"), "diag_only_proof_of_concept")
            self.assertTrue((outdir / "epsilon_posterior_1d.png").is_file())
            self.assertTrue((outdir / "omega_m_vs_epsilon.png").is_file())

            text = report.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
