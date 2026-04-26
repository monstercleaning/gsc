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
SANITY_SCRIPT = ROOT / "scripts" / "phase3_pt_spectra_sanity_report.py"


def _make_fake_class_with_headered_cl(path: Path) -> Path:
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
                "mkdir -p output",
                'cp "$INI_PATH" used_class.ini',
                "cat > output/cl.dat <<'EOF'",
                "# l TT EE TE",
                "2 100 5 20",
                "50 900 20 100",
                "100 1300 25 150",
                "220 2050 35 220",
                "500 700 18 80",
                "1000 300 10 30",
                "EOF",
                'echo "fake class run complete"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


class TestPhase3M126SpectraSanityReportDetectsTTFromClassClDatToy(unittest.TestCase):
    def test_detects_tt_metrics_from_headered_class_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = td_path / "export_pack"
            run_dir = td_path / "run_dir"
            results_out = td_path / "results_out"
            sanity_out = td_path / "sanity_out"
            fake_bin = _make_fake_class_with_headered_cl(td_path / "fake_class.sh")

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
                    "5",
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
                text=True,
                capture_output=True,
                env=env,
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
                    str(results_out),
                    "--overwrite",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_results.returncode, 0, msg=(proc_results.stdout or "") + (proc_results.stderr or ""))

            proc_sanity = subprocess.run(
                [
                    sys.executable,
                    str(SANITY_SCRIPT),
                    "--path",
                    str(results_out),
                    "--outdir",
                    str(sanity_out),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--require-tt",
                    "1",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_sanity.returncode, 0, msg=(proc_sanity.stdout or "") + (proc_sanity.stderr or ""))
            report = json.loads((sanity_out / "SPECTRA_SANITY_REPORT.json").read_text(encoding="utf-8"))
            tt = report.get("tt_metrics") or {}
            selected = report.get("selected_spectra_file") or {}
            self.assertTrue(bool(tt.get("has_tt")))
            self.assertIsInstance(tt.get("peak1_ell"), int)
            self.assertLessEqual(abs(int(tt.get("peak1_ell")) - 220), 5)
            relpath = str(selected.get("relpath") or "")
            self.assertIn("output/cl.dat", relpath)


if __name__ == "__main__":
    unittest.main()

