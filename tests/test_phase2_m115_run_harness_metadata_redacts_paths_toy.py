import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_run_harness.py"
WIN_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


class TestPhase2M115RunHarnessMetadataRedactsPathsToy(unittest.TestCase):
    def _make_export_pack(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        (path / "EXPORT_SUMMARY.json").write_text(
            json.dumps({"schema": "phase2_pt_boltzmann_export_pack_v1"}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (path / "CANDIDATE_RECORD.json").write_text(
            json.dumps({"schema": "phase2_pt_boltzmann_export_candidate_v1"}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (path / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini").write_text("h = 0.67\n", encoding="utf-8")
        return path

    def _make_fake_class(self, path: Path) -> Path:
        path.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\necho 'ok' > toy_tt.dat\necho 'done'\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def test_run_metadata_redacts_absolute_paths_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            fake_bin = self._make_fake_class(td_path / "fake_class.sh")
            run_dir = td_path / "run"

            env = os.environ.copy()
            env["GSC_CLASS_BIN"] = str(fake_bin)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--export-pack",
                    str(export_pack),
                    "--code",
                    "class",
                    "--runner",
                    "native",
                    "--run-dir",
                    str(run_dir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--overwrite",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                env=env,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            payload = json.loads((run_dir / "RUN_METADATA.json").read_text(encoding="utf-8"))
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertEqual(payload.get("run_dir"), ".")
            self.assertNotIn("run_dir_abs", payload)

            rendered = json.dumps(payload, sort_keys=True)
            self.assertNotIn(str(run_dir), rendered)
            self.assertNotIn("/Users/", rendered)
            self.assertNotIn("/home/", rendered)
            self.assertNotIn("/var/folders/", rendered)

            for row in payload.get("input_files", []):
                if not isinstance(row, dict):
                    continue
                source = str(row.get("source", ""))
                self.assertFalse(source.startswith("/"), msg=source)
                self.assertIsNone(WIN_ABS_RE.match(source), msg=source)


if __name__ == "__main__":
    unittest.main()
