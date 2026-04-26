import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_lineage_dag.py"


class TestPhase2M115LineageJsonHasNoAbsoluteBundleDir(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _make_bundle(self, base: Path) -> Path:
        bundle = base / "bundle"
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "merged.jsonl").write_text('{"status":"ok","chi2_total":1.0}\n', encoding="utf-8")
        self._write_json(bundle / "scan_config.json", {"scan_config_sha256": "a" * 64})
        self._write_json(bundle / "plan.json", {"schema": "phase2_e2_refine_plan_v1", "points": [{"point_id": "p0"}]})
        self._write_json(
            bundle / "manifest.json",
            {
                "schema": "phase2_e2_manifest_v1",
                "inputs": [{"path": "plan.json"}, {"path": "scan_config.json"}],
                "artifacts": [{"path": "merged.jsonl"}],
            },
        )
        return bundle

    def test_default_payload_redacts_absolute_bundle_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle = self._make_bundle(td_path)
            out = td_path / "LINEAGE.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--bundle-dir",
                    str(bundle),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--out",
                    str(out),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_dir"), ".")
            self.assertNotIn("bundle_dir_abs", payload)

            rendered = out.read_text(encoding="utf-8")
            self.assertNotIn("/Users/", rendered)
            self.assertNotIn("/home/", rendered)
            self.assertNotIn("/var/folders/", rendered)
            self.assertNotIn("C:\\Users\\", rendered)


if __name__ == "__main__":
    unittest.main()
