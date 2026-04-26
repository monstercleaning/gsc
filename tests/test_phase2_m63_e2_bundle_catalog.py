import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M63E2BundleCatalog(unittest.TestCase):
    def _sha256_bytes(self, data: bytes) -> str:
        digest = hashlib.sha256()
        digest.update(data)
        return digest.hexdigest()

    def _write_bundle_tree(
        self,
        *,
        root: Path,
        best_chi2: float,
        coverage_fraction: float,
        n_ok: int,
        n_error: int,
        config_sha: str,
        plan_source_sha: str,
        git_sha: str,
        params_hash: str,
        plan_point_id: str,
    ) -> None:
        cert_rel = Path("paper_assets/paper_assets_cmb_e2_drift_constrained_closure_bound/e2_certificate.json")
        merge_rel = Path("merge_report.json")
        cert_path = root / cert_rel
        merge_path = root / merge_rel
        cert_path.parent.mkdir(parents=True, exist_ok=True)

        cert_payload = {
            "schema": "phase2_e2_certificate_v1",
            "tool": {"repo_git_sha": str(git_sha)},
            "inputs": {"plan": {"sha256": str(plan_source_sha)}},
            "counts": {
                "n_total_records": int(n_ok + n_error),
                "n_ok": int(n_ok),
                "n_eligible": int(n_ok),
                "n_plausible": int(n_ok),
                "status_counts": {"ok": int(n_ok), "error": int(n_error)},
            },
            "coverage": {
                "n_plan_points": 4,
                "n_seen_plan_point_ids": int(round(4.0 * float(coverage_fraction))),
                "fraction": float(coverage_fraction),
            },
            "best": {
                "best_overall": {
                    "chi2_total": float(best_chi2),
                    "params_hash": str(params_hash),
                    "plan_point_id": str(plan_point_id),
                },
                "best_plausible": {
                    "chi2_total": float(best_chi2 + 0.25),
                    "params_hash": str(params_hash),
                    "plan_point_id": str(plan_point_id),
                },
            },
        }
        cert_text = json.dumps(cert_payload, indent=2, sort_keys=True) + "\n"
        cert_path.write_text(cert_text, encoding="utf-8")

        merge_payload = {
            "scan_config_sha256_chosen": str(config_sha),
            "plan_source_sha256_chosen": str(plan_source_sha),
        }
        merge_text = json.dumps(merge_payload, indent=2, sort_keys=True) + "\n"
        merge_path.write_text(merge_text, encoding="utf-8")

        artifacts = []
        for rel, text in (
            (str(merge_rel).replace("\\", "/"), merge_text),
            (str(cert_rel).replace("\\", "/"), cert_text),
        ):
            data = text.encode("utf-8")
            artifacts.append(
                {
                    "path": rel,
                    "sha256": self._sha256_bytes(data),
                    "bytes": len(data),
                }
            )
        manifest_payload = {
            "schema": "phase2_e2_manifest_v1",
            "git": {"sha": str(git_sha), "dirty": False},
            "artifacts": sorted(artifacts, key=lambda row: str(row["path"])),
            "inputs": [],
            "run": {"argv": [], "outdir": ".", "dry_run": False},
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _make_bundle_tar(
        self,
        *,
        out_path: Path,
        best_chi2: float,
        coverage_fraction: float,
        n_ok: int,
        n_error: int,
        config_sha: str,
        plan_source_sha: str,
        git_sha: str,
        params_hash: str,
        plan_point_id: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = td_path / "bundle_root"
            root.mkdir(parents=True, exist_ok=True)
            self._write_bundle_tree(
                root=root,
                best_chi2=best_chi2,
                coverage_fraction=coverage_fraction,
                n_ok=n_ok,
                n_error=n_error,
                config_sha=config_sha,
                plan_source_sha=plan_source_sha,
                git_sha=git_sha,
                params_hash=params_hash,
                plan_point_id=plan_point_id,
            )
            with tarfile.open(out_path, "w:gz") as tf:
                tf.add(root, arcname="bundle")

    def _run_catalog(self, args: list[str]) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_bundle_catalog.py"
        cmd = [sys.executable, str(script)] + list(args)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_catalog_json_sort_and_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_a = td_path / "a.tar.gz"
            bundle_b = td_path / "b.tar.gz"

            self._make_bundle_tar(
                out_path=bundle_a,
                best_chi2=10.0,
                coverage_fraction=1.0,
                n_ok=3,
                n_error=1,
                config_sha="cfg_a",
                plan_source_sha="plan_a",
                git_sha="git_a",
                params_hash="hash_a",
                plan_point_id="p0",
            )
            self._make_bundle_tar(
                out_path=bundle_b,
                best_chi2=9.0,
                coverage_fraction=0.5,
                n_ok=2,
                n_error=0,
                config_sha="cfg_b",
                plan_source_sha="plan_b",
                git_sha="git_b",
                params_hash="hash_b",
                plan_point_id="p1",
            )

            proc = self._run_catalog(
                [
                    "--bundle",
                    str(bundle_a),
                    "--bundle",
                    str(bundle_b),
                    "--format",
                    "json",
                    "--sort-by",
                    "best_chi2_total",
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(proc.stdout)

            self.assertEqual(payload.get("schema"), "phase2_e2_bundle_catalog_v1")
            self.assertEqual(int(payload.get("inputs", {}).get("n_bundles_found", 0)), 2)
            bundles = list(payload.get("bundles") or [])
            self.assertEqual(len(bundles), 2)
            self.assertAlmostEqual(float(bundles[0].get("best_chi2_total")), 9.0, places=9)
            self.assertTrue(str(bundles[0].get("path", "")).endswith("b.tar.gz"))

            proc_cov = self._run_catalog(
                [
                    "--bundle",
                    str(bundle_a),
                    "--bundle",
                    str(bundle_b),
                    "--format",
                    "json",
                    "--require-coverage",
                    "complete",
                ]
            )
            output_cov = (proc_cov.stdout or "") + (proc_cov.stderr or "")
            self.assertEqual(proc_cov.returncode, 2, msg=output_cov)

            proc_same_fail = self._run_catalog(
                [
                    "--bundle",
                    str(bundle_a),
                    "--bundle",
                    str(bundle_b),
                    "--format",
                    "json",
                    "--require-same",
                    "config_sha",
                ]
            )
            output_same_fail = (proc_same_fail.stdout or "") + (proc_same_fail.stderr or "")
            self.assertEqual(proc_same_fail.returncode, 2, msg=output_same_fail)

            bundle_c = td_path / "c.tar.gz"
            self._make_bundle_tar(
                out_path=bundle_c,
                best_chi2=8.5,
                coverage_fraction=1.0,
                n_ok=2,
                n_error=0,
                config_sha="cfg_a",
                plan_source_sha="plan_a",
                git_sha="git_a",
                params_hash="hash_c",
                plan_point_id="p2",
            )
            proc_same_ok = self._run_catalog(
                [
                    "--bundle",
                    str(bundle_a),
                    "--bundle",
                    str(bundle_c),
                    "--format",
                    "json",
                    "--require-same",
                    "config_sha",
                ]
            )
            output_same_ok = (proc_same_ok.stdout or "") + (proc_same_ok.stderr or "")
            self.assertEqual(proc_same_ok.returncode, 0, msg=output_same_ok)

    def test_directory_input_discovers_archives(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundles_dir = td_path / "bundles"
            bundles_dir.mkdir(parents=True, exist_ok=True)
            bundle_a = bundles_dir / "run_a.tar.gz"
            bundle_b = bundles_dir / "run_b.tar.gz"

            self._make_bundle_tar(
                out_path=bundle_a,
                best_chi2=7.0,
                coverage_fraction=1.0,
                n_ok=3,
                n_error=0,
                config_sha="cfg_dir",
                plan_source_sha="plan_dir",
                git_sha="git_dir",
                params_hash="h1",
                plan_point_id="p0",
            )
            self._make_bundle_tar(
                out_path=bundle_b,
                best_chi2=6.0,
                coverage_fraction=1.0,
                n_ok=4,
                n_error=0,
                config_sha="cfg_dir",
                plan_source_sha="plan_dir",
                git_sha="git_dir",
                params_hash="h2",
                plan_point_id="p1",
            )

            proc = self._run_catalog(
                [
                    "--bundle",
                    str(bundles_dir),
                    "--format",
                    "json",
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(proc.stdout)
            self.assertEqual(int(payload.get("inputs", {}).get("n_bundles_found", 0)), 2)
            self.assertEqual(len(list(payload.get("bundles") or [])), 2)


if __name__ == "__main__":
    unittest.main()
