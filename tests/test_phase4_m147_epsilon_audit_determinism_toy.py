from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_epsilon_framework_readiness_audit.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M147EpsilonAuditDeterminismToy(unittest.TestCase):
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
                        "--format",
                        "json",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "EPSILON_FRAMEWORK_READINESS_AUDIT.json"
            json_b = out_b / "EPSILON_FRAMEWORK_READINESS_AUDIT.json"
            md_a = out_a / "EPSILON_FRAMEWORK_READINESS_AUDIT.md"
            md_b = out_b / "EPSILON_FRAMEWORK_READINESS_AUDIT.md"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(md_a.read_bytes(), md_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_epsilon_framework_readiness_audit_report_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertIsInstance(payload.get("gap_list"), list)
            self.assertGreaterEqual(len(payload.get("gap_list", [])), 1)

            text = json_a.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
