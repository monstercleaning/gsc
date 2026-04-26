import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs_claim_ledger_lint.py"
LEDGER = ROOT / "docs" / "claim_ledger.json"


class TestPhase2M113ClaimLedgerLint(unittest.TestCase):
    def test_claim_ledger_lint_passes(self) -> None:
        self.assertTrue(LEDGER.is_file(), msg=str(LEDGER))
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(ROOT),
                "--ledger",
                "docs/claim_ledger.json",
                "--format",
                "json",
            ],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload.get("schema"), "phase2_claim_ledger_lint_v1")
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(int(payload.get("error_count", 0)), 0)


if __name__ == "__main__":
    unittest.main()
