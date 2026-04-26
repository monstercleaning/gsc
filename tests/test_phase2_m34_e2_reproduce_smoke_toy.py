import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M34E2ReproduceSmokeToy(unittest.TestCase):
    def test_reproduce_pipeline_toy_with_refine_and_manifest(self):
        script = ROOT / "scripts" / "phase2_e2_reproduce.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            cmd = [
                sys.executable,
                str(script),
                "--outdir",
                str(out_dir),
                "--toy",
                "--emit-refine-plan",
                "--jobs",
                "2",
                "--scan-args",
                "--model lcdm --sampler random --n-samples 10 --grid H0=60:75 --grid Omega_m=0.2:0.4",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            base_jsonl = out_dir / "e2_base.jsonl"
            refine_plan = out_dir / "e2_refine_plan.json"
            refine_jsonl = out_dir / "e2_refine.jsonl"
            refine_summary = out_dir / "e2_refine_summary.json"
            combined_jsonl = out_dir / "e2_combined.jsonl"
            manifest_json = out_dir / "manifest.json"

            self.assertTrue(base_jsonl.is_file())
            self.assertTrue(refine_plan.is_file())
            self.assertTrue(refine_jsonl.is_file())
            self.assertTrue(refine_summary.is_file())
            self.assertTrue(combined_jsonl.is_file())
            self.assertTrue(manifest_json.is_file())

            base_lines = [line for line in base_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreater(len(base_lines), 0)
            refine_lines = [line for line in refine_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreater(len(refine_lines), 0)

            refine_summary_payload = json.loads(refine_summary.read_text(encoding="utf-8"))
            self.assertFalse(bool(refine_summary_payload.get("toy_refine_placeholder")))

            combined_rows = [
                json.loads(line)
                for line in combined_jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertGreater(len(combined_rows), 0)
            hashes = [str(row.get("params_hash", "")) for row in combined_rows]
            self.assertEqual(hashes, sorted(hashes))

            manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("schema"), "phase2_e2_manifest_v1")
            artifacts = manifest.get("artifacts") or []
            artifact_paths = {str(item.get("path")) for item in artifacts}
            self.assertIn("e2_combined.jsonl", artifact_paths)
            self.assertIn("e2_refine_plan.json", artifact_paths)


if __name__ == "__main__":
    unittest.main()
