import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _write_bundle_tree(
    *,
    root: Path,
    best_overall_chi2: float,
    best_plausible_chi2: float,
    coverage_fraction: float,
    plausible_ok: bool,
    config_sha: str,
    plan_sha: str,
    params_hash: str,
    point_id: str,
) -> None:
    cert_rel = Path("paper_assets/paper_assets_cmb_e2_drift_constrained_closure_bound/e2_certificate.json")
    merge_rel = Path("merge_report.json")

    cert_path = root / cert_rel
    merge_path = root / merge_rel
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    cert_payload = {
        "schema": "phase2_e2_certificate_v1",
        "inputs": {"plan": {"sha256": str(plan_sha)}},
        "coverage": {
            "n_plan_points": 4,
            "n_seen_plan_point_ids": int(round(float(coverage_fraction) * 4.0)),
            "fraction": float(coverage_fraction),
        },
        "counts": {
            "n_total_records": 4,
            "n_ok": 3,
            "n_eligible": 3,
            "n_plausible": 2 if plausible_ok else 0,
            "status_counts": {"ok": 3, "error": 1},
        },
        "best": {
            "best_overall": {
                "chi2_total": float(best_overall_chi2),
                "microphysics_plausible_ok": bool(plausible_ok),
                "params_hash": str(params_hash),
                "plan_point_id": str(point_id),
            },
            "best_plausible": {
                "chi2_total": float(best_plausible_chi2),
                "microphysics_plausible_ok": True,
                "params_hash": str(params_hash),
                "plan_point_id": str(point_id),
            },
        },
        "top_k": {
            "overall": [
                {
                    "chi2_total": float(best_overall_chi2),
                    "microphysics_plausible_ok": bool(plausible_ok),
                    "params_hash": str(params_hash),
                    "plan_point_id": str(point_id),
                }
            ]
        },
    }
    cert_path.write_text(json.dumps(cert_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    merge_payload = {
        "scan_config_sha256_chosen": str(config_sha),
        "plan_source_sha256_chosen": str(plan_sha),
    }
    merge_path.write_text(json.dumps(merge_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_payload = {
        "schema": "phase2_e2_manifest_v1",
        "artifacts": [],
        "inputs": [],
        "run": {"argv": [], "outdir": ".", "dry_run": False},
    }
    (root / "manifest.json").write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _make_tar_bundle(path: Path, **kwargs: object) -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        tree = td_path / "bundle_root"
        tree.mkdir(parents=True, exist_ok=True)
        _write_bundle_tree(root=tree, **kwargs)
        with tarfile.open(path, "w:gz") as tf:
            tf.add(tree, arcname="bundle")


class TestPhase2M64E2SelectBundle(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_select_bundle.py"
        cmd = [sys.executable, str(script)] + list(args)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_selection_and_coverage_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_a = td_path / "bundle_a.tar.gz"
            bundle_b = td_path / "bundle_b.tar.gz"

            _make_tar_bundle(
                bundle_a,
                best_overall_chi2=10.0,
                best_plausible_chi2=10.0,
                coverage_fraction=1.0,
                plausible_ok=True,
                config_sha="cfg_a",
                plan_sha="plan_x",
                params_hash="hash_a",
                point_id="p0",
            )
            _make_tar_bundle(
                bundle_b,
                best_overall_chi2=8.0,
                best_plausible_chi2=8.0,
                coverage_fraction=0.5,
                plausible_ok=True,
                config_sha="cfg_a",
                plan_sha="plan_x",
                params_hash="hash_b",
                point_id="p1",
            )

            proc_best = self._run(
                [
                    "--input",
                    str(td_path),
                    "--select",
                    "best_plausible",
                    "--format",
                    "json",
                ]
            )
            out_best = (proc_best.stdout or "") + (proc_best.stderr or "")
            self.assertEqual(proc_best.returncode, 0, msg=out_best)
            payload_best = json.loads(proc_best.stdout)
            self.assertEqual(Path(payload_best.get("selected_bundle_path", "")).resolve(), bundle_b.resolve())

            proc_cov = self._run(
                [
                    "--input",
                    str(td_path),
                    "--select",
                    "best_plausible",
                    "--require-plan-coverage",
                    "complete",
                    "--format",
                    "json",
                ]
            )
            out_cov = (proc_cov.stdout or "") + (proc_cov.stderr or "")
            self.assertEqual(proc_cov.returncode, 0, msg=out_cov)
            payload_cov = json.loads(proc_cov.stdout)
            self.assertEqual(Path(payload_cov.get("selected_bundle_path", "")).resolve(), bundle_a.resolve())

            proc_fail = self._run(
                [
                    "--input",
                    str(bundle_b),
                    "--select",
                    "best_plausible",
                    "--require-plan-coverage",
                    "complete",
                    "--format",
                    "json",
                ]
            )
            out_fail = (proc_fail.stdout or "") + (proc_fail.stderr or "")
            self.assertEqual(proc_fail.returncode, 2, msg=out_fail)

    def test_print_path_outputs_only_selected_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_a = td_path / "bundle_a.tar.gz"
            bundle_b = td_path / "bundle_b.tar.gz"

            _make_tar_bundle(
                bundle_a,
                best_overall_chi2=5.0,
                best_plausible_chi2=5.0,
                coverage_fraction=1.0,
                plausible_ok=True,
                config_sha="cfg_same",
                plan_sha="plan_same",
                params_hash="hash_a",
                point_id="p0",
            )
            _make_tar_bundle(
                bundle_b,
                best_overall_chi2=4.0,
                best_plausible_chi2=4.0,
                coverage_fraction=1.0,
                plausible_ok=True,
                config_sha="cfg_same",
                plan_sha="plan_same",
                params_hash="hash_b",
                point_id="p1",
            )

            proc = self._run(
                [
                    "--input",
                    str(bundle_a),
                    "--input",
                    str(bundle_b),
                    "--select",
                    "best_eligible",
                    "--print-path",
                ]
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)
            self.assertEqual(proc.stdout.strip(), str(bundle_b.resolve()))
            self.assertEqual(proc.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
