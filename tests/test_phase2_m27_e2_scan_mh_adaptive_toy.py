import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M27E2ScanMHAdaptiveToy(unittest.TestCase):
    def _run_scan(self, *, out_dir: Path, resume: bool) -> subprocess.CompletedProcess[str]:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--toy",
            "--model",
            "lcdm",
            "--sampler",
            "mh_adaptive",
            "--mh-chains",
            "2",
            "--mh-steps",
            "30",
            "--mh-burnin",
            "10",
            "--mh-thin",
            "2",
            "--seed",
            "123",
            "--resume-mode",
            "cache",
            "--grid",
            "H0=60:75",
            "--grid",
            "Omega_m=0.2:0.4",
            "--out-dir",
            str(out_dir),
        ]
        if resume:
            cmd.append("--resume")
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_jsonl(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _normalized_rows(self, rows: list[dict]) -> list[dict]:
        out = []
        for row in rows:
            out.append(
                {
                    "model": row.get("model"),
                    "params_hash": row.get("params_hash"),
                    "chain_id": row.get("chain_id"),
                    "step_index": row.get("step_index"),
                    "accepted": row.get("accepted"),
                    "energy": row.get("energy"),
                    "log_alpha": row.get("log_alpha"),
                    "sampler_name": row.get("sampler_name"),
                }
            )
        return out

    def test_mh_adaptive_toy_cache_resume(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"

            proc1 = self._run_scan(out_dir=out_dir, resume=False)
            output1 = (proc1.stdout or "") + (proc1.stderr or "")
            self.assertEqual(proc1.returncode, 0, msg=output1)

            jsonl_path = out_dir / "e2_scan_points.jsonl"
            self.assertTrue(jsonl_path.is_file())
            rows1 = self._load_jsonl(jsonl_path)
            # 2 chains * ((30-10)/2) = 20 emitted rows.
            self.assertEqual(len(rows1), 20)

            for row in rows1:
                self.assertEqual(row.get("sampler_name"), "mh_adaptive")
                self.assertIn("chain_id", row)
                self.assertIn("step_index", row)
                self.assertIn("accepted", row)
                self.assertIn("energy", row)
                self.assertIn("energy_proposal", row)
                self.assertIn("proposal_scales", row)
                self.assertIn("cache_hit", row)

            proc2 = self._run_scan(out_dir=out_dir, resume=True)
            output2 = (proc2.stdout or "") + (proc2.stderr or "")
            self.assertEqual(proc2.returncode, 0, msg=output2)

            rows2 = self._load_jsonl(jsonl_path)
            self.assertEqual(len(rows2), 40)
            self.assertEqual(self._normalized_rows(rows1), self._normalized_rows(rows2[:20]))
            self.assertEqual(self._normalized_rows(rows1), self._normalized_rows(rows2[20:]))
            self.assertTrue(any(bool(row.get("cache_hit")) for row in rows2[20:]))


if __name__ == "__main__":
    unittest.main()
