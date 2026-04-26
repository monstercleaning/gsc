import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PACK_SCRIPT = ROOT / "scripts" / "phase2_e2_make_reviewer_pack.py"
BUNDLE_SCRIPT = ROOT / "scripts" / "phase2_e2_bundle.py"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase2M105ReviewerPackIncludesBoltzmannExport(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _make_bundle_zip(self, td_path: Path) -> Path:
        shard_a = td_path / "shard_a.jsonl"
        shard_b = td_path / "shard_b.jsonl"
        self._write_jsonl(
            shard_a,
            [
                {"type": "header", "schema": "gsc.phase2.e2.scan.v1"},
                {
                    "params_hash": "m105_hash_a",
                    "plan_point_id": "p0",
                    "status": "ok",
                    "chi2_total": 3.9,
                    "params": {"H0": 67.2, "omega_b": 0.049, "omega_m": 0.31, "As": 2.1e-9, "ns": 0.965, "k_pivot_mpc": 0.05},
                },
            ],
        )
        self._write_jsonl(
            shard_b,
            [
                {
                    "params_hash": "m105_hash_b",
                    "plan_point_id": "p1",
                    "status": "ok",
                    "chi2_total": 4.4,
                    "params": {"H0": 68.1, "omega_b": 0.049, "omega_m": 0.32},
                },
            ],
        )

        bundle_dir = td_path / "bundle_dir"
        proc = self._run(
            [
                sys.executable,
                str(BUNDLE_SCRIPT),
                "--in",
                str(shard_a),
                "--in",
                str(shard_b),
                "--outdir",
                str(bundle_dir),
                "--steps",
                "merge,pareto,manifest,meta",
            ]
        )
        self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
        self.assertTrue((bundle_dir / "manifest.json").is_file())

        bundle_zip = td_path / "bundle.zip"
        with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(bundle_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(bundle_dir).as_posix()
                zf.write(path, arcname=str(PurePosixPath("bundle") / rel))
        return bundle_zip

    def test_include_boltzmann_export_on_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_zip = self._make_bundle_zip(td_path)

            out_shared = td_path / "pack"
            zip_a = td_path / "pack_a.zip"
            zip_b = td_path / "pack_b.zip"

            base_cmd = [
                sys.executable,
                str(REVIEWER_PACK_SCRIPT),
                "--bundle",
                str(bundle_zip),
                "--outdir",
                str(out_shared),
                "--zip-out",
                str(zip_a),
                "--include-repo-snapshot",
                "0",
                "--include-paper-assets",
                "0",
                "--include-verify",
                "0",
                "--include-boltzmann-export",
                "on",
                "--boltzmann-rank-by",
                "cmb",
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--format",
                "json",
            ]
            run_a = self._run(base_cmd)
            self.assertEqual(run_a.returncode, 0, msg=(run_a.stdout or "") + (run_a.stderr or ""))
            self.assertTrue(zip_a.is_file())

            cmd_b = list(base_cmd)
            shutil.rmtree(out_shared)
            cmd_b[cmd_b.index(str(zip_a))] = str(zip_b)
            run_b = self._run(cmd_b)
            self.assertEqual(run_b.returncode, 0, msg=(run_b.stdout or "") + (run_b.stderr or ""))
            self.assertTrue(zip_b.is_file())

            self.assertEqual(_sha256_path(zip_a), _sha256_path(zip_b))
            self.assertLessEqual(zip_a.stat().st_size, 50 * 1024 * 1024)

            with zipfile.ZipFile(zip_a, "r") as zf:
                names = sorted(zf.namelist())
                self.assertIn("reviewer_pack/boltzmann_export.sh", names)
                self.assertIn("reviewer_pack/boltzmann_export/EXPORT_SUMMARY.json", names)
                self.assertIn("reviewer_pack/boltzmann_export/CANDIDATE_RECORD.json", names)
                guide_text = zf.read("reviewer_pack/REVIEWER_GUIDE.md").decode("utf-8")
                self.assertIn("## Boltzmann export (perturbations)", guide_text)
                script_text = zf.read("reviewer_pack/boltzmann_export.sh").decode("utf-8")
                self.assertIn("phase2_pt_boltzmann_export_pack.py", script_text)

    def test_boltzmann_zip_budget_nonpositive_returns_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_zip = self._make_bundle_zip(td_path)
            outdir = td_path / "pack_budget_fail"
            cmd = [
                sys.executable,
                str(REVIEWER_PACK_SCRIPT),
                "--bundle",
                str(bundle_zip),
                "--outdir",
                str(outdir),
                "--include-repo-snapshot",
                "0",
                "--include-paper-assets",
                "0",
                "--include-verify",
                "0",
                "--include-boltzmann-export",
                "on",
                "--boltzmann-zip",
                "--boltzmann-max-zip-mb",
                "0",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]
            run = self._run(cmd)
            self.assertEqual(run.returncode, 2, msg=(run.stdout or "") + (run.stderr or ""))


if __name__ == "__main__":
    unittest.main()
