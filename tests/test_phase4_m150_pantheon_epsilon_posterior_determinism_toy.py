from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_pantheon_plus_epsilon_posterior.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M150PantheonEpsilonPosteriorDeterminismToy(unittest.TestCase):
    def test_report_is_deterministic_and_portable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            common = [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(ROOT),
                "--deterministic",
                "1",
                "--created-utc",
                "946684800",
                "--format",
                "json",
                "--run-mode",
                "demo",
                "--toy",
                "1",
                "--omega-m-min",
                "0.20",
                "--omega-m-max",
                "0.40",
                "--omega-m-n",
                "11",
                "--epsilon-min",
                "-0.06",
                "--epsilon-max",
                "0.06",
                "--epsilon-n",
                "13",
                "--integration-n",
                "600",
            ]

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [*common, "--outdir", str(outdir)],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "PANTHEON_EPSILON_POSTERIOR_REPORT.json"
            json_b = out_b / "PANTHEON_EPSILON_POSTERIOR_REPORT.json"
            md_a = out_a / "PANTHEON_EPSILON_POSTERIOR_REPORT.md"
            md_b = out_b / "PANTHEON_EPSILON_POSTERIOR_REPORT.md"
            png1_a = out_a / "epsilon_posterior_1d.png"
            png1_b = out_b / "epsilon_posterior_1d.png"
            png2_a = out_a / "omega_m_vs_epsilon.png"
            png2_b = out_b / "omega_m_vs_epsilon.png"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(md_a.read_bytes(), md_b.read_bytes())
            self.assertEqual(png1_a.read_bytes(), png1_b.read_bytes())
            self.assertEqual(png2_a.read_bytes(), png2_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_pantheon_plus_epsilon_posterior_report_v2")
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("run_mode"), "demo")
            self.assertEqual(payload.get("covariance_mode"), "diag_only_proof_of_concept")
            self.assertTrue(bool(payload.get("paths_redacted")))
            portability = payload.get("portability", {})
            self.assertEqual(int(portability.get("forbidden_absolute_path_match_count", -1)), 0)
            artifacts = payload.get("artifacts")
            self.assertIsInstance(artifacts, list)
            artifact_sha_by_name = {}
            artifact_names = {
                str(row.get("filename"))
                for row in artifacts
                if isinstance(row, dict)
            }
            for row in artifacts:
                if isinstance(row, dict):
                    artifact_sha_by_name[str(row.get("filename"))] = str(row.get("sha256", ""))
            self.assertIn("epsilon_posterior_1d.png", artifact_names)
            self.assertIn("omega_m_vs_epsilon.png", artifact_names)
            self.assertEqual(artifact_sha_by_name.get("epsilon_posterior_1d.png"), hashlib.sha256(png1_a.read_bytes()).hexdigest())
            self.assertEqual(artifact_sha_by_name.get("omega_m_vs_epsilon.png"), hashlib.sha256(png2_a.read_bytes()).hexdigest())

            digest = hashlib.sha256(json_a.read_bytes()).hexdigest()
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

            for path in (json_a, md_a):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(str(td_path.resolve()), text)
                for token in ABS_TOKENS:
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
