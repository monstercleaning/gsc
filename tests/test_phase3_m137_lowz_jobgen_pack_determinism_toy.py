import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JOBGEN_SCRIPT = ROOT / "scripts" / "phase3_lowz_jobgen.py"
SCAN_SCRIPT = ROOT / "scripts" / "phase3_scan_sigmatensor_lowz_joint.py"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _file_table(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = _sha256(path)
    return out


class TestPhase3M137LowzJobgenPackDeterminismToy(unittest.TestCase):
    def test_pack_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan_path = td_path / "plan.json"
            out_a = td_path / "pack_a"
            out_b = td_path / "pack_b"

            proc_plan = subprocess.run(
                [
                    sys.executable,
                    str(SCAN_SCRIPT),
                    "--plan-out",
                    str(plan_path),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m-min",
                    "0.31",
                    "--Omega-m-max",
                    "0.31",
                    "--Omega-m-steps",
                    "1",
                    "--w0-min",
                    "-1.0",
                    "--w0-max",
                    "-1.0",
                    "--w0-steps",
                    "1",
                    "--lambda-min",
                    "0.0",
                    "--lambda-max",
                    "0.0",
                    "--lambda-steps",
                    "1",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_plan.returncode, 0, msg=(proc_plan.stdout or "") + (proc_plan.stderr or ""))

            base_cmd = [
                sys.executable,
                str(JOBGEN_SCRIPT),
                "--plan",
                str(plan_path),
                "--slices",
                "2",
                "--scheduler",
                "slurm_array",
                "--shards-compress",
                "gzip",
                "--analysis-top-k",
                "3",
                "--analysis-metric",
                "chi2_total",
                "--joint-extra-arg",
                "--bao",
                "--joint-extra-arg",
                "0",
                "--joint-extra-arg",
                "--sn",
                "--joint-extra-arg",
                "0",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]

            proc_a = subprocess.run(
                [*base_cmd, "--outdir", str(out_a)],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))

            proc_b = subprocess.run(
                [*base_cmd, "--outdir", str(out_b)],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            table_a = _file_table(out_a)
            table_b = _file_table(out_b)
            self.assertEqual(table_a, table_b)

            manifest = json.loads((out_a / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("schema"), "phase3_lowz_job_pack_manifest_v1")
            self.assertEqual(int(manifest.get("slices", 0)), 2)


if __name__ == "__main__":
    unittest.main()
