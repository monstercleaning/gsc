import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"


def _sha256_bytes(payload: bytes) -> str:
    h = hashlib.sha256()
    h.update(payload)
    return h.hexdigest()


def _write_catalog(path: Path, *, asset_name: str, sha: str) -> None:
    catalog = {
        "schema_version": 2,
        "artifacts": {
            "late_time": {
                "type": "late-time",
                "tier": "frozen",
                "tag": "vL",
                "release_url": "https://example.com/L",
                "asset": asset_name,
                "sha256": sha,
            },
            "submission": {
                "type": "submission",
                "tier": "frozen",
                "tag": "vS",
                "release_url": "https://example.com/S",
                "asset": asset_name,
                "sha256": sha,
            },
            "referee_pack": {
                "type": "referee",
                "tier": "recommended",
                "tag": "vR",
                "release_url": "https://example.com/R",
                "asset": asset_name,
                "sha256": sha,
            },
            "toe_bundle": {
                "type": "toe",
                "tier": "recommended",
                "tag": "vT",
                "release_url": "https://example.com/T",
                "asset": asset_name,
                "sha256": sha,
            },
        },
    }
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


class TestOperatorOneButtonReport(unittest.TestCase):
    def test_report_includes_artifact_integrity_and_step_durations(self):
        script = SCRIPTS / "operator_one_button.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            asset = td / "toy.zip"
            payload = b"toy"
            asset.write_bytes(payload)
            sha = _sha256_bytes(payload)
            catalog = td / "catalog.json"
            report = td / "report.json"
            _write_catalog(catalog, asset_name=asset.name, sha=sha)

            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--catalog",
                    str(catalog),
                    "--artifacts-dir",
                    str(td),
                    "--dry-run",
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertTrue(report.is_file())

            obj = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(obj.get("overall_status"), "PASS")
            self.assertEqual(obj.get("result"), "PASS")
            self.assertIn("summary", obj)
            self.assertGreaterEqual(float(obj["summary"].get("duration_sec_total", -1)), 0.0)

            artifacts = obj.get("artifacts", [])
            self.assertEqual(len(artifacts), 4)
            for row in artifacts:
                self.assertTrue(row.get("present_before_fetch"))
                self.assertTrue(row.get("present_after_fetch"))
                self.assertFalse(row.get("fetched_during_run"))
                self.assertEqual(row.get("sha256_actual"), sha)
                self.assertTrue(row.get("sha256_match"))

            steps = obj.get("steps", [])
            self.assertGreaterEqual(len(steps), 1)
            for s in steps:
                self.assertIn("started_utc", s)
                self.assertIn("finished_utc", s)
                self.assertGreaterEqual(float(s.get("duration_sec", -1)), 0.0)


if __name__ == "__main__":
    unittest.main()
