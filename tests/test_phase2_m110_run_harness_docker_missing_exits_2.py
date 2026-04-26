import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_run_harness.py"


class TestPhase2M110RunHarnessDockerMissingExits2(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

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

    def test_docker_missing_returns_exit_2(self) -> None:
        if shutil.which("docker") is not None:
            self.skipTest("docker is available in this environment; missing-docker gate is not applicable")

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            run_dir = td_path / "run_dir"

            cmd = [
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
            ]
            proc = self._run(cmd)
            self.assertEqual(proc.returncode, 2, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertIn("docker not found", (proc.stderr or "").lower())


if __name__ == "__main__":
    unittest.main()
