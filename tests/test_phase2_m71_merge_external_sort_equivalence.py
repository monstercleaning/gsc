import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import List, Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M71MergeExternalSortEquivalence(unittest.TestCase):
    def _write_jsonl_with_invalid(self, path: Path, rows: list[dict], *, invalid_tail: bool = False) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.write("{not_json\n")
            if invalid_tail:
                fh.write(" ")

    def _run_merge(
        self,
        *,
        inputs: list[Path],
        out_jsonl: Path,
        external_sort: bool,
        extra: Optional[List[str]] = None,
    ) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        cmd = [sys.executable, str(script), *[str(p) for p in inputs], "--out", str(out_jsonl)]
        if external_sort:
            cmd.extend(["--external-sort", "--chunk-records", "5"])
        if extra:
            cmd.extend(list(extra))
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _build_rows(self) -> list[dict]:
        rows: list[dict] = []
        for i in range(12):
            rows.append(
                {
                    "plan_point_id": f"p{i:02d}",
                    "plan_point_index": i,
                    "plan_source_sha256": "plan_sha_m71",
                    "scan_config_sha256": "cfg_sha_m71",
                    "params_hash": f"h{i:02d}",
                    "status": "ok",
                    "chi2_total": float(100 + i),
                    "params": {"H0": 66.0 + 0.1 * i, "Omega_m": 0.28 + 0.001 * i},
                }
            )
        return rows

    def test_external_sort_matches_in_memory_merge(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            rows = self._build_rows()
            a = tdp / "a.jsonl"
            b = tdp / "b.jsonl"
            c = tdp / "c.jsonl"

            rows_a = [
                dict(rows[0], chi2_total=12.0, status="ok"),
                dict(rows[1], status="error", error="RuntimeError: bad step"),
                dict(rows[2], chi2_total=9.0),
                dict(rows[3], status="skipped_drift_precheck", chi2_total=19.0),
                dict(rows[4], chi2_total=7.0),
                dict(rows[5], status="ok", chi2_total=6.0),
            ]
            rows_b = [
                dict(rows[0], chi2_total=10.0, status="ok"),
                dict(rows[1], status="ok", chi2_total=15.0),
                dict(rows[6], status="error", error="ValueError: unstable"),
                dict(rows[7], chi2_total=8.0),
                dict(rows[8], chi2_total=5.0),
                dict(rows[9], status="skipped_drift_precheck", chi2_total=4.0),
            ]
            rows_c = [
                dict(rows[2], chi2_total=11.0, status="ok"),
                dict(rows[3], status="ok", chi2_total=14.0),
                dict(rows[4], status="error", error="ValueError: retry"),
                dict(rows[10], chi2_total=16.0),
                dict(rows[11], chi2_total=18.0),
                dict(rows[5], status="ok", chi2_total=5.5),
            ]
            rows_b[3].pop("status", None)
            rows_c[3].pop("status", None)

            self._write_jsonl_with_invalid(a, rows_a)
            self._write_jsonl_with_invalid(b, rows_b)
            self._write_jsonl_with_invalid(c, rows_c, invalid_tail=True)

            inmem_out = tdp / "merged_inmem.jsonl"
            ext_out = tdp / "merged_ext.jsonl"
            proc_inmem = self._run_merge(inputs=[a, b, c], out_jsonl=inmem_out, external_sort=False)
            proc_ext = self._run_merge(inputs=[a, b, c], out_jsonl=ext_out, external_sort=True)
            self.assertEqual(proc_inmem.returncode, 0, msg=(proc_inmem.stdout or "") + (proc_inmem.stderr or ""))
            self.assertEqual(proc_ext.returncode, 0, msg=(proc_ext.stdout or "") + (proc_ext.stderr or ""))
            self.assertTrue(inmem_out.is_file())
            self.assertTrue(ext_out.is_file())
            self.assertEqual(inmem_out.read_bytes(), ext_out.read_bytes())

            merged_lines = [line for line in ext_out.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(merged_lines), 12)

    def test_external_sort_enforces_plan_and_scan_guards(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            rows = self._build_rows()
            good = tdp / "good.jsonl"
            bad_plan = tdp / "bad_plan.jsonl"
            bad_cfg = tdp / "bad_cfg.jsonl"
            self._write_jsonl_with_invalid(good, [dict(rows[0], chi2_total=10.0), dict(rows[1], chi2_total=11.0)])

            bad_plan_rows = [dict(rows[2], chi2_total=12.0), dict(rows[3], chi2_total=13.0)]
            bad_plan_rows[0]["plan_source_sha256"] = "other_plan_sha"
            self._write_jsonl_with_invalid(bad_plan, bad_plan_rows)

            bad_cfg_rows = [dict(rows[4], chi2_total=14.0), dict(rows[5], chi2_total=15.0)]
            bad_cfg_rows[1]["scan_config_sha256"] = "other_cfg_sha"
            self._write_jsonl_with_invalid(bad_cfg, bad_cfg_rows)

            out_plan = tdp / "merged_bad_plan.jsonl"
            proc_plan = self._run_merge(inputs=[good, bad_plan], out_jsonl=out_plan, external_sort=True)
            output_plan = (proc_plan.stdout or "") + (proc_plan.stderr or "")
            self.assertEqual(proc_plan.returncode, 2, msg=output_plan)
            self.assertIn("mixed plan_source_sha256", output_plan)
            self.assertFalse(out_plan.exists())

            out_cfg = tdp / "merged_bad_cfg.jsonl"
            proc_cfg = self._run_merge(
                inputs=[good, bad_cfg],
                out_jsonl=out_cfg,
                external_sort=True,
                extra=["--scan-config-sha-policy", "require"],
            )
            output_cfg = (proc_cfg.stdout or "") + (proc_cfg.stderr or "")
            self.assertEqual(proc_cfg.returncode, 2, msg=output_cfg)
            self.assertIn("scan_config_sha256", output_cfg)
            self.assertFalse(out_cfg.exists())


if __name__ == "__main__":
    unittest.main()
