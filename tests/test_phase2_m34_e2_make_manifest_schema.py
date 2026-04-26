import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M34E2MakeManifestSchema(unittest.TestCase):
    def test_manifest_schema_and_sha256(self):
        script = ROOT / "scripts" / "phase2_e2_make_manifest.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            outdir = tmp / "out"
            outdir.mkdir(parents=True, exist_ok=True)

            artifact_a = outdir / "a.txt"
            artifact_b = outdir / "z.jsonl"
            artifact_a.write_text("alpha\n", encoding="utf-8")
            artifact_b.write_text('{"k":1}\n', encoding="utf-8")

            input_a = tmp / "in_a.py"
            input_b = tmp / "in_b.md"
            input_a.write_text("print('x')\n", encoding="utf-8")
            input_b.write_text("# note\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--outdir",
                str(outdir),
                "--repo-root",
                str(ROOT),
                "--artifact",
                str(artifact_b),
                "--artifact",
                str(artifact_a),
                "--input",
                str(input_b),
                "--input",
                str(input_a),
                "--manifest-name",
                "manifest.json",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            manifest_path = outdir / "manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(manifest.get("schema"), "phase2_e2_manifest_v1")
            self.assertIn("artifacts", manifest)
            self.assertIn("inputs", manifest)
            self.assertIn("python", manifest)
            self.assertIn("run", manifest)

            artifact_paths = [str(item.get("path")) for item in manifest.get("artifacts") or []]
            self.assertEqual(artifact_paths, sorted(artifact_paths))

            expected_sha_a = hashlib.sha256(artifact_a.read_bytes()).hexdigest()
            sha_by_path = {str(item.get("path")): str(item.get("sha256")) for item in manifest.get("artifacts") or []}
            self.assertEqual(sha_by_path.get("a.txt"), expected_sha_a)


if __name__ == "__main__":
    unittest.main()
