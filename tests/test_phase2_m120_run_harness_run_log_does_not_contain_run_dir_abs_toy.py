import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_run_harness.py"


class TestPhase2M120RunHarnessRunLogDoesNotContainRunDirAbsToy(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _make_export_pack(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        self._write_json(path / "EXPORT_SUMMARY.json", {"schema": "phase2_pt_boltzmann_export_pack_v1"})
        self._write_json(path / "CANDIDATE_RECORD.json", {"schema": "phase2_pt_boltzmann_export_candidate_v1"})
        (path / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini").write_text("h = 0.67\n", encoding="utf-8")
        return path

    def _make_fake_docker(self, path: Path) -> Path:
        script = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'echo \"docker_argv:$*\"',
                "for ((i=1;i<=$#;i++)); do",
                "  arg=\"${!i}\"",
                "  if [[ \"$arg\" == \"-v\" ]]; then",
                "    j=$((i+1))",
                "    mount=\"${!j:-}\"",
                "    echo \"docker_mount=$mount\"",
                "  fi",
                "done",
                "echo ok",
                "",
            ]
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_docker_mode_run_log_redacts_run_dir_path_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            fake_dir = td_path / "fake_bin"
            fake_dir.mkdir(parents=True, exist_ok=True)
            fake_docker = self._make_fake_docker(fake_dir / "docker")
            run_dir = td_path / "run_dir"

            env = os.environ.copy()
            env["PATH"] = str(fake_dir) + os.pathsep + env.get("PATH", "")
            env["GSC_CLASS_DOCKER_IMAGE"] = "fake/class:latest"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--export-pack",
                    str(export_pack),
                    "--code",
                    "class",
                    "--runner",
                    "docker",
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
            self.assertTrue(fake_docker.is_file())

            run_log = (run_dir / "run.log").read_text(encoding="utf-8")
            self.assertIn("paths_redacted=true", run_log)
            self.assertNotIn(str(run_dir.resolve()), run_log)


if __name__ == "__main__":
    unittest.main()
