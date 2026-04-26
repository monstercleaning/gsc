from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_cosmofalsify_demo.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class TestPhase4M142CosmofalsifyDemoDeterminismToy(unittest.TestCase):
    def test_demo_report_and_zip_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--outdir",
                        str(outdir),
                        "--zip-out",
                        str(outdir / "demo_pack.zip"),
                        "--created-utc",
                        "946684800",
                        "--keep-work",
                        "0",
                        "--format",
                        "json",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            report_a = out_a / "cosmofalsify_demo_report.json"
            report_b = out_b / "cosmofalsify_demo_report.json"
            self.assertTrue(report_a.is_file())
            self.assertTrue(report_b.is_file())
            self.assertEqual(report_a.read_bytes(), report_b.read_bytes())

            payload = json.loads(report_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_cosmofalsify_demo_report_v1")
            self.assertEqual(payload.get("status"), "ok")
            self.assertTrue(bool(payload.get("paths_redacted")))

            zip_a = out_a / "demo_pack.zip"
            zip_b = out_b / "demo_pack.zip"
            self.assertTrue(zip_a.is_file())
            self.assertTrue(zip_b.is_file())
            self.assertEqual(_sha256(zip_a), _sha256(zip_b))

            report_text = report_a.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), report_text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, report_text)


if __name__ == "__main__":
    unittest.main()
