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
            "n_plausible": 3,
            "status_counts": {"ok": 3, "error": 1},
        },
        "best": {
            "best_overall": {
                "chi2_total": float(best_overall_chi2),
                "microphysics_plausible_ok": True,
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
    }
    cert_path.write_text(json.dumps(cert_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    merge_payload = {
        "scan_config_sha256_chosen": str(config_sha),
        "plan_source_sha256_chosen": str(plan_sha),
    }
    merge_path.write_text(json.dumps(merge_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    (root / "manifest.json").write_text(
        json.dumps({"schema": "phase2_e2_manifest_v1", "artifacts": []}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _make_tar_bundle(path: Path, **kwargs: object) -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        tree = td_path / "bundle_root"
        tree.mkdir(parents=True, exist_ok=True)
        _write_bundle_tree(root=tree, **kwargs)
        with tarfile.open(path, "w:gz") as tf:
            tf.add(tree, arcname="bundle")


class TestPhase2M64BuildPaperBundleAutoSelectResolveOnly(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "build_paper.sh"
        return subprocess.run(["bash", str(script)] + list(args), cwd=str(ROOT), text=True, capture_output=True)

    def test_help_includes_new_phase2_selector_flags(self) -> None:
        proc = self._run(["--help"])
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)
        self.assertIn("--phase2-e2-bundle", output)
        self.assertIn("--phase2-e2-bundle-dir", output)
        self.assertIn("--phase2-e2-bundle-select", output)
        self.assertIn("--phase2-e2-resolve-only", output)

    def test_resolve_only_auto_selects_bundle_from_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_a = td_path / "bundle_a.tar.gz"
            bundle_b = td_path / "bundle_b.tar.gz"

            # Better chi2 but incomplete coverage -> should be excluded by build_paper auto-selection.
            _make_tar_bundle(
                bundle_b,
                best_overall_chi2=7.0,
                best_plausible_chi2=7.0,
                coverage_fraction=0.5,
                config_sha="cfg_x",
                plan_sha="plan_x",
                params_hash="hash_b",
                point_id="p1",
            )
            # Slightly worse chi2 but complete coverage -> expected winner.
            _make_tar_bundle(
                bundle_a,
                best_overall_chi2=8.0,
                best_plausible_chi2=8.0,
                coverage_fraction=1.0,
                config_sha="cfg_x",
                plan_sha="plan_x",
                params_hash="hash_a",
                point_id="p0",
            )

            proc = self._run(
                [
                    "--phase2-e2-bundle-dir",
                    str(td_path),
                    "--phase2-e2-bundle-select",
                    "best_plausible",
                    "--phase2-e2-resolve-only",
                ]
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertEqual(proc.stdout.strip(), str(bundle_a.resolve()))
            self.assertEqual(proc.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
