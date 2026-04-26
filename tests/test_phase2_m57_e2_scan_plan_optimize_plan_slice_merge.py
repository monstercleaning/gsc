import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M57ScanPlanOptimizePlanSliceMerge(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m57planseedsha"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.1, "Omega_m": 0.320}},
                {"point_id": "p2", "params": {"H0": 68.0, "Omega_m": 0.340}},
                {"point_id": "p3", "params": {"H0": 69.0, "Omega_m": 0.280}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_scan_slice(self, *, plan: Path, out_dir: Path, slice_spec: str) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan),
            "--plan-slice",
            str(slice_spec),
            "--optimize",
            "nelder_mead",
            "--opt-objective-key",
            "chi2_total",
            "--opt-max-eval",
            "50",
            "--opt-step-frac",
            "0.1",
            "--jobs",
            "2",
            "--out-dir",
            str(out_dir),
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _run_merge(self, *, shards: list[Path], out_jsonl: Path) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        cmd = [
            sys.executable,
            str(script),
            *[str(p) for p in shards],
            "--out",
            str(out_jsonl),
            "--dedupe-key",
            "auto",
            "--canonicalize",
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _run_coverage(self, *, plan: Path, merged: Path) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_plan_coverage.py"
        cmd = [
            sys.executable,
            str(script),
            "--plan",
            str(plan),
            "--jsonl",
            str(merged),
            "--strict",
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_jsonl(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
        return rows

    def _run_pipeline(self, *, run_root: Path) -> Path:
        run_root.mkdir(parents=True, exist_ok=True)
        plan = run_root / "plan.json"
        self._write_plan(plan)

        s0_dir = run_root / "s0"
        s1_dir = run_root / "s1"
        merged = run_root / "merged.jsonl"

        proc_s0 = self._run_scan_slice(plan=plan, out_dir=s0_dir, slice_spec="0/2")
        out_s0 = (proc_s0.stdout or "") + (proc_s0.stderr or "")
        self.assertEqual(proc_s0.returncode, 0, msg=out_s0)

        proc_s1 = self._run_scan_slice(plan=plan, out_dir=s1_dir, slice_spec="1/2")
        out_s1 = (proc_s1.stdout or "") + (proc_s1.stderr or "")
        self.assertEqual(proc_s1.returncode, 0, msg=out_s1)

        shard0 = s0_dir / "e2_scan_points.jsonl"
        shard1 = s1_dir / "e2_scan_points.jsonl"
        self.assertTrue(shard0.is_file())
        self.assertTrue(shard1.is_file())

        proc_merge = self._run_merge(shards=[shard0, shard1], out_jsonl=merged)
        out_merge = (proc_merge.stdout or "") + (proc_merge.stderr or "")
        self.assertEqual(proc_merge.returncode, 0, msg=out_merge)
        self.assertTrue(merged.is_file())

        proc_cov = self._run_coverage(plan=plan, merged=merged)
        out_cov = (proc_cov.stdout or "") + (proc_cov.stderr or "")
        self.assertEqual(proc_cov.returncode, 0, msg=out_cov)
        coverage = json.loads((proc_cov.stdout or "").strip())
        self.assertEqual(int(coverage["counts"]["n_missing"]), 0)
        self.assertEqual(int(coverage["counts"]["n_failed"]), 0)

        rows = self._load_jsonl(merged)
        self.assertEqual(len(rows), 4)
        point_ids = [str(row.get("plan_point_id")) for row in rows]
        self.assertEqual(sorted(point_ids), ["p0", "p1", "p2", "p3"])
        for row in rows:
            self.assertTrue(isinstance(row.get("plan_point_id"), str) and row.get("plan_point_id"))
            self.assertTrue(isinstance(row.get("plan_source_sha256"), str) and row.get("plan_source_sha256"))
            self.assertIn("plan_point_index", row)
            refine_meta = row.get("refine_meta") or {}
            self.assertEqual(refine_meta.get("method"), "nelder_mead")
            self.assertEqual(refine_meta.get("objective_key"), "chi2_total")
            self.assertIn("optimize_start_params", row)

        return merged

    def test_plan_slice_optimize_merge_coverage_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            merged_a = self._run_pipeline(run_root=td_path / "run_a")
            merged_b = self._run_pipeline(run_root=td_path / "run_b")
            self.assertEqual(merged_a.read_bytes(), merged_b.read_bytes())


if __name__ == "__main__":
    unittest.main()
