import gzip
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JOBGEN_SCRIPT = ROOT / "scripts" / "phase3_lowz_jobgen.py"


class TestPhase3M138LowzJobgenSlices1MergeSmokeToy(unittest.TestCase):
    def test_slices_1_run_and_merge(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pack_dir = td_path / "job_pack"

            proc_jobgen = subprocess.run(
                [
                    sys.executable,
                    str(JOBGEN_SCRIPT),
                    "--outdir",
                    str(pack_dir),
                    "--slices",
                    "1",
                    "--scheduler",
                    "bash",
                    "--shards-compress",
                    "gzip",
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m-min",
                    "0.31",
                    "--Omega-m-max",
                    "0.31",
                    "--Omega-m-steps",
                    "1",
                    "--w0-min",
                    "-0.95",
                    "--w0-max",
                    "-0.95",
                    "--w0-steps",
                    "1",
                    "--lambda-min",
                    "0.2",
                    "--lambda-max",
                    "0.2",
                    "--lambda-steps",
                    "1",
                    "--joint-extra-arg",
                    "--bao",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--sn",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--rsd",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--cmb",
                    "--joint-extra-arg",
                    "0",
                    "--joint-extra-arg",
                    "--compare-lcdm",
                    "--joint-extra-arg",
                    "0",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_jobgen.returncode, 0, msg=(proc_jobgen.stdout or "") + (proc_jobgen.stderr or ""))

            env = os.environ.copy()
            env["GSC_REPO_ROOT"] = str(ROOT)
            env["GSC_PYTHON"] = str(sys.executable)

            proc_run = subprocess.run(
                ["bash", "./run_all_local.sh"],
                cwd=str(pack_dir),
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(proc_run.returncode, 0, msg=(proc_run.stdout or "") + (proc_run.stderr or ""))

            proc_merge = subprocess.run(
                ["bash", "./merge_shards.sh"],
                cwd=str(pack_dir),
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(proc_merge.returncode, 0, msg=(proc_merge.stdout or "") + (proc_merge.stderr or ""))

            merged_path = pack_dir / "merged" / "merged.jsonl.gz"
            self.assertTrue(merged_path.is_file())
            self.assertGreater(int(merged_path.stat().st_size), 0)

            with gzip.open(merged_path, "rt", encoding="utf-8") as fh:
                rows = [line for line in fh if line.strip()]
            self.assertGreaterEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
