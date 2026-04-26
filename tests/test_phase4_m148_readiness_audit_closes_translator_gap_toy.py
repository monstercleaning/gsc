from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "phase4_epsilon_framework_readiness_audit.py"


class TestPhase4M148ReadinessAuditClosesTranslatorGapToy(unittest.TestCase):
    def test_translator_related_gaps_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "audit"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT_SCRIPT),
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

            report = outdir / "EPSILON_FRAMEWORK_READINESS_AUDIT.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            gaps = payload.get("gap_list", [])
            ids = {str(row.get("id")) for row in gaps if isinstance(row, dict)}

            self.assertNotIn("TH-002", ids)
            self.assertNotIn("TH-003", ids)
            self.assertNotIn("IMPL-001", ids)
            self.assertNotIn("IMPL-005", ids)


if __name__ == "__main__":
    unittest.main()
