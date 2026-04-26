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
RESULTS_SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_results_pack.py"


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
                "2 80",
                "50 820",
                "100 1320",
                "220 1980",
                "500 610",
                "1000 250",
                "EOF",
                'echo \"fake class run complete\"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


class TestPhase3M125ResultsPackSmokeFromFakeClassRunToy(unittest.TestCase):
    def test_results_pack_from_fake_class_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = td_path / "export_pack"
            run_dir = td_path / "run_dir"
            outdir = td_path / "results_out"
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
            proc_harness = subprocess.run(
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
            self.assertEqual(proc_harness.returncode, 0, msg=(proc_harness.stdout or "") + (proc_harness.stderr or ""))

            proc_results = subprocess.run(
                [
                    sys.executable,
                    str(RESULTS_SCRIPT),
                    "--export-pack",
                    str(export_pack),
                    "--run-dir",
                    str(run_dir),
                    "--outdir",
                    str(outdir),
                    "--overwrite",
                    "--format",
                    "json",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_results.returncode, 0, msg=(proc_results.stdout or "") + (proc_results.stderr or ""))
            self.assertTrue((outdir / "RESULTS_SUMMARY.json").is_file())

            summary = json.loads((outdir / "RESULTS_SUMMARY.json").read_text(encoding="utf-8"))
            spectra = summary.get("spectra_detected") or {}
            self.assertTrue(bool(spectra.get("has_tt")))
            self.assertTrue((outdir / "outputs" / "toy_tt.dat").is_file())


if __name__ == "__main__":
    unittest.main()

