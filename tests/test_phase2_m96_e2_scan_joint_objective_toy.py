import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = ROOT / "scripts" / "phase2_e2_scan.py"
RSD_DATASET = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"


class TestPhase2M96E2ScanJointObjectiveToy(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
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
            *args,
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    def test_joint_objective_emits_precomputed_joint_field(self) -> None:
        self.assertTrue(SCAN_SCRIPT.is_file())
        self.assertTrue(RSD_DATASET.is_file())
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "joint"
            proc = self._run(
                "--out-dir",
                str(out_dir),
                "--rsd-overlay",
                "--rsd-data",
                str(RSD_DATASET),
                "--chi2-objective",
                "joint",
                "--rsd-chi2-field",
                "rsd_chi2_total",
                "--rsd-chi2-weight",
                "1.0",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            rows = self._read_jsonl(out_dir / "e2_scan_points.jsonl")
            self.assertGreaterEqual(len(rows), 1)
            ok_rows = [r for r in rows if str(r.get("status", "")).strip().lower() == "ok"]
            self.assertTrue(ok_rows)
            for row in ok_rows:
                chi2_total = row.get("chi2_total")
                chi2_rsd = row.get("rsd_chi2_total")
                if chi2_total is None or chi2_rsd is None:
                    continue
                self.assertIn("chi2_joint_total", row)
                self.assertAlmostEqual(
                    float(row["chi2_joint_total"]),
                    float(chi2_total) + float(chi2_rsd),
                    places=12,
                )
                self.assertEqual(str(row.get("rsd_chi2_field_used")), "rsd_chi2_total")
                self.assertAlmostEqual(float(row.get("rsd_chi2_weight")), 1.0, places=12)

    def test_joint_objective_requires_rsd_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "missing_overlay"
            proc = self._run(
                "--out-dir",
                str(out_dir),
                "--chi2-objective",
                "joint",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("MISSING_RSD_OVERLAY_FOR_JOINT_OBJECTIVE", output)


if __name__ == "__main__":
    unittest.main()
