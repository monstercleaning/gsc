import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_pt_boltzmann_results_pack.py"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase2M106PtBoltzmannResultsPackDeterminismToy(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _make_export_pack(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        export_summary = {
            "tool": "phase2_pt_boltzmann_export_pack",
            "schema": "phase2_pt_boltzmann_export_pack_v1",
            "selection": {"rank_by": "cmb"},
            "best": {"best_params_hash": "m106_best", "best_plan_point_id": "pp-1"},
        }
        candidate = {
            "schema": "phase2_pt_boltzmann_export_candidate_v1",
            "selection": {"rank_by": "cmb"},
            "best": {"best_params_hash": "m106_best", "best_plan_point_id": "pp-1"},
            "record": {
                "status": "ok",
                "params_hash": "m106_best",
                "plan_point_id": "pp-1",
                "scan_config_sha256": "a" * 64,
                "plan_source_sha256": "b" * 64,
            },
        }
        (path / "EXPORT_SUMMARY.json").write_text(json.dumps(export_summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (path / "CANDIDATE_RECORD.json").write_text(json.dumps(candidate, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (path / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini").write_text("h = 0.67\n", encoding="utf-8")
        return path

    def _make_run_dir_with_tt(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        tt = """# ell C_ell\n2 100\n50 900\n100 1500\n220 2000\n500 700\n1000 300\n"""
        (path / "toy_tt.dat").write_text(tt, encoding="utf-8")
        (path / "run.log").write_text("CLASS v3 toy run\n", encoding="utf-8")
        return path

    def test_deterministic_zip_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")
            run_dir = self._make_run_dir_with_tt(td_path / "run_dir")

            out1 = td_path / "out1"
            out2 = td_path / "out2"
            zip1 = td_path / "results1.zip"
            zip2 = td_path / "results2.zip"

            base_cmd = [
                sys.executable,
                str(SCRIPT),
                "--export-pack",
                str(export_pack),
                "--run-dir",
                str(run_dir),
                "--outdir",
                str(out1),
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--zip-out",
                str(zip1),
                "--format",
                "json",
            ]
            run1 = self._run(base_cmd)
            self.assertEqual(run1.returncode, 0, msg=(run1.stdout or "") + (run1.stderr or ""))
            payload1 = json.loads(run1.stdout)
            self.assertEqual(payload1.get("schema"), "phase2_pt_boltzmann_results_pack_v1")

            cmd2 = list(base_cmd)
            cmd2[cmd2.index(str(out1))] = str(out2)
            cmd2[cmd2.index(str(zip1))] = str(zip2)
            run2 = self._run(cmd2)
            self.assertEqual(run2.returncode, 0, msg=(run2.stdout or "") + (run2.stderr or ""))

            self.assertTrue(zip1.is_file())
            self.assertTrue(zip2.is_file())
            self.assertEqual(_sha256_path(zip1), _sha256_path(zip2))

            summary = json.loads((out1 / "RESULTS_SUMMARY.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("schema"), "phase2_pt_boltzmann_results_pack_v1")
            self.assertTrue(summary.get("spectra_detected", {}).get("has_tt"))
            self.assertIn("files", summary)

            with zipfile.ZipFile(zip1, "r") as zf:
                names = sorted(zf.namelist())
                self.assertIn("boltzmann_results_pack/RESULTS_SUMMARY.json", names)
                self.assertIn("boltzmann_results_pack/README.md", names)
                self.assertIn("boltzmann_results_pack/export_pack/EXPORT_SUMMARY.json", names)
                self.assertIn("boltzmann_results_pack/outputs/toy_tt.dat", names)

    def test_require_tt_gate_and_symlink_failfast(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            export_pack = self._make_export_pack(td_path / "export_pack")

            run_no_tt = td_path / "run_no_tt"
            run_no_tt.mkdir(parents=True, exist_ok=True)
            (run_no_tt / "run.log").write_text("no spectra\n", encoding="utf-8")

            out_gate = td_path / "out_gate"
            cmd_gate = [
                sys.executable,
                str(SCRIPT),
                "--export-pack",
                str(export_pack),
                "--run-dir",
                str(run_no_tt),
                "--outdir",
                str(out_gate),
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--require",
                "tt_spectrum",
            ]
            run_gate = self._run(cmd_gate)
            self.assertEqual(run_gate.returncode, 2, msg=(run_gate.stdout or "") + (run_gate.stderr or ""))
            self.assertIn("MISSING_TT_SPECTRUM_FOR_RESULTS_PACK", run_gate.stderr)

            run_symlink = td_path / "run_symlink"
            run_symlink.mkdir(parents=True, exist_ok=True)
            target = run_symlink / "target.log"
            target.write_text("x\n", encoding="utf-8")
            link = run_symlink / "linked.log"
            if hasattr(os, "symlink"):
                try:
                    os.symlink(str(target), str(link))
                except (OSError, NotImplementedError):
                    self.skipTest("symlink creation not supported in this environment")
            else:
                self.skipTest("symlink creation not supported")

            out_symlink = td_path / "out_symlink"
            cmd_symlink = [
                sys.executable,
                str(SCRIPT),
                "--export-pack",
                str(export_pack),
                "--run-dir",
                str(run_symlink),
                "--outdir",
                str(out_symlink),
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]
            run_sym = self._run(cmd_symlink)
            self.assertEqual(run_sym.returncode, 1, msg=(run_sym.stdout or "") + (run_sym.stderr or ""))
            self.assertIn("symlink", (run_sym.stderr or "").lower())


if __name__ == "__main__":
    unittest.main()
