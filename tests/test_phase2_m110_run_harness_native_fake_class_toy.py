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


class TestPhase2M110RunHarnessNativeFakeClassToy(unittest.TestCase):
    def _run(self, cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, env=env)

    def _make_export_pack(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        (path / "EXPORT_SUMMARY.json").write_text(
            json.dumps({"schema": "phase2_pt_boltzmann_export_pack_v1", "tool": "phase2_pt_boltzmann_export_pack"}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (path / "CANDIDATE_RECORD.json").write_text(
            json.dumps({"schema": "phase2_pt_boltzmann_export_candidate_v1", "record": {"params_hash": "m110_native"}}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (path / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini").write_text("h = 0.67\n", encoding="utf-8")
        return path

    def _make_fake_class_bin(self, path: Path) -> Path:
        script = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'INI_PATH="${1:-}"',
                'if [[ -z "$INI_PATH" ]]; then',
                '  echo "missing ini path" >&2',
                "  exit 3",
                "fi",
                'cp "$INI_PATH" used_class.ini',
                "cat > toy_tt.dat <<'EOF'",
                "# ell C_ell",
                "2 100",
                "50 900",
                "100 1300",
                "220 2000",
                "500 650",
                "1000 280",
                "EOF",
                'echo "fake class run complete"',
                "",
            ]
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_native_fake_class_run_writes_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            fake_bin = self._make_fake_class_bin(td_path / "fake_class.sh")
            run_dir = td_path / "run_dir"

            cmd = [
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
            ]
            env = os.environ.copy()
            env["GSC_CLASS_BIN"] = str(fake_bin)
            proc = self._run(cmd, env=env)
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            self.assertTrue((run_dir / "RUN_METADATA.json").is_file())
            self.assertTrue((run_dir / "run.log").is_file())
            self.assertTrue((run_dir / "toy_tt.dat").is_file())

            payload = json.loads((run_dir / "RUN_METADATA.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_pt_boltzmann_run_metadata_v1")
            self.assertEqual(payload.get("created_utc"), "2000-01-01T00:00:00Z")
            self.assertEqual(payload.get("code"), "class")
            self.assertEqual(payload.get("runner"), "native")
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertEqual(int(payload.get("returncode")), 0)
            self.assertEqual(payload.get("run_dir"), ".")
            self.assertTrue(str(payload.get("run_log", "")).endswith("run.log"))

            input_files = payload.get("input_files")
            self.assertIsInstance(input_files, list)
            self.assertGreaterEqual(len(input_files), 3)
            for row in input_files:
                self.assertRegex(str(row.get("sha256", "")), r"^[0-9a-f]{64}$")

            command_argv = payload.get("command_argv")
            self.assertIsInstance(command_argv, list)
            self.assertGreaterEqual(len(command_argv), 2)
            self.assertEqual(str(command_argv[0]), f"[abs]/{fake_bin.name}")
            self.assertTrue(str(command_argv[1]).endswith("BOLTZMANN_INPUT_TEMPLATE_CLASS.ini"))

            run_log = (run_dir / "run.log").read_text(encoding="utf-8")
            self.assertIn("fake class run complete", run_log)


if __name__ == "__main__":
    unittest.main()
