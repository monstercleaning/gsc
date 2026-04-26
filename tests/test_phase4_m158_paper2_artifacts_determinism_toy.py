from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_make_paper2_artifacts.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class TestPhase4M158Paper2ArtifactsDeterminismToy(unittest.TestCase):
    def test_deterministic_outputs(self) -> None:
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
                        "--run-mode",
                        "demo",
                        "--outdir",
                        str(outdir),
                        "--created-utc",
                        "946684800",
                        "--format",
                        "json",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            files = (
                "artifacts_manifest.json",
                "sn_epsilon_posterior_summary.json",
                "bao_leg_summary.json",
                "sn_bao_joint_summary.json",
                "epsilon_posterior_1d.png",
                "omega_m_vs_epsilon.png",
                "bao_rd_degeneracy.png",
                "joint_corner_or_equivalent.png",
            )
            for name in files:
                self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes(), msg=name)

            payload = json.loads((out_a / "artifacts_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_paper2_artifacts_manifest_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))

            sha_by_name = {
                str(row.get("filename")): str(row.get("sha256"))
                for row in payload.get("artifacts", [])
                if isinstance(row, dict)
            }
            self.assertEqual(
                sha_by_name.get("epsilon_posterior_1d.png"),
                hashlib.sha256((out_a / "epsilon_posterior_1d.png").read_bytes()).hexdigest(),
            )
            self.assertEqual(
                sha_by_name.get("sn_bao_joint_summary.json"),
                hashlib.sha256((out_a / "sn_bao_joint_summary.json").read_bytes()).hexdigest(),
            )

            text = (out_a / "artifacts_manifest.json").read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
