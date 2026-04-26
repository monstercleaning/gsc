import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = ROOT / "scripts" / "phase3_pt_sigmatensor_class_export_pack.py"
HARNESS_SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_run_harness.py"


def _make_fake_class_bin(path: Path) -> Path:
    path.write_text(
        "\n".join(
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
                "100 1400",
                "220 2100",
                "500 620",
                "1000 260",
                "EOF",
                'echo \"fake class run complete\"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


class TestPhase3M125ExportPackRunsWithPhase2HarnessNativeFakeClassToy(unittest.TestCase):
    def test_harness_native_fake_class_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = td_path / "export_pack"
            run_dir = td_path / "run_dir"
            fake_bin = _make_fake_class_bin(td_path / "fake_class.sh")

            proc_export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT_SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.315",
                    "--w0",
                    "-0.95",
                    "--lambda",
                    "0.4",
                    "--z-max",
                    "3",
                    "--n-steps",
                    "128",
                    "--outdir",
                    str(export_pack),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_export.returncode, 0, msg=(proc_export.stdout or "") + (proc_export.stderr or ""))

            env = os.environ.copy()
            env["GSC_CLASS_BIN"] = str(fake_bin)
            proc_run = subprocess.run(
                [
                    sys.executable,
                    str(HARNESS_SCRIPT),
                    "--export-pack",
                    str(export_pack),
                    "--code",
                    "class",
                    "--runner",
                    "native",
                    "--run-dir",
                    str(run_dir),
                    "--overwrite",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_run.returncode, 0, msg=(proc_run.stdout or "") + (proc_run.stderr or ""))
            self.assertTrue((run_dir / "RUN_METADATA.json").is_file())
            self.assertTrue((run_dir / "run.log").is_file())
            self.assertTrue((run_dir / "toy_tt.dat").is_file())

            payload = json.loads((run_dir / "RUN_METADATA.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_pt_boltzmann_run_metadata_v1")
            self.assertEqual(payload.get("code"), "class")
            self.assertEqual(payload.get("runner"), "native")
            self.assertEqual(payload.get("created_utc"), "2000-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()

