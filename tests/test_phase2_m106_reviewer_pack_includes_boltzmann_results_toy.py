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


class TestPhase2M106ReviewerPackIncludesBoltzmannResultsToy(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _make_bundle_zip(self, td_path: Path) -> Path:
        shard = td_path / "shard.jsonl"
        self._write_jsonl(
            shard,
            [
                {"type": "header", "schema": "gsc.phase2.e2.scan.v1"},
                {
                    "params_hash": "m106_hash_best",
                    "plan_point_id": "p0",
                    "status": "ok",
                    "chi2_total": 3.2,
                    "params": {
                        "H0": 67.7,
                        "omega_b": 0.049,
                        "omega_m": 0.31,
                        "As": 2.1e-9,
                        "ns": 0.965,
                        "k_pivot_mpc": 0.05,
                    },
                },
            ],
        )

        bundle_dir = td_path / "bundle_dir"
        proc = self._run(
            [
                sys.executable,
                str(BUNDLE_SCRIPT),
                "--in",
                str(shard),
                "--outdir",
                str(bundle_dir),
                "--steps",
                "merge,pareto,manifest,meta",
            ]
        )
        self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

        bundle_zip = td_path / "bundle.zip"
        with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(bundle_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(bundle_dir).as_posix()
                zf.write(path, arcname=str(PurePosixPath("bundle") / rel))
        return bundle_zip

    def _make_run_dir(self, td_path: Path) -> Path:
        run_dir = td_path / "external_run"
        run_dir.mkdir(parents=True, exist_ok=True)
        tt = """# ell C_ell\n2 100\n50 900\n100 1300\n220 1900\n500 650\n1000 280\n"""
        (run_dir / "toy_tt.dat").write_text(tt, encoding="utf-8")
        (run_dir / "class_run.log").write_text("CLASS v3 synthetic\n", encoding="utf-8")
        return run_dir

    def test_reviewer_pack_includes_boltzmann_results_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_zip = self._make_bundle_zip(td_path)
            run_dir = self._make_run_dir(td_path)

            outdir = td_path / "pack_out"
            zip_a = td_path / "pack_a.zip"
            zip_b = td_path / "pack_b.zip"

            cmd = [
                sys.executable,
                str(REVIEWER_PACK_SCRIPT),
                "--bundle",
                str(bundle_zip),
                "--outdir",
                str(outdir),
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
                "--include-boltzmann-results",
                "on",
                "--boltzmann-run-dir",
                str(run_dir),
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--format",
                "json",
            ]
            run_a = self._run(cmd)
            self.assertEqual(run_a.returncode, 0, msg=(run_a.stdout or "") + (run_a.stderr or ""))
            self.assertTrue(zip_a.is_file())

            cmd_b = list(cmd)
            shutil.rmtree(outdir)
            cmd_b[cmd_b.index(str(zip_a))] = str(zip_b)
            run_b = self._run(cmd_b)
            self.assertEqual(run_b.returncode, 0, msg=(run_b.stdout or "") + (run_b.stderr or ""))
            self.assertTrue(zip_b.is_file())

            self.assertEqual(_sha256_path(zip_a), _sha256_path(zip_b))

            with zipfile.ZipFile(zip_a, "r") as zf:
                names = sorted(zf.namelist())
                self.assertIn("reviewer_pack/boltzmann_results/RESULTS_SUMMARY.json", names)
                self.assertIn("reviewer_pack/boltzmann_results/README.md", names)
                self.assertIn("reviewer_pack/boltzmann_results/export_pack/CANDIDATE_RECORD.json", names)
                guide = zf.read("reviewer_pack/REVIEWER_GUIDE.md").decode("utf-8")
                self.assertIn("## Boltzmann results (perturbations)", guide)


if __name__ == "__main__":
    unittest.main()
