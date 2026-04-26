import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M39VerifyBundlePlanCoverage(unittest.TestCase):
    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "bundle_plan_sha_m39"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.2, "Omega_m": 0.315}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_results(self, path: Path, *, p0_status: str, p1_status: str, include_p1: bool = True) -> None:
        rows = [
            {
                "plan_point_id": "p0",
                "plan_source_sha256": "bundle_plan_sha_m39",
                "status": str(p0_status),
                "params_hash": "hash0",
                "params": {"H0": 66.8, "Omega_m": 0.300},
            }
        ]
        if include_p1:
            rows.append(
                {
                    "plan_point_id": "p1",
                    "plan_source_sha256": "bundle_plan_sha_m39",
                    "status": str(p1_status),
                    "params_hash": "hash1",
                    "params": {"H0": 67.2, "Omega_m": 0.315},
                }
            )
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _write_manifest(self, bundle_dir: Path, files: list[Path]) -> Path:
        artifacts = []
        for path in sorted(files, key=lambda p: p.name):
            artifacts.append(
                {
                    "path": path.name,
                    "sha256": self._sha256(path),
                    "bytes": int(path.stat().st_size),
                }
            )
        payload = {
            "schema": "phase2_e2_manifest_v1",
            "artifacts": artifacts,
            "inputs": [],
        }
        manifest = bundle_dir / "manifest.json"
        manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest

    def _run_verify(self, bundle_dir: Path, mode: str) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"
        cmd = [
            sys.executable,
            str(script),
            "--bundle",
            str(bundle_dir),
            "--plan-coverage",
            str(mode),
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _write_lineage(self, bundle_dir: Path) -> None:
        script = ROOT / "scripts" / "phase2_lineage_dag.py"
        cmd = [
            sys.executable,
            str(script),
            "--bundle-dir",
            str(bundle_dir),
            "--out",
            str(bundle_dir / "LINEAGE.json"),
            "--format",
            "json",
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

    def test_plan_coverage_modes(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_dir = td_path / "bundle"
            bundle_dir.mkdir(parents=True, exist_ok=True)
            plan = bundle_dir / "refine_plan.json"
            results = bundle_dir / "results.jsonl"
            self._write_plan(plan)

            # Case 1: full coverage with all ok -> ok mode passes.
            self._write_results(results, p0_status="ok", p1_status="ok", include_p1=True)
            self._write_manifest(bundle_dir, [plan, results])
            self._write_lineage(bundle_dir)
            proc_ok = self._run_verify(bundle_dir, "ok")
            self.assertEqual(proc_ok.returncode, 0, msg=(proc_ok.stdout or "") + (proc_ok.stderr or ""))

            # Case 2: missing one point -> complete mode fails.
            self._write_results(results, p0_status="ok", p1_status="ok", include_p1=False)
            self._write_manifest(bundle_dir, [plan, results])
            self._write_lineage(bundle_dir)
            proc_missing = self._run_verify(bundle_dir, "complete")
            self.assertNotEqual(proc_missing.returncode, 0, msg=(proc_missing.stdout or "") + (proc_missing.stderr or ""))

            # Case 3: one point failed -> complete passes, ok fails.
            self._write_results(results, p0_status="ok", p1_status="error", include_p1=True)
            self._write_manifest(bundle_dir, [plan, results])
            self._write_lineage(bundle_dir)
            proc_complete = self._run_verify(bundle_dir, "complete")
            self.assertEqual(proc_complete.returncode, 0, msg=(proc_complete.stdout or "") + (proc_complete.stderr or ""))

            proc_ok_failed = self._run_verify(bundle_dir, "ok")
            self.assertNotEqual(proc_ok_failed.returncode, 0, msg=(proc_ok_failed.stdout or "") + (proc_ok_failed.stderr or ""))


if __name__ == "__main__":
    unittest.main()
