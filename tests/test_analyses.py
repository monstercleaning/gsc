"""Diagnostic analyses are deterministic and reproduce their committed outputs."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestAnalyses(unittest.TestCase):
    def test_p_role_consistency_reproduces_its_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            subprocess.run([sys.executable, str(ROOT / "analyses" / "p_role_consistency.py"), "--output", str(out)],
                           check=True, capture_output=True)
            self.assertEqual(out.read_bytes(), (ROOT / "analyses" / "p_role_consistency.json").read_bytes())

    def test_w0wa_diagnostic_fast_blocks_reproduce(self):
        committed = json.loads((ROOT / "analyses" / "w0wa_rd_shift_diagnostic.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            subprocess.run([sys.executable, str(ROOT / "analyses" / "w0wa_rd_shift_diagnostic.py"), "--fast",
                            "--output", str(out)], check=True, capture_output=True)
            fresh = json.loads(out.read_text())
        for key in ("controls", "fits_on_shifted_mock", "fits_on_shifted_mock_dr2_precision"):
            with self.subTest(block=key):
                self.assertEqual(fresh[key], committed[key])


if __name__ == "__main__":
    unittest.main()
