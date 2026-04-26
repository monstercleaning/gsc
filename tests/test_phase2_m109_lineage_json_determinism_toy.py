import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_lineage_dag.py"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


class TestPhase2M109LineageJsonDeterminismToy(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _make_bundle_dir(self, root: Path) -> Path:
        bundle_dir = root / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        plan = bundle_dir / "refine_plan.json"
        scan_config = bundle_dir / "scan_config.json"
        shard = bundle_dir / "shard_0001.jsonl"
        merged = bundle_dir / "merged.jsonl"
        report = bundle_dir / "pareto_summary.json"

        self._write_json(plan, {"schema": "phase2_e2_refine_plan_v1", "points": [{"point_id": "p0"}]})
        self._write_json(scan_config, {"scan_config_sha256": "abc"})
        shard.write_text('{"status":"ok","params_hash":"h1"}\n', encoding="utf-8")
        merged.write_text('{"status":"ok","params_hash":"h1","chi2_total":4.0}\n', encoding="utf-8")
        self._write_json(report, {"best": {"chi2_total": 4.0}})

        manifest = {
            "schema": "phase2_e2_manifest_v1",
            "artifacts": [
                {
                    "path": "merged.jsonl",
                    "sha256": _sha256(merged),
                    "bytes": int(merged.stat().st_size),
                },
                {
                    "path": "pareto_summary.json",
                    "sha256": _sha256(report),
                    "bytes": int(report.stat().st_size),
                },
            ],
            "inputs": [
                {
                    "path": "refine_plan.json",
                    "sha256": _sha256(plan),
                    "bytes": int(plan.stat().st_size),
                },
                {
                    "path": "scan_config.json",
                    "sha256": _sha256(scan_config),
                    "bytes": int(scan_config.stat().st_size),
                },
                {
                    "path": "shard_0001.jsonl",
                    "sha256": _sha256(shard),
                    "bytes": int(shard.stat().st_size),
                },
            ],
        }
        self._write_json(bundle_dir / "manifest.json", manifest)
        return bundle_dir

    def test_lineage_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_dir = self._make_bundle_dir(td_path)

            out_a = td_path / "LINEAGE_A.json"
            out_b = td_path / "LINEAGE_B.json"
            cmd_base = [
                sys.executable,
                str(SCRIPT),
                "--bundle-dir",
                str(bundle_dir),
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--format",
                "json",
            ]

            first = subprocess.run(cmd_base + ["--out", str(out_a)], cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, msg=(first.stdout or "") + (first.stderr or ""))

            second = subprocess.run(cmd_base + ["--out", str(out_b)], cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, msg=(second.stdout or "") + (second.stderr or ""))

            self.assertEqual(_sha256(out_a), _sha256(out_b))

            payload = json.loads(out_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_lineage_dag_v1")
            self.assertIn("nodes", payload)
            self.assertIn("edges", payload)
            self.assertGreaterEqual(len(list(payload.get("nodes") or [])), 4)
            self.assertGreaterEqual(len(list(payload.get("edges") or [])), 1)


if __name__ == "__main__":
    unittest.main()
