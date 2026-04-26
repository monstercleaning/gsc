import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_results_pack.py"


class TestPhase2M120ResultsPackRedactsRunLogWhenNeededToy(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _make_export_pack(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        self._write_json(path / "EXPORT_SUMMARY.json", {"schema": "phase2_pt_boltzmann_export_pack_v1"})
        self._write_json(path / "CANDIDATE_RECORD.json", {"schema": "phase2_pt_boltzmann_export_candidate_v1"})
        return path

    def _make_run_dir(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        (path / "toy_tt.dat").write_text("2 1\n50 2\n100 3\n220 4\n500 2\n", encoding="utf-8")
        leak_text = (
            "solver run\n"
            f"abs_run_dir={path.resolve()}\n"
            "host_path=/home/alice/secret\n"
            "win_path=C:\\Users\\alice\\secret\n"
        )
        (path / "run.log").write_text(leak_text, encoding="utf-8")
        return path

    def test_default_redacts_leaking_run_log(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            run_dir = self._make_run_dir(td_path / "run_dir")
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

            self.assertTrue((outdir / "outputs" / "run_REDACTED.log").is_file())
            self.assertFalse((outdir / "outputs" / "run.log").exists())

            summary = json.loads((outdir / "RESULTS_SUMMARY.json").read_text(encoding="utf-8"))
            run_log = summary.get("run_log") or {}
            self.assertEqual(run_log.get("path"), "outputs/run_REDACTED.log")
            self.assertTrue(bool(run_log.get("paths_redacted")))
            summary_text = json.dumps(summary, sort_keys=True)
            self.assertNotIn(str(run_dir.resolve()), summary_text)
            self.assertNotIn("/home/alice/secret", summary_text)

    def test_include_unredacted_logs_writes_explicit_copy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            run_dir = self._make_run_dir(td_path / "run_dir")
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
                    "--include-unredacted-logs",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue((outdir / "outputs" / "run_REDACTED.log").is_file())
            self.assertTrue((outdir / "outputs" / "run_UNREDACTED.log").is_file())


if __name__ == "__main__":
    unittest.main()
