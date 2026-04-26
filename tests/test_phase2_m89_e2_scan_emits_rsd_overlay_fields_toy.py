import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = ROOT / "scripts" / "phase2_e2_scan.py"
RSD_DATASET = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TestPhase2M89E2ScanEmitsRsdOverlayFieldsToy(unittest.TestCase):
    def _run_scan(self, *, out_dir: Path, rsd_overlay: bool) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(SCAN_SCRIPT),
            "--model",
            "lcdm",
            "--toy",
            "--grid",
            "H0=67.4",
            "--grid",
            "Omega_m=0.315",
            "--out-dir",
            str(out_dir),
        ]
        if rsd_overlay:
            cmd.extend(
                [
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--rsd-ap-correction",
                    "none",
                    "--rsd-mode",
                    "profile_sigma8_0",
                ]
            )
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_jsonl_records(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    def test_scan_emits_rsd_fields_and_config_sha_changes(self) -> None:
        self.assertTrue(SCAN_SCRIPT.is_file())
        self.assertTrue(RSD_DATASET.is_file())
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            out_plain = tdp / "plain"
            out_rsd = tdp / "rsd"

            proc_plain = self._run_scan(out_dir=out_plain, rsd_overlay=False)
            msg_plain = (proc_plain.stdout or "") + (proc_plain.stderr or "")
            self.assertEqual(proc_plain.returncode, 0, msg=msg_plain)

            proc_rsd = self._run_scan(out_dir=out_rsd, rsd_overlay=True)
            msg_rsd = (proc_rsd.stdout or "") + (proc_rsd.stderr or "")
            self.assertEqual(proc_rsd.returncode, 0, msg=msg_rsd)

            rows_plain = self._load_jsonl_records(out_plain / "e2_scan_points.jsonl")
            rows_rsd = self._load_jsonl_records(out_rsd / "e2_scan_points.jsonl")
            self.assertGreaterEqual(len(rows_plain), 1)
            self.assertGreaterEqual(len(rows_rsd), 1)

            first_plain = rows_plain[0]
            first_rsd = rows_rsd[0]
            sha_plain = str(first_plain.get("scan_config_sha256", "")).strip()
            sha_rsd = str(first_rsd.get("scan_config_sha256", "")).strip()
            self.assertTrue(sha_plain)
            self.assertTrue(sha_rsd)
            self.assertNotEqual(sha_plain, sha_rsd)

            ok_rows = [row for row in rows_rsd if str(row.get("status", "")).strip().lower() == "ok"]
            self.assertGreaterEqual(len(ok_rows), 1)
            ok_row = ok_rows[0]

            self.assertIn("rsd_overlay_ok", ok_row)
            self.assertIn("rsd_chi2", ok_row)
            self.assertIn("rsd_sigma8_0_best", ok_row)
            self.assertIn("rsd_dataset_sha256", ok_row)
            self.assertIn("rsd_n", ok_row)
            self.assertIn("rsd_dataset_id", ok_row)
            self.assertEqual(str(ok_row.get("rsd_ap_correction")), "none")
            self.assertEqual(str(ok_row.get("rsd_mode")), "profile_sigma8_0")
            self.assertTrue(bool(ok_row.get("rsd_overlay_ok")))
            self.assertIsNotNone(ok_row.get("rsd_chi2"))
            self.assertIsNotNone(ok_row.get("rsd_sigma8_0_best"))
            self.assertGreater(int(ok_row.get("rsd_n", 0)), 0)
            self.assertGreaterEqual(float(ok_row.get("rsd_chi2")), 0.0)
            self.assertRegex(str(ok_row.get("rsd_dataset_sha256", "")), SHA256_RE)


if __name__ == "__main__":
    unittest.main()
