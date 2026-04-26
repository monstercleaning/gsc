import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M61ScanConfigShaContract(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m61_plan_seed"},
            "points": [
                {"point_id": "p0", "params": {"H0": 66.8, "Omega_m": 0.300}},
                {"point_id": "p1", "params": {"H0": 67.1, "Omega_m": 0.310}},
                {"point_id": "p2", "params": {"H0": 67.4, "Omega_m": 0.320}},
                {"point_id": "p3", "params": {"H0": 67.7, "Omega_m": 0.330}},
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_scan_slice(
        self,
        *,
        plan: Path,
        outdir: Path,
        slice_spec: str,
        extra_args: Optional[list[str]] = None,
    ) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan),
            "--plan-slice",
            str(slice_spec),
            "--jobs",
            "2",
            "--out-dir",
            str(outdir),
        ]
        if extra_args:
            cmd.extend(str(v) for v in extra_args)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _run_merge(
        self,
        *,
        inputs: list[Path],
        out_jsonl: Path,
        policy: str,
    ) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_merge_jsonl.py"
        cmd = [
            sys.executable,
            str(script),
            *[str(p) for p in inputs],
            "--out",
            str(out_jsonl),
            "--scan-config-sha-policy",
            str(policy),
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_first_record(self, path: Path) -> dict:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        self.fail(f"No JSON object record found in {path}")

    def _rewrite_with_scan_sha(self, *, src: Path, dst: Path, scan_sha: Optional[str]) -> None:
        out_lines: list[str] = []
        for line in src.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if not isinstance(payload, dict):
                continue
            if scan_sha is None:
                payload.pop("scan_config_sha256", None)
            else:
                payload["scan_config_sha256"] = str(scan_sha)
            out_lines.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    def test_scan_emits_sha_and_merge_rejects_mixed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            plan = tdp / "plan.json"
            self._write_plan(plan)

            s0_dir = tdp / "s0"
            s1_dir = tdp / "s1"
            proc0 = self._run_scan_slice(plan=plan, outdir=s0_dir, slice_spec="0/2")
            out0 = (proc0.stdout or "") + (proc0.stderr or "")
            self.assertEqual(proc0.returncode, 0, msg=out0)
            proc1 = self._run_scan_slice(plan=plan, outdir=s1_dir, slice_spec="1/2")
            out1 = (proc1.stdout or "") + (proc1.stderr or "")
            self.assertEqual(proc1.returncode, 0, msg=out1)

            shard0 = s0_dir / "e2_scan_points.jsonl"
            shard1 = s1_dir / "e2_scan_points.jsonl"
            self.assertTrue(shard0.is_file())
            self.assertTrue(shard1.is_file())

            row0 = self._load_first_record(shard0)
            row1 = self._load_first_record(shard1)
            sha0 = str(row0.get("scan_config_sha256", "")).strip()
            sha1 = str(row1.get("scan_config_sha256", "")).strip()
            self.assertTrue(sha0)
            self.assertTrue(sha1)
            self.assertEqual(sha0, sha1)

            sidecar0 = Path(str(shard0) + ".scan_config.json")
            sidecar1 = Path(str(shard1) + ".scan_config.json")
            self.assertTrue(sidecar0.is_file())
            self.assertTrue(sidecar1.is_file())
            side_payload0 = json.loads(sidecar0.read_text(encoding="utf-8"))
            side_payload1 = json.loads(sidecar1.read_text(encoding="utf-8"))
            self.assertEqual(side_payload0.get("scan_config_sha256"), sha0)
            self.assertEqual(side_payload1.get("scan_config_sha256"), sha1)

            bad = tdp / "bad.jsonl"
            self._rewrite_with_scan_sha(src=shard1, dst=bad, scan_sha="b" * 64)
            merged_bad = tdp / "merged_bad.jsonl"
            proc_bad = self._run_merge(inputs=[shard0, bad], out_jsonl=merged_bad, policy="auto")
            out_bad = (proc_bad.stdout or "") + (proc_bad.stderr or "")
            self.assertEqual(proc_bad.returncode, 2, msg=out_bad)
            self.assertIn("scan_config_sha256", out_bad)

            legacy0 = tdp / "legacy0.jsonl"
            legacy1 = tdp / "legacy1.jsonl"
            self._rewrite_with_scan_sha(src=shard0, dst=legacy0, scan_sha=None)
            self._rewrite_with_scan_sha(src=shard1, dst=legacy1, scan_sha=None)
            merged_legacy = tdp / "merged_legacy.jsonl"
            proc_legacy = self._run_merge(inputs=[legacy0, legacy1], out_jsonl=merged_legacy, policy="auto")
            out_legacy = (proc_legacy.stdout or "") + (proc_legacy.stderr or "")
            self.assertEqual(proc_legacy.returncode, 0, msg=out_legacy)
            self.assertTrue(merged_legacy.is_file())
            self.assertTrue(hashlib.sha256(merged_legacy.read_bytes()).hexdigest())

    def test_rsd_irrelevant_knobs_do_not_perturb_sha_when_overlay_off(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            plan = tdp / "plan.json"
            self._write_plan(plan)

            out_a = tdp / "out_a"
            out_b = tdp / "out_b"
            proc_a = self._run_scan_slice(
                plan=plan,
                outdir=out_a,
                slice_spec="0/1",
                extra_args=[
                    "--rsd-mode",
                    "derived_As",
                    "--rsd-transfer-model",
                    "bbks",
                    "--rsd-ns",
                    "0.95",
                    "--rsd-k-pivot",
                    "0.05",
                ],
            )
            proc_b = self._run_scan_slice(
                plan=plan,
                outdir=out_b,
                slice_spec="0/1",
                extra_args=[
                    "--rsd-mode",
                    "derived_As",
                    "--rsd-transfer-model",
                    "eh98_nowiggle",
                    "--rsd-ns",
                    "1.03",
                    "--rsd-k-pivot",
                    "0.09",
                ],
            )
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            shard_a = out_a / "e2_scan_points.jsonl"
            shard_b = out_b / "e2_scan_points.jsonl"
            row_a = self._load_first_record(shard_a)
            row_b = self._load_first_record(shard_b)
            sha_a = str(row_a.get("scan_config_sha256", "")).strip()
            sha_b = str(row_b.get("scan_config_sha256", "")).strip()
            self.assertTrue(sha_a)
            self.assertTrue(sha_b)
            self.assertEqual(sha_a, sha_b)


if __name__ == "__main__":
    unittest.main()
