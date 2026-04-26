from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M47BuildPaperHelp(unittest.TestCase):
    def test_help_includes_phase2_bundle_flag(self):
        script = ROOT / "scripts" / "build_paper.sh"
        proc = subprocess.run(
            ["bash", str(script), "--help"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)
        self.assertIn("--phase2-e2-bundle", output)
        self.assertIn("--phase2-e2-extract-root", output)


if __name__ == "__main__":
    unittest.main()
