import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M45E2JobgenScanExtraArgs(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m45_plan_source"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.9, "Omega_m": 0.301}},
                {"point_id": "p1", "params": {"H0": 67.2, "Omega_m": 0.307}},
                {"point_id": "p2", "params": {"H0": 67.5, "Omega_m": 0.313}},
            ],
        }
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _run_jobgen(self, *, plan: Path, outdir: Path) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_jobgen.py"
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
            "--scan-extra-arg",
            "--model",
            "--scan-extra-arg",
            "lcdm",
            "--scan-extra-arg",
            "--toy",
            "--scan-extra-arg",
            "--drift-precheck",
            "--scan-extra-arg",
            "z2_5_positive",
            "--scan-extra-arg",
            "--integrator",
            "--scan-extra-arg",
            "trap",
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_scan_extra_args_are_wired_into_scripts_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            outdir = td_path / "jobpack"
            self._write_plan(plan)

            proc = self._run_jobgen(plan=plan, outdir=outdir)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            scripts = sorted(outdir.glob("run_slice_*_of_*.sh"))
            self.assertEqual(len(scripts), 2)
            for script in scripts:
                text = script.read_text(encoding="utf-8")
                self.assertIn("--drift-precheck", text)
                self.assertIn("z2_5_positive", text)
                self.assertIn("--integrator", text)
                self.assertIn("trap", text)
                self.assertIn("--model", text)
                self.assertIn("lcdm", text)

            manifest = json.loads((outdir / "jobgen_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest.get("scan_extra_args"),
                ["--model", "lcdm", "--toy", "--drift-precheck", "z2_5_positive", "--integrator", "trap"],
            )

    def test_deterministic_outputs_for_same_scan_extra_args(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            out_a = td_path / "pack_a"
            out_b = td_path / "pack_b"
            self._write_plan(plan)

            proc_a = self._run_jobgen(plan=plan, outdir=out_a)
            proc_b = self._run_jobgen(plan=plan, outdir=out_b)
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            names = sorted(
                [path.name for path in out_a.glob("run_slice_*_of_*.sh")]
                + [
                    "jobgen_manifest.json",
                    "README.md",
                    "plan.json",
                    "merge_shards.sh",
                    "bundle.sh",
                    "verify.sh",
                    "status.sh",
                    "requeue.sh",
                ]
            )
            for name in names:
                self.assertEqual(self._sha256(out_a / name), self._sha256(out_b / name), msg=name)


if __name__ == "__main__":
    unittest.main()
