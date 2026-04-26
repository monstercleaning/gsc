import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M36E2ScanPlanSliceMergeDeterminism(unittest.TestCase):
    def _write_plan_json(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m36toy"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.280}},
                {"point_id": "p1", "params": {"H0": 67.0, "Omega_m": 0.290}},
                {"point_id": "p2", "params": {"H0": 67.2, "Omega_m": 0.300}},
                {"point_id": "p3", "params": {"H0": 67.4, "Omega_m": 0.310}},
                {"point_id": "p4", "params": {"H0": 67.6, "Omega_m": 0.320}},
                {"point_id": "p5", "params": {"H0": 67.8, "Omega_m": 0.330}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_scan(self, *, plan: Path, out_dir: Path, plan_slice: Optional[str] = None, jobs: int = 1) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan),
            "--jobs",
            str(jobs),
            "--out-dir",
            str(out_dir),
        ]
        if plan_slice is not None:
            cmd.extend(["--plan-slice", str(plan_slice)])
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _run_merge(self, *, out_jsonl: Path, inputs: list[Path], report_json: Optional[Path] = None) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        cmd = [sys.executable, str(script)] + [str(p) for p in inputs] + ["--out", str(out_jsonl)]
        if report_json is not None:
            cmd.extend(["--report-out", str(report_json)])
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_jsonl(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
        return rows

    def _normalized_records(self, rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        for row in rows:
            item = dict(row)
            item.pop("plan_slice_i", None)
            item.pop("plan_slice_n", None)
            out.append(item)
        out.sort(key=lambda r: str(r.get("params_hash", "")))
        return out

    def test_plan_slice_merge_matches_full_and_is_order_independent(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan_json = td_path / "plan.json"
            self._write_plan_json(plan_json)

            full_dir = td_path / "full"
            s0_dir = td_path / "s0"
            s1_dir = td_path / "s1"
            merged_a = td_path / "merged_a.jsonl"
            merged_b = td_path / "merged_b.jsonl"
            merge_report = td_path / "merge_report.json"

            proc_full = self._run_scan(plan=plan_json, out_dir=full_dir, jobs=1)
            out_full = (proc_full.stdout or "") + (proc_full.stderr or "")
            self.assertEqual(proc_full.returncode, 0, msg=out_full)

            proc_s0 = self._run_scan(plan=plan_json, out_dir=s0_dir, plan_slice="0/2", jobs=2)
            out_s0 = (proc_s0.stdout or "") + (proc_s0.stderr or "")
            self.assertEqual(proc_s0.returncode, 0, msg=out_s0)

            proc_s1 = self._run_scan(plan=plan_json, out_dir=s1_dir, plan_slice="1/2", jobs=2)
            out_s1 = (proc_s1.stdout or "") + (proc_s1.stderr or "")
            self.assertEqual(proc_s1.returncode, 0, msg=out_s1)

            s0_jsonl = s0_dir / "e2_scan_points.jsonl"
            s1_jsonl = s1_dir / "e2_scan_points.jsonl"
            full_jsonl = full_dir / "e2_scan_points.jsonl"
            self.assertTrue(full_jsonl.is_file())
            self.assertTrue(s0_jsonl.is_file())
            self.assertTrue(s1_jsonl.is_file())

            proc_merge_a = self._run_merge(out_jsonl=merged_a, inputs=[s0_jsonl, s1_jsonl], report_json=merge_report)
            out_merge_a = (proc_merge_a.stdout or "") + (proc_merge_a.stderr or "")
            self.assertEqual(proc_merge_a.returncode, 0, msg=out_merge_a)
            self.assertTrue(merged_a.is_file())
            self.assertTrue(merge_report.is_file())

            proc_merge_b = self._run_merge(out_jsonl=merged_b, inputs=[s1_jsonl, s0_jsonl])
            out_merge_b = (proc_merge_b.stdout or "") + (proc_merge_b.stderr or "")
            self.assertEqual(proc_merge_b.returncode, 0, msg=out_merge_b)
            self.assertTrue(merged_b.is_file())

            self.assertEqual(merged_a.read_bytes(), merged_b.read_bytes())

            full_rows = self._load_jsonl(full_jsonl)
            merged_rows = self._load_jsonl(merged_a)
            self.assertEqual(self._normalized_records(full_rows), self._normalized_records(merged_rows))

            report = json.loads(merge_report.read_text(encoding="utf-8"))
            self.assertEqual(report.get("n_inputs"), 2)
            self.assertEqual(report.get("policy_prefer"), "ok_then_lowest_chi2")
            self.assertTrue(isinstance(report.get("sha256_out"), str) and report.get("sha256_out"))


if __name__ == "__main__":
    unittest.main()
