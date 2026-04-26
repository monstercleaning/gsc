import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M37E2BundleEndToEndToy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[str]) -> None:
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _run_bundle(self, *, inputs: list[Path], outdir: Path, steps: str, strict: bool = False, emit_refine_plan: bool = False) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_bundle.py"
        cmd = [
            sys.executable,
            str(script),
            "--outdir",
            str(outdir),
            "--steps",
            str(steps),
        ]
        for inp in inputs:
            cmd.extend(["--in", str(inp)])
        if strict:
            cmd.append("--strict")
        if emit_refine_plan:
            cmd.append("--emit-refine-plan")
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_bundle_merge_reports_manifest_deterministic(self):
        script = ROOT / "scripts" / "phase2_e2_bundle.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a = td_path / "shard_a.jsonl"
            shard_b = td_path / "shard_b.jsonl"

            self._write_jsonl(
                shard_a,
                [
                    json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                    json.dumps(
                        {
                            "params_hash": "hash_a",
                            "status": "ok",
                            "model": "lcdm",
                            "chi2_total": 4.0,
                            "chi2_cmb": 2.0,
                            "drift": {"min_z_dot": 1.0e-12},
                            "microphysics_plausible_ok": True,
                            "params": {"H0": 67.0, "Omega_m": 0.30},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_b",
                            "status": "ok",
                            "model": "lcdm",
                            "chi2_total": 5.0,
                            "chi2_cmb": 3.0,
                            "drift": {"min_z_dot": 5.0e-13},
                            "microphysics_plausible_ok": True,
                            "params": {"H0": 68.0, "Omega_m": 0.31},
                        }
                    ),
                ],
            )

            self._write_jsonl(
                shard_b,
                [
                    json.dumps(
                        {
                            "params_hash": "hash_b",
                            "status": "ok",
                            "model": "lcdm",
                            "chi2_total": 4.5,
                            "chi2_cmb": 1.5,
                            "drift": {"min_z_dot": 7.0e-13},
                            "microphysics_plausible_ok": True,
                            "params": {"H0": 68.0, "Omega_m": 0.31},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_c",
                            "status": "error",
                            "model": "lcdm",
                            "chi2_total": 99.0,
                            "chi2_cmb": 88.0,
                            "params": {"H0": 69.0, "Omega_m": 0.32},
                        }
                    ),
                ],
            )

            out1 = td_path / "bundle_a"
            out2 = td_path / "bundle_b"

            proc1 = self._run_bundle(
                inputs=[shard_a, shard_b],
                outdir=out1,
                steps="merge,pareto,meta,manifest",
                emit_refine_plan=False,
            )
            output1 = (proc1.stdout or "") + (proc1.stderr or "")
            self.assertEqual(proc1.returncode, 0, msg=output1)

            expected_paths = [
                out1 / "merged.jsonl",
                out1 / "pareto_summary.json",
                out1 / "pareto_frontier.csv",
                out1 / "pareto_top_positive.csv",
                out1 / "pareto_report.md",
                out1 / "bundle_meta.json",
                out1 / "manifest.json",
            ]
            for path in expected_paths:
                self.assertTrue(path.is_file(), msg=str(path))
                self.assertGreater(path.stat().st_size, 0, msg=str(path))

            meta = json.loads((out1 / "bundle_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta.get("schema"), "phase2_e2_bundle_v1")
            self.assertIn("inputs", meta)
            self.assertIn("outputs", meta)
            self.assertIn("steps", meta)

            manifest = json.loads((out1 / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("schema"), "phase2_e2_manifest_v1")

            proc2 = self._run_bundle(
                inputs=[shard_a, shard_b],
                outdir=out2,
                steps="merge,pareto,meta,manifest",
                emit_refine_plan=False,
            )
            output2 = (proc2.stdout or "") + (proc2.stderr or "")
            self.assertEqual(proc2.returncode, 0, msg=output2)

            compare_files = [
                "merged.jsonl",
                "pareto_frontier.csv",
                "bundle_meta.json",
                "manifest.json",
            ]
            for name in compare_files:
                self.assertEqual(self._sha256(out1 / name), self._sha256(out2 / name), msg=name)

    def test_non_strict_skips_failed_step_but_strict_fails(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            sparse = td_path / "sparse.jsonl"
            self._write_jsonl(
                sparse,
                [
                    json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                    json.dumps({"note": "legacy-non-data-record"}),
                ],
            )

            out_non_strict = td_path / "out_non_strict"
            proc_ok = self._run_bundle(
                inputs=[sparse],
                outdir=out_non_strict,
                steps="merge,sensitivity,meta",
                strict=False,
            )
            out_ok = (proc_ok.stdout or "") + (proc_ok.stderr or "")
            self.assertEqual(proc_ok.returncode, 0, msg=out_ok)
            meta = json.loads((out_non_strict / "bundle_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta.get("steps", {}).get("sensitivity", {}).get("status"), "skipped")

            out_strict = td_path / "out_strict"
            proc_fail = self._run_bundle(
                inputs=[sparse],
                outdir=out_strict,
                steps="merge,sensitivity,meta",
                strict=True,
            )
            out_fail = (proc_fail.stdout or "") + (proc_fail.stderr or "")
            self.assertNotEqual(proc_fail.returncode, 0)
            self.assertIn("Step 'sensitivity' failed", out_fail)


if __name__ == "__main__":
    unittest.main()
