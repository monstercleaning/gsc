import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_schema_validate.py"
SCHEMA_DIR = ROOT / "schemas"


class TestPhase2M117SchemaValidateAutoSelectsSchemaToy(unittest.TestCase):
    def _run(self, payload_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--auto",
                "--schema-dir",
                str(SCHEMA_DIR),
                "--json",
                str(payload_path),
                "--format",
                "json",
            ],
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )

    def test_auto_select_passes_for_known_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            payload_path = td_path / "lineage.json"
            payload = {
                "schema": "phase2_lineage_dag_v1",
                "bundle_dir": ".",
                "manifest_relpath": "manifest.json",
                "nodes": [],
                "edges": [],
                "counts": {"n_nodes": 0, "n_edges": 0},
            }
            payload_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

            proc = self._run(payload_path)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            report = json.loads(proc.stdout)
            self.assertTrue(bool(report.get("ok")), msg=output)
            self.assertIn("phase2_lineage_dag_v1", str(report.get("schema_selected_by", "")))

    def test_auto_select_fails_for_unknown_schema_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            payload_path = td_path / "unknown.json"
            payload_path.write_text(
                json.dumps({"schema": "phase2_unknown_schema_v1", "value": 1}, sort_keys=True),
                encoding="utf-8",
            )

            proc = self._run(payload_path)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("unknown schema id", output.lower())


if __name__ == "__main__":
    unittest.main()
