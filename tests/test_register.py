"""The register is frozen: every pipeline reproduces its registered output, and
scoring is deterministic and returns the registered verdicts."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "predictions"
EXPECTED_VERDICTS = {
    "P1": "PASS", "P3": "FAIL", "P4": "PASS", "P5": "PASS", "P6": "FAIL",
    "P7": "SUB-THRESHOLD", "P9": "PASS", "P11": "PASS", "P13": "PASS",
}


def entries():
    for d in sorted(p for p in REGISTER.iterdir() if p.is_dir()):
        yield f"P{int(d.name[1:3])}", d


class TestRegister(unittest.TestCase):
    def test_every_pipeline_reproduces_its_registered_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            for pid, d in entries():
                with self.subTest(pid=pid):
                    out = Path(tmp) / f"{pid}.json"
                    subprocess.run([sys.executable, str(ROOT / "pipelines" / f"predictions_compute_{pid}.py"),
                                    "--output", str(out)], check=True, capture_output=True)
                    self.assertEqual(out.read_bytes(), (d / "pipeline_output.json").read_bytes(),
                                     f"{pid}: recomputed output differs from the registered one")

    def test_scorers_return_registered_verdicts_without_changing_scorecards(self):
        scored = {pid: d for pid, d in entries() if (d / "scorecard.md").is_file()}
        self.assertEqual(set(scored), set(EXPECTED_VERDICTS), "the set of scored predictions changed")
        for pid, d in scored.items():
            with self.subTest(pid=pid):
                before = (d / "scorecard.md").read_bytes()
                proc = subprocess.run([sys.executable, str(ROOT / "pipelines" / f"predictions_score_{pid}.py")],
                                      capture_output=True, text=True)
                self.assertIn(f"outcome: {EXPECTED_VERDICTS[pid]}", proc.stdout)
                self.assertEqual(before, (d / "scorecard.md").read_bytes(), f"{pid}: rescoring changed the scorecard")

    def test_generated_files_are_current(self):
        for tool in ("make_predictions_table.py", "make_register_manifest.py"):
            with self.subTest(tool=tool):
                proc = subprocess.run([sys.executable, str(ROOT / "pipelines" / tool), "--check"],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
