import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M40E2JobgenClusterPack(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m40_plan_source"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.1, "Omega_m": 0.305}},
                {"point_id": "p2", "params": {"H0": 67.4, "Omega_m": 0.310}},
                {"point_id": "p3", "params": {"H0": 67.7, "Omega_m": 0.315}},
                {"point_id": "p4", "params": {"H0": 68.0, "Omega_m": 0.320}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_jobgen(
        self,
        *,
        plan: Path,
        outdir: Path,
        slices: int,
        scheduler: str,
        created_utc: str,
        paper_assets: str = "none",
    ) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_jobgen.py"
        cmd = [
            sys.executable,
            str(script),
            "--plan",
            str(plan),
            "--outdir",
            str(outdir),
            "--slices",
            str(int(slices)),
            "--scheduler",
            str(scheduler),
            "--created-utc",
            str(created_utc),
            "--paper-assets",
            str(paper_assets),
            "--",
            "--model",
            "lcdm",
            "--toy",
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_jobgen_emits_expected_tree_bash(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan_input.json"
            outdir = td_path / "pack_bash"
            self._write_plan(plan)

            proc = self._run_jobgen(
                plan=plan,
                outdir=outdir,
                slices=3,
                scheduler="bash",
                created_utc="2000-01-01T00:00:00Z",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            expected = [
                outdir / "plan.json",
                outdir / "jobgen_manifest.json",
                outdir / "README.md",
                outdir / "merge_shards.sh",
                outdir / "bundle.sh",
                outdir / "verify.sh",
                outdir / "status.sh",
                outdir / "watch.sh",
                outdir / "requeue.sh",
                outdir / "rsd_overlay.sh",
                outdir / "boltzmann_export.sh",
                outdir / "boltzmann_run_class.sh",
                outdir / "boltzmann_run_camb.sh",
                outdir / "boltzmann_results.sh",
            ]
            for path in expected:
                self.assertTrue(path.is_file(), msg=str(path))
                self.assertGreater(path.stat().st_size, 0, msg=str(path))

            self.assertTrue((outdir / "shards").is_dir())

            run_scripts = sorted(outdir.glob("run_slice_*_of_*.sh"))
            self.assertEqual(len(run_scripts), 3)
            for idx, script in enumerate(run_scripts):
                text = script.read_text(encoding="utf-8")
                self.assertIn("--plan-slice", text)
                self.assertIn(f"{idx}/3", text)
                self.assertIn('PLAN="$JOB_ROOT/plan.json"', text)
                self.assertIn('shards/slice_', text)

            status_text = (outdir / "status.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_e2_live_status.py", status_text)
            self.assertIn("--mode", status_text)
            self.assertIn("--tail-safe", status_text)
            self.assertIn("--include-slice-summary", status_text)
            self.assertIn("RSD overlay", status_text)

            watch_text = (outdir / "watch.sh").read_text(encoding="utf-8")
            self.assertIn("status.sh", watch_text)
            self.assertIn("INTERVAL", watch_text)

            requeue_text = (outdir / "requeue.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_e2_requeue_plan.py", requeue_text)
            self.assertIn("--select", requeue_text)

            rsd_overlay_text = (outdir / "rsd_overlay.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_e2_pareto_report.py", rsd_overlay_text)
            self.assertIn("--rsd-overlay", rsd_overlay_text)
            self.assertIn("--rsd-data", rsd_overlay_text)

            boltzmann_export_text = (outdir / "boltzmann_export.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_pt_boltzmann_export_pack.py", boltzmann_export_text)
            self.assertIn("GSC_BOLTZMANN_OUTDIR", boltzmann_export_text)
            self.assertIn("GSC_RANK_BY", boltzmann_export_text)
            boltzmann_results_text = (outdir / "boltzmann_results.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_pt_boltzmann_results_pack.py", boltzmann_results_text)
            self.assertIn("GSC_BOLTZMANN_RESULTS_RUN_DIR", boltzmann_results_text)
            self.assertIn("GSC_BOLTZMANN_RESULTS_REQUIRE", boltzmann_results_text)
            boltzmann_run_class_text = (outdir / "boltzmann_run_class.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_pt_boltzmann_run_harness.py", boltzmann_run_class_text)
            self.assertIn("GSC_CLASS_BIN", boltzmann_run_class_text)
            self.assertIn("GSC_BOLTZMANN_RUNNER", boltzmann_run_class_text)
            boltzmann_run_camb_text = (outdir / "boltzmann_run_camb.sh").read_text(encoding="utf-8")
            self.assertIn("phase2_pt_boltzmann_run_harness.py", boltzmann_run_camb_text)
            self.assertIn("GSC_CAMB_BIN", boltzmann_run_camb_text)

            readme_text = (outdir / "README.md").read_text(encoding="utf-8")
            merge_text = (outdir / "merge_shards.sh").read_text(encoding="utf-8")
            bundle_text = (outdir / "bundle.sh").read_text(encoding="utf-8")
            status_text = (outdir / "status.sh").read_text(encoding="utf-8")
            requeue_text = (outdir / "requeue.sh").read_text(encoding="utf-8")
            self.assertIn("## Monitoring progress (live)", readme_text)
            self.assertIn("--scan-extra-arg --rsd-overlay", readme_text)
            self.assertIn("--rsd-transfer-model", readme_text)
            self.assertIn("--rsd-ns", readme_text)
            self.assertIn("--rsd-k-pivot", readme_text)
            self.assertIn("Joint objective (CMB+RSD)", readme_text)
            self.assertIn("--chi2-objective", readme_text)
            self.assertIn("--rsd-chi2-field", readme_text)
            self.assertIn("--rsd-chi2-weight", readme_text)
            self.assertIn("./status.sh", readme_text)
            self.assertIn("./watch.sh", readme_text)
            self.assertIn("MERGED_JSONL=", readme_text)
            self.assertIn("MERGED_JSONL=merged.jsonl ./merge_shards.sh", readme_text)
            self.assertIn("## Merging large shards (memory-safe)", readme_text)
            self.assertIn("GSC_MERGE_CHUNK_RECORDS", readme_text)
            self.assertIn("GSC_MERGE_KEEP_TMP", readme_text)
            self.assertIn("## Requeue / rerun unresolved points", readme_text)
            self.assertIn("./requeue.sh", readme_text)
            self.assertIn("## Structure-growth sanity check (RSD fσ8 overlay)", readme_text)
            self.assertIn("./rsd_overlay.sh", readme_text)
            self.assertIn("## Boltzmann export (perturbations)", readme_text)
            self.assertIn("./boltzmann_export.sh", readme_text)
            self.assertIn("## Boltzmann run harness (external execution)", readme_text)
            self.assertIn("./boltzmann_run_class.sh", readme_text)
            self.assertIn("./boltzmann_run_camb.sh", readme_text)
            self.assertIn("## Boltzmann results (perturbations)", readme_text)
            self.assertIn("./boltzmann_results.sh", readme_text)
            self.assertIn("## Plan integrity guardrails", readme_text)
            self.assertIn("plan-source", readme_text)
            self.assertIn("## Provenance / scan_config_sha256", readme_text)
            self.assertIn("MIXED_SCAN_CONFIG_SHA256", readme_text)
            self.assertIn("--external-sort", merge_text)
            self.assertIn("--chunk-records", merge_text)
            self.assertIn("GSC_MERGE_CHUNK_RECORDS", merge_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl}"', merge_text)
            self.assertIn("$MERGED_PATH", merge_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl}"', bundle_text)
            self.assertIn("$MERGED_PATH", bundle_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl}"', status_text)
            self.assertIn("$MERGED_PATH", status_text)
            self.assertIn('MERGED_JSONL="${MERGED_JSONL:-merged.jsonl}"', requeue_text)
            self.assertIn("$MERGED_PATH", requeue_text)

    def test_jobgen_emits_expected_tree_slurm_array(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan_input.json"
            outdir = td_path / "pack_slurm"
            self._write_plan(plan)

            proc = self._run_jobgen(
                plan=plan,
                outdir=outdir,
                slices=3,
                scheduler="slurm_array",
                created_utc="2000-01-01T00:00:00Z",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            sbatch = outdir / "slurm_array.sbatch"
            self.assertTrue(sbatch.is_file())
            text = sbatch.read_text(encoding="utf-8")
            self.assertIn("#SBATCH --array=0-2", text)
            self.assertIn("SLURM_ARRAY_TASK_ID", text)
            self.assertIn('--plan-slice" "${i}/${N}"', text)

    def test_jobgen_determinism_with_fixed_created_utc(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan_input.json"
            out_a = td_path / "pack_a"
            out_b = td_path / "pack_b"
            self._write_plan(plan)

            proc_a = self._run_jobgen(
                plan=plan,
                outdir=out_a,
                slices=4,
                scheduler="bash",
                created_utc="2000-01-01T00:00:00Z",
            )
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))

            proc_b = self._run_jobgen(
                plan=plan,
                outdir=out_b,
                slices=4,
                scheduler="bash",
                created_utc="2000-01-01T00:00:00Z",
            )
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            names = sorted(
                [p.name for p in out_a.glob("run_slice_*_of_*.sh")]
                + [
                    "merge_shards.sh",
                    "bundle.sh",
                    "verify.sh",
                    "status.sh",
                    "watch.sh",
                    "requeue.sh",
                    "rsd_overlay.sh",
                    "boltzmann_export.sh",
                    "boltzmann_run_class.sh",
                    "boltzmann_run_camb.sh",
                    "boltzmann_results.sh",
                    "plan.json",
                ]
            )
            for name in names:
                self.assertEqual(
                    self._sha256(out_a / name),
                    self._sha256(out_b / name),
                    msg=name,
                )

    def test_jobgen_bash_slices_run_end_to_end_toy_small(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan_input.json"
            outdir = td_path / "pack_run"
            self._write_plan(plan)

            proc = self._run_jobgen(
                plan=plan,
                outdir=outdir,
                slices=2,
                scheduler="bash",
                created_utc="2000-01-01T00:00:00Z",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            env = os.environ.copy()
            env["GSC_REPO_ROOT"] = str(ROOT)
            env["GSC_PYTHON"] = sys.executable

            for script in sorted(outdir.glob("run_slice_*_of_*.sh")):
                proc_slice = subprocess.run(
                    ["bash", str(script)],
                    cwd=str(outdir),
                    text=True,
                    capture_output=True,
                    env=env,
                )
                self.assertEqual(
                    proc_slice.returncode,
                    0,
                    msg=(proc_slice.stdout or "") + (proc_slice.stderr or ""),
                )

            proc_merge = subprocess.run(
                ["bash", str(outdir / "merge_shards.sh")],
                cwd=str(outdir),
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(proc_merge.returncode, 0, msg=(proc_merge.stdout or "") + (proc_merge.stderr or ""))
            self.assertTrue((outdir / "merged.jsonl").is_file())

            proc_bundle = subprocess.run(
                ["bash", str(outdir / "bundle.sh")],
                cwd=str(outdir),
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(proc_bundle.returncode, 0, msg=(proc_bundle.stdout or "") + (proc_bundle.stderr or ""))
            self.assertTrue((outdir / "bundle_dir").is_dir())

            proc_verify = subprocess.run(
                ["bash", str(outdir / "verify.sh")],
                cwd=str(outdir),
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(proc_verify.returncode, 0, msg=(proc_verify.stdout or "") + (proc_verify.stderr or ""))
            self.assertTrue((outdir / "bundle_verify.json").is_file())

    def test_jobgen_wires_paper_assets_into_bundle_and_verify_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan_input.json"
            outdir = td_path / "pack_paper_assets"
            self._write_plan(plan)

            proc = self._run_jobgen(
                plan=plan,
                outdir=outdir,
                slices=2,
                scheduler="bash",
                created_utc="2000-01-01T00:00:00Z",
                paper_assets="snippets",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            bundle_text = (outdir / "bundle.sh").read_text(encoding="utf-8")
            verify_text = (outdir / "verify.sh").read_text(encoding="utf-8")
            self.assertIn("--paper-assets", bundle_text)
            self.assertIn("snippets", bundle_text)
            self.assertIn("--paper-assets", verify_text)
            self.assertIn("require", verify_text)
            self.assertIn("--require-plan-source", verify_text)
            self.assertIn("--require-scan-config-sha", verify_text)

            merge_text = (outdir / "merge_shards.sh").read_text(encoding="utf-8")
            self.assertIn("--plan", merge_text)
            self.assertIn("plan.json", merge_text)
            self.assertIn("--plan-source-policy", merge_text)
            self.assertIn("--scan-config-sha-policy", merge_text)
            self.assertIn("--external-sort", merge_text)
            self.assertIn("GSC_MERGE_CHUNK_RECORDS", merge_text)


if __name__ == "__main__":
    unittest.main()
