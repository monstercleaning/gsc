from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_epsilon_translator_mvp.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M148EpsilonTranslatorDeterminismToy(unittest.TestCase):
    def test_report_is_deterministic_and_portable(self) -> None:
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
                        "--format",
                        "json",
                        "--epsilon-em",
                        "0.010",
                        "--epsilon-qcd",
                        "-0.020",
                        "--sigma-ratio-min",
                        "1.0",
                        "--sigma-ratio-max",
                        "6.0",
                        "--n",
                        "9",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "EPSILON_TRANSLATOR_MVP.json"
            json_b = out_b / "EPSILON_TRANSLATOR_MVP.json"
            md_a = out_a / "EPSILON_TRANSLATOR_MVP.md"
            md_b = out_b / "EPSILON_TRANSLATOR_MVP.md"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(md_a.read_bytes(), md_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_epsilon_translator_report_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertEqual(payload.get("status"), "ok")

            rows = payload.get("grid_rows", [])
            self.assertIsInstance(rows, list)
            self.assertEqual(len(rows), 9)

            digest = hashlib.sha256(json_a.read_bytes()).hexdigest()
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

            text = json_a.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
