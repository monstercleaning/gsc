import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import List, Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M60MergePlanSourceShaGuards(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run_merge(
        self,
        *,
        inputs: List[Path],
        out_jsonl: Path,
        extra: Optional[List[str]] = None,
    ) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        cmd = [sys.executable, str(script), *[str(p) for p in inputs], "--out", str(out_jsonl)]
        if extra:
            cmd.extend(extra)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_consistent_policy_mismatch_fails_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            a = tdp / "a.jsonl"
            b = tdp / "b.jsonl"
            out = tdp / "merged.jsonl"

            self._write_jsonl(
                a,
                [
                    {
                        "params_hash": "h1",
                        "status": "ok",
                        "chi2_total": 3.0,
                        "plan_source_sha256": "aaa",
                    }
                ],
            )
            self._write_jsonl(
                b,
                [
                    {
                        "params_hash": "h2",
                        "status": "ok",
                        "chi2_total": 2.0,
                        "plan_source_sha256": "bbb",
                    }
                ],
            )

            proc = self._run_merge(inputs=[a, b], out_jsonl=out)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("mixed plan_source_sha256", output)
            self.assertFalse(out.exists())

    def test_ignore_policy_allows_mixed_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            a = tdp / "a.jsonl"
            b = tdp / "b.jsonl"
            out = tdp / "merged.jsonl"

            self._write_jsonl(
                a,
                [
                    {
                        "params_hash": "h1",
                        "status": "ok",
                        "chi2_total": 3.0,
                        "plan_source_sha256": "aaa",
                    }
                ],
            )
            self._write_jsonl(
                b,
                [
                    {
                        "params_hash": "h2",
                        "status": "ok",
                        "chi2_total": 2.0,
                        "plan_source_sha256": "bbb",
                    }
                ],
            )

            proc = self._run_merge(
                inputs=[a, b],
                out_jsonl=out,
                extra=["--plan-source-policy", "ignore"],
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue(out.is_file())

    def test_match_plan_policy_mismatch_fails_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            a = tdp / "a.jsonl"
            b = tdp / "b.jsonl"
            out = tdp / "merged.jsonl"
            plan = tdp / "plan.json"
            plan.write_text('{"plan_version":"phase2_e2_refine_plan_v1","points":[]}', encoding="utf-8")

            self._write_jsonl(
                a,
                [
                    {
                        "params_hash": "h1",
                        "status": "ok",
                        "chi2_total": 3.0,
                        "plan_source_sha256": "not_plan_sha",
                    }
                ],
            )
            self._write_jsonl(
                b,
                [
                    {
                        "params_hash": "h2",
                        "status": "ok",
                        "chi2_total": 2.0,
                        "plan_source_sha256": "not_plan_sha",
                    }
                ],
            )

            proc = self._run_merge(
                inputs=[a, b],
                out_jsonl=out,
                extra=["--plan", str(plan), "--plan-source-policy", "match_plan"],
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("does not match --plan SHA256", output)
            self.assertFalse(out.exists())

    def test_match_plan_policy_missing_field_fails_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            a = tdp / "a.jsonl"
            b = tdp / "b.jsonl"
            out = tdp / "merged.jsonl"
            plan = tdp / "plan.json"
            plan.write_text('{"plan_version":"phase2_e2_refine_plan_v1","points":[]}', encoding="utf-8")

            self._write_jsonl(a, [{"params_hash": "h1", "status": "ok", "chi2_total": 3.0}])
            self._write_jsonl(b, [{"params_hash": "h2", "status": "ok", "chi2_total": 2.0}])

            proc = self._run_merge(
                inputs=[a, b],
                out_jsonl=out,
                extra=["--plan", str(plan), "--plan-source-policy", "match_plan"],
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("no non-empty plan_source_sha256", output)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
