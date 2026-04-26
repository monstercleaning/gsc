from pathlib import Path
import json
import subprocess
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M154PantheonEpsilonPosteriorGitlessSnapshotToy(unittest.TestCase):
    def test_gitless_snapshot_run_emits_portable_full_cov_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            extracted = td_path / "extracted"
            snapshot_repo_root = extracted / "GSC" / "v11.0.0"
            snapshot_repo_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ROOT, snapshot_repo_root)

            outdir = snapshot_repo_root / "out" / "pantheon_eps_gitless_fullcov"
            script = snapshot_repo_root / "scripts" / "phase4_pantheon_plus_epsilon_posterior.py"

            python3 = shutil.which("python3")
            self.assertIsNotNone(python3)
            proc_exec = subprocess.run(
                [
                    str(python3),
                    str(script),
                    "--repo-root",
                    str(snapshot_repo_root),
                    "--outdir",
                    str(outdir),
                    "--deterministic",
                    "1",
                    "--format",
                    "json",
                    "--run-mode",
                    "demo",
                    "--covariance-mode",
                    "full",
                    "--dataset",
                    "tests/fixtures/phase4_m154/pantheon_toy_mu_fullcov.csv",
                    "--covariance",
                    "tests/fixtures/phase4_m154/pantheon_toy_cov.txt",
                    "--data-manifest",
                    "tests/fixtures/phase4_m154/pantheon_toy_manifest.json",
                    "--omega-m-n",
                    "7",
                    "--epsilon-n",
                    "7",
                    "--integration-n",
                    "300",
                ],
                cwd=str(extracted / "GSC"),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_exec.returncode, 0, msg=(proc_exec.stdout or "") + (proc_exec.stderr or ""))

            report = outdir / "PANTHEON_EPSILON_POSTERIOR_REPORT.json"
            self.assertTrue(report.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))

            self.assertEqual(payload.get("schema"), "phase4_pantheon_plus_epsilon_posterior_report_v2")
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("run_mode"), "demo")
            self.assertEqual(payload.get("covariance_mode"), "full")
            self.assertTrue(bool(payload.get("paths_redacted")))

            text = report.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
