from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_triangle1_sn_bao_planck_thetastar.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class TestPhase4M157Triangle1DeterminismToy(unittest.TestCase):
    def test_report_and_png_are_deterministic_and_portable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--repo-root",
                        str(ROOT),
                        "--outdir",
                        str(outdir),
                        "--deterministic",
                        "1",
                        "--created-utc",
                        "946684800",
                        "--run-mode",
                        "demo",
                        "--toy",
                        "1",
                        "--omega-m-steps",
                        "9",
                        "--epsilon-steps",
                        "9",
                        "--integration-n",
                        "512",
                        "--format",
                        "json",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "TRIANGLE1_SN_BAO_PLANCK_REPORT.json"
            json_b = out_b / "TRIANGLE1_SN_BAO_PLANCK_REPORT.json"
            md_a = out_a / "TRIANGLE1_SN_BAO_PLANCK_REPORT.md"
            md_b = out_b / "TRIANGLE1_SN_BAO_PLANCK_REPORT.md"
            png1_a = out_a / "epsilon_posterior_1d.png"
            png1_b = out_b / "epsilon_posterior_1d.png"
            png2_a = out_a / "omega_m_vs_epsilon.png"
            png2_b = out_b / "omega_m_vs_epsilon.png"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(md_a.read_bytes(), md_b.read_bytes())
            self.assertEqual(png1_a.read_bytes(), png1_b.read_bytes())
            self.assertEqual(png2_a.read_bytes(), png2_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_triangle1_report_v1")
            self.assertEqual(payload.get("status"), "ok")
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertTrue(bool(payload.get("toy_mode")))

            artifact_sha = {
                str(row.get("filename")): str(row.get("sha256"))
                for row in payload.get("artifacts", [])
                if isinstance(row, dict) and "sha256" in row
            }
            self.assertEqual(artifact_sha.get("epsilon_posterior_1d.png"), hashlib.sha256(png1_a.read_bytes()).hexdigest())
            self.assertEqual(artifact_sha.get("omega_m_vs_epsilon.png"), hashlib.sha256(png2_a.read_bytes()).hexdigest())
            self.assertEqual(
                artifact_sha.get("TRIANGLE1_SN_BAO_PLANCK_REPORT.md"),
                hashlib.sha256(md_a.read_bytes()).hexdigest(),
            )

            text = json_a.read_text(encoding="utf-8") + md_a.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
