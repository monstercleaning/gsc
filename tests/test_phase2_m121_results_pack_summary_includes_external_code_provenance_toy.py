import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_results_pack.py"


class TestPhase2M121ResultsPackSummaryIncludesExternalCodeProvenanceToy(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _make_export_pack(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        self._write_json(path / "EXPORT_SUMMARY.json", {"schema": "phase2_pt_boltzmann_export_pack_v1"})
        self._write_json(path / "CANDIDATE_RECORD.json", {"schema": "phase2_pt_boltzmann_export_candidate_v1"})
        return path

    def test_summary_includes_external_code_without_absolute_path_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            run_dir = td_path / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "toy_tt.dat").write_text("2 1.0\n10 2.0\n50 5.0\n100 7.0\n220 9.0\n", encoding="utf-8")
            (run_dir / "run.log").write_text("run ok\n", encoding="utf-8")
            self._write_json(
                run_dir / "RUN_METADATA.json",
                {
                    "schema": "phase2_pt_boltzmann_run_metadata_v1",
                    "external_code": {
                        "runner": "docker",
                        "docker": {
                            "image_ref": "fake/class:v1.2.3",
                            "image_is_pinned": True,
                            "docker_bin": "/home/alice/bin/docker",
                            "inspect_ok": True,
                        },
                    },
                    "run_dir": "/Users/alice/private/run_dir",
                    "command_argv": ["/var/folders/xx/bin/docker"],
                    "input_files": [{"source": "C:\\Users\\alice\\input\\template.ini"}],
                },
            )

            outdir = td_path / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--export-pack",
                    str(export_pack),
                    "--run-dir",
                    str(run_dir),
                    "--outdir",
                    str(outdir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            summary = json.loads((outdir / "RESULTS_SUMMARY.json").read_text(encoding="utf-8"))
            external_code = summary.get("external_code") or {}
            self.assertEqual(external_code.get("runner"), "docker")

            dump = json.dumps(summary, sort_keys=True)
            self.assertNotIn("/Users/", dump)
            self.assertNotIn("/home/", dump)
            self.assertNotIn("/var/folders/", dump)
            self.assertNotRegex(dump, re.compile(r"C:\\\\Users\\\\"))


if __name__ == "__main__":
    unittest.main()
