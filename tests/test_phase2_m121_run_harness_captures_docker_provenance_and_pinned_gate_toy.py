import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_run_harness.py"


class TestPhase2M121RunHarnessDockerProvenanceAndPinnedGateToy(unittest.TestCase):
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
                'if [[ "${1:-}" == "run" ]]; then',
                '  echo "run_ok"',
                "  exit 0",
                "fi",
                'if [[ "${1:-}" == "image" && "${2:-}" == "inspect" ]]; then',
                '  image="${3:-}"',
                '  fmt="${5:-}"',
                '  if [[ "$fmt" == "{{json .RepoDigests}}" ]]; then',
                '    echo "[\\\"${image%@*}@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\\"]"',
                "    exit 0",
                "  fi",
                '  if [[ "$fmt" == "{{json .Id}}" ]]; then',
                '    echo "\\\"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\\""',
                "    exit 0",
                "  fi",
                "fi",
                'if [[ "${1:-}" == "version" ]]; then',
                '  echo "{\"Client\":{\"Version\":\"25.0.0\"},\"Server\":{\"Version\":\"25.0.0\"}}"',
                "  exit 0",
                "fi",
                'echo "unsupported docker invocation: $*" >&2',
                "exit 3",
                "",
            ]
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_capture_docker_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            fake_bin_dir = td_path / "bin"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            self._make_fake_docker(fake_bin_dir / "docker")
            run_dir = td_path / "run"

            env = os.environ.copy()
            env["PATH"] = str(fake_bin_dir) + os.pathsep + env.get("PATH", "")
            env["GSC_CLASS_DOCKER_IMAGE"] = "fake/class:v1.2.3"

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

            payload = json.loads((run_dir / "RUN_METADATA.json").read_text(encoding="utf-8"))
            external_code = payload.get("external_code") or {}
            self.assertEqual(external_code.get("runner"), "docker")
            docker = external_code.get("docker") or {}
            self.assertEqual(docker.get("image_ref"), "fake/class:v1.2.3")
            self.assertTrue(bool(docker.get("image_is_pinned")))
            self.assertTrue(bool(docker.get("inspect_ok")))
            self.assertEqual(docker.get("image_id"), "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
            self.assertIsInstance(docker.get("image_repo_digests"), list)
            self.assertGreaterEqual(len(docker.get("image_repo_digests")), 1)

    def test_require_pinned_image_gate_fails_for_latest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            fake_bin_dir = td_path / "bin"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            self._make_fake_docker(fake_bin_dir / "docker")
            run_dir = td_path / "run"

            env = os.environ.copy()
            env["PATH"] = str(fake_bin_dir) + os.pathsep + env.get("PATH", "")
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
                    "--require-pinned-image",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                env=env,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("HARNESS_UNPINNED_DOCKER_IMAGE", output)


if __name__ == "__main__":
    unittest.main()
