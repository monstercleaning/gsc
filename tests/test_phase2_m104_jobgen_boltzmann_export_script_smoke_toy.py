import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JOBGEN_SCRIPT = ROOT / "scripts" / "phase2_e2_jobgen.py"


class TestPhase2M104JobgenBoltzmannExportScriptSmokeToy(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m104_boltzmann_export_smoke"},
            "points": [
                {"point_id": "p0", "params": {"H0": 67.4, "Omega_m": 0.31}},
            ],
        }
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def test_jobgen_boltzmann_export_script_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            outdir = td_path / "pack"
            self._write_plan(plan)

            cmd = [
                sys.executable,
                str(JOBGEN_SCRIPT),
                "--plan",
                str(plan),
                "--outdir",
                str(outdir),
                "--slices",
                "1",
                "--scheduler",
                "bash",
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--",
                "--model",
                "lcdm",
                "--toy",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            merged = outdir / "merged.jsonl"
            rows = [
                {
                    "status": "ok",
                    "chi2_total": 4.2,
                    "params_hash": "m104_best",
                    "plan_point_id": "p0",
                    "params": {
                        "H0": 67.4,
                        "omega_b": 0.049,
                        "omega_m": 0.31,
                        "As": 2.1e-9,
                        "ns": 0.965,
                        "k_pivot_mpc": 0.05,
                    },
                }
            ]
            with merged.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")

            env = os.environ.copy()
            env["GSC_REPO_ROOT"] = str(ROOT)
            env["GSC_PYTHON"] = sys.executable
            proc_export = subprocess.run(
                ["bash", str(outdir / "boltzmann_export.sh")],
                cwd=str(outdir),
                text=True,
                capture_output=True,
                env=env,
            )
            export_output = (proc_export.stdout or "") + (proc_export.stderr or "")
            self.assertEqual(proc_export.returncode, 0, msg=export_output)

            export_dir = outdir / "boltzmann_export_pack"
            self.assertTrue((export_dir / "EXPORT_SUMMARY.json").is_file())
            self.assertTrue((export_dir / "CANDIDATE_RECORD.json").is_file())


if __name__ == "__main__":
    unittest.main()
