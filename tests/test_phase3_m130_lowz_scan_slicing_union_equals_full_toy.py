import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_scan_sigmatensor_lowz_joint.py"


def _load_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        payload = json.loads(text)
        ids.add(str(payload.get("plan_point_id")))
    return ids


class TestPhase3M130LowzScanSlicingUnionEqualsFullToy(unittest.TestCase):
    def test_slice_union_matches_full(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            full = td_path / "full.jsonl"
            s0 = td_path / "s0.jsonl"
            s1 = td_path / "s1.jsonl"

            proc_plan = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--plan-out",
                    str(plan),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m-min",
                    "0.30",
                    "--Omega-m-max",
                    "0.31",
                    "--Omega-m-steps",
                    "2",
                    "--w0-min",
                    "-1.0",
                    "--w0-max",
                    "-1.0",
                    "--w0-steps",
                    "1",
                    "--lambda-min",
                    "0.0",
                    "--lambda-max",
                    "0.1",
                    "--lambda-steps",
                    "2",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_plan.returncode, 0, msg=(proc_plan.stdout or "") + (proc_plan.stderr or ""))

            common = [
                sys.executable,
                str(SCRIPT),
                "--plan",
                str(plan),
                "--created-utc",
                "2000-01-01T00:00:00Z",
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
            ]

            proc_full = subprocess.run(
                [*common, "--out-jsonl", str(full)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_full.returncode, 0, msg=(proc_full.stdout or "") + (proc_full.stderr or ""))

            proc_s0 = subprocess.run(
                [*common, "--plan-slice", "0/2", "--out-jsonl", str(s0)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_s0.returncode, 0, msg=(proc_s0.stdout or "") + (proc_s0.stderr or ""))

            proc_s1 = subprocess.run(
                [*common, "--plan-slice", "1/2", "--out-jsonl", str(s1)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_s1.returncode, 0, msg=(proc_s1.stdout or "") + (proc_s1.stderr or ""))

            full_ids = _load_ids(full)
            s0_ids = _load_ids(s0)
            s1_ids = _load_ids(s1)
            self.assertEqual(full_ids, s0_ids | s1_ids)


if __name__ == "__main__":
    unittest.main()
