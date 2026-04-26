import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_run_harness.py"


class TestPhase2M121RunHarnessCapturesNativeBinaryShaAndVersionToy(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _make_export_pack(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        self._write_json(path / "EXPORT_SUMMARY.json", {"schema": "phase2_pt_boltzmann_export_pack_v1"})
        self._write_json(path / "CANDIDATE_RECORD.json", {"schema": "phase2_pt_boltzmann_export_candidate_v1"})
        (path / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini").write_text("h = 0.67\n", encoding="utf-8")
        return path

    def _make_fake_native_solver(self, path: Path) -> Path:
        script = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'if [[ "${1:-}" == "--version" ]]; then',
                '  echo "fake-native-solver 1.2.3"',
                "  exit 0",
                "fi",
                'ini="${1:-}"',
                'if [[ -z "$ini" ]]; then',
                '  echo "missing ini" >&2',
                "  exit 4",
                "fi",
                'cp "$ini" used_class.ini',
                'echo "run-ok" > toy_tt.dat',
                "",
            ]
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_native_metadata_includes_bin_sha_and_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            fake_solver = self._make_fake_native_solver(td_path / "fake_solver.sh")
            run_dir = td_path / "run"

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
                    "--bin",
                    str(fake_solver),
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
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            payload = json.loads((run_dir / "RUN_METADATA.json").read_text(encoding="utf-8"))
            external_code = payload.get("external_code") or {}
            self.assertEqual(external_code.get("runner"), "native")
            native = external_code.get("native") or {}
            self.assertEqual(native.get("bin_name"), fake_solver.name)
            self.assertRegex(str(native.get("bin_sha256", "")), r"^[0-9a-f]{64}$")
            self.assertTrue(bool(native.get("version_ok")))
            self.assertEqual(native.get("version_first_line"), "fake-native-solver 1.2.3")

            dump = json.dumps(payload, sort_keys=True)
            self.assertNotIn(str(fake_solver.resolve()), dump)
            self.assertNotIn("/Users/", dump)
            self.assertNotIn("/home/", dump)
            self.assertNotIn("/var/folders/", dump)
            self.assertNotRegex(dump, re.compile(r"C:\\\\Users\\\\"))


if __name__ == "__main__":
    unittest.main()
