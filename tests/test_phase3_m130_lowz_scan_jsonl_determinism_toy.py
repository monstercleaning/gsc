import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_scan_sigmatensor_lowz_joint.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class TestPhase3M130LowzScanJsonlDeterminismToy(unittest.TestCase):
    def test_scan_jsonl_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            out_a = td_path / "scan_a.jsonl"
            out_b = td_path / "scan_b.jsonl"

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
                    "0.0",
                    "--lambda-steps",
                    "1",
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_plan.returncode, 0, msg=(proc_plan.stdout or "") + (proc_plan.stderr or ""))

            base_scan_cmd = [
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

            proc_a = subprocess.run(
                [*base_scan_cmd, "--out-jsonl", str(out_a)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))

            proc_b = subprocess.run(
                [*base_scan_cmd, "--out-jsonl", str(out_b)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            self.assertEqual(_sha256(out_a), _sha256(out_b))
            text = out_a.read_text(encoding="utf-8")
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)

            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row.get("schema"), "phase3_sigmatensor_lowz_scan_row_v1")
                self.assertEqual(row.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
