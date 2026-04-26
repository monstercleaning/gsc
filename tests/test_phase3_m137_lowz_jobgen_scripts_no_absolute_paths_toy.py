from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JOBGEN_SCRIPT = ROOT / "scripts" / "phase3_lowz_jobgen.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase3M137LowzJobgenScriptsNoAbsolutePathsToy(unittest.TestCase):
    def test_scripts_and_readme_have_no_host_absolute_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = td_path / "pack"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(JOBGEN_SCRIPT),
                    "--outdir",
                    str(outdir),
                    "--slices",
                    "2",
                    "--scheduler",
                    "bash",
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m-min",
                    "0.31",
                    "--Omega-m-max",
                    "0.31",
                    "--Omega-m-steps",
                    "1",
                    "--w0-min",
                    "-1.0",
                    "--w0-max",
                    "-1.0",
                    "--w0-steps",
                    "1",
                    "--lambda-min",
                    "0.0",
                    "--lambda-max",
                    "0.0",
                    "--lambda-steps",
                    "1",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            target_files = sorted(list(outdir.glob("*.sh")) + [outdir / "README.md"])
            self.assertGreaterEqual(len(target_files), 6)
            for path in target_files:
                text = path.read_text(encoding="utf-8")
                for token in ABS_TOKENS:
                    self.assertNotIn(token, text, msg=f"found absolute token {token!r} in {path.name}")


if __name__ == "__main__":
    unittest.main()
