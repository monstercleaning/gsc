import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bridges" / "phase4_qcd_gravity_bridge_v0.1" / "tools" / "make_qcd_gravity_bridge_artifacts.py"
GOLDEN = ROOT / "bridges" / "phase4_qcd_gravity_bridge_v0.1" / "golden"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")
EXPECTED = (
    "qcd_gravity_bridge_numbers.json",
    "qcd_gravity_bridge_kill_matrix.csv",
    "qcd_gravity_bridge_scale_plot.png",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase4M160QCDGravityBridgeArtifactsDeterministic(unittest.TestCase):
    def test_ci_smoke_matches_committed_golden_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--outdir",
                    str(outdir),
                    "--preset",
                    "ci_smoke",
                    "--seed",
                    "0",
                    "--emit-plot",
                    "1",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            for name in EXPECTED:
                generated = outdir / name
                golden = GOLDEN / name
                self.assertTrue(generated.is_file(), msg=f"missing generated artifact: {name}")
                self.assertTrue(golden.is_file(), msg=f"missing golden artifact: {name}")
                self.assertEqual(
                    _sha256_file(generated),
                    _sha256_file(golden),
                    msg=f"sha256 mismatch for {name}",
                )

            text = (outdir / "qcd_gravity_bridge_numbers.json").read_text(encoding="utf-8")
            csv_text = (outdir / "qcd_gravity_bridge_kill_matrix.csv").read_text(encoding="utf-8")
            self.assertIn('"paths_redacted": true', text)
            for tok in ABS_TOKENS:
                self.assertNotIn(tok, text)
                self.assertNotIn(tok, csv_text)


if __name__ == "__main__":
    unittest.main()
