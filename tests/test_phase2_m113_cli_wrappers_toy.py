import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI_SCRIPT = ROOT / "scripts" / "gsc_cli.py"


class TestPhase2M113CLIWrappersToy(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=str(ROOT.parent),
            text=True,
            capture_output=True,
        )

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def test_results_help_subcommand(self) -> None:
        proc = self._run(
            [
                sys.executable,
                str(CLI_SCRIPT),
                "phase2",
                "pt",
                "results",
                "--help",
            ]
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)
        self.assertIn("gsc phase2 pt results", output)

    def test_results_dispatch_toy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = td_path / "export_pack"
            run_dir = td_path / "run_dir"
            out_dir = td_path / "out_dir"
            export_pack.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(parents=True, exist_ok=True)

            self._write_json(
                export_pack / "EXPORT_SUMMARY.json",
                {
                    "tool": "phase2_pt_boltzmann_export_pack",
                    "schema": "phase2_pt_boltzmann_export_pack_v1",
                    "selection": {"rank_by": "cmb"},
                },
            )
            self._write_json(
                export_pack / "CANDIDATE_RECORD.json",
                {
                    "schema": "phase2_pt_boltzmann_export_candidate_v1",
                    "selection": {"rank_by": "cmb"},
                    "best": {"best_params_hash": "m113_toy"},
                    "record": {"status": "ok", "params_hash": "m113_toy"},
                },
            )
            (run_dir / "toy_tt.dat").write_text("# ell C_ell\n2 1.0\n20 5.0\n200 25.0\n", encoding="utf-8")
            (run_dir / "run.log").write_text("toy class run\n", encoding="utf-8")

            proc = self._run(
                [
                    sys.executable,
                    str(CLI_SCRIPT),
                    "phase2",
                    "pt",
                    "results",
                    "--",
                    "--export-pack",
                    str(export_pack),
                    "--run-dir",
                    str(run_dir),
                    "--outdir",
                    str(out_dir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--format",
                    "json",
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("schema"), "phase2_pt_boltzmann_results_pack_v1")
            self.assertTrue((out_dir / "RESULTS_SUMMARY.json").is_file())


if __name__ == "__main__":
    unittest.main()
