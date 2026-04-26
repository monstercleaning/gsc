import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M72E2JobgenGzipShardsPack(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m72_jobgen_gzip_plan_source"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.9, "Omega_m": 0.301}},
                {"point_id": "p1", "params": {"H0": 67.3, "Omega_m": 0.307}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_jobgen_emits_gzip_shard_wiring_when_enabled(self) -> None:
        script = ROOT / "scripts" / "phase2_e2_jobgen.py"
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            plan = tdp / "plan.json"
            outdir = tdp / "pack_gzip"
            self._write_plan(plan)

            cmd = [
                sys.executable,
                str(script),
                "--plan",
                str(plan),
                "--outdir",
                str(outdir),
                "--slices",
                "2",
                "--scheduler",
                "bash",
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--shards-compress",
                "gzip",
                "--",
                "--model",
                "lcdm",
                "--toy",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            run_scripts = sorted(outdir.glob("run_slice_*_of_*.sh"))
            self.assertEqual(len(run_scripts), 2)
            for script_path in run_scripts:
                text = script_path.read_text(encoding="utf-8")
                self.assertIn("e2_scan_points.jsonl.gz", text)
                self.assertIn("--points-jsonl-name", text)

            merge_text = (outdir / "merge_shards.sh").read_text(encoding="utf-8")
            self.assertIn("e2_scan_points.jsonl.gz", merge_text)
            self.assertIn("--external-sort", merge_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl.gz}"', merge_text)
            self.assertIn("$MERGED_PATH", merge_text)

            boltzmann_export_text = (outdir / "boltzmann_export.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_pt_boltzmann_export_pack.py", boltzmann_export_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl.gz}"', boltzmann_export_text)
            boltzmann_results_text = (outdir / "boltzmann_results.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_pt_boltzmann_results_pack.py", boltzmann_results_text)
            self.assertIn("GSC_BOLTZMANN_RESULTS_RUN_DIR", boltzmann_results_text)

            bundle_text = (outdir / "bundle.sh").read_text(encoding="utf-8")
            status_text = (outdir / "status.sh").read_text(encoding="utf-8")
            requeue_text = (outdir / "requeue.sh").read_text(encoding="utf-8")
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl.gz}"', bundle_text)
            self.assertIn("$MERGED_PATH", bundle_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl.gz}"', status_text)
            self.assertIn("$MERGED_PATH", status_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl.gz}"', requeue_text)
            self.assertIn("$MERGED_PATH", requeue_text)

            readme_text = (outdir / "README.md").read_text(encoding="utf-8")
            self.assertIn("## Compressed shards (gzip)", readme_text)
            self.assertIn("--shards-compress gzip", readme_text)
            self.assertIn("MERGED_JSONL=merged.jsonl ./merge_shards.sh", readme_text)
            self.assertIn("merged output defaults to `merged.jsonl.gz`", readme_text)
            self.assertIn("## Boltzmann export (perturbations)", readme_text)
            self.assertIn("## Boltzmann results (perturbations)", readme_text)

            manifest = json.loads((outdir / "jobgen_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("shards_compress"), "gzip")
            self.assertEqual(manifest.get("shard_points_filename"), "e2_scan_points.jsonl.gz")
            self.assertEqual(manifest.get("merged_jsonl_default"), "merged.jsonl.gz")


if __name__ == "__main__":
    unittest.main()
