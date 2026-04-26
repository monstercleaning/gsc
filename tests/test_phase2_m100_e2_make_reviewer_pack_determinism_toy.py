import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PACK_SCRIPT = ROOT / "scripts" / "phase2_e2_make_reviewer_pack.py"
BUNDLE_SCRIPT = ROOT / "scripts" / "phase2_e2_bundle.py"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase2M100E2MakeReviewerPackDeterminismToy(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _make_bundle_zip(self, td_path: Path) -> Path:
        shard_a = td_path / "shard_a.jsonl"
        shard_b = td_path / "shard_b.jsonl"
        self._write_jsonl(
            shard_a,
            [
                {"type": "header", "schema": "gsc.phase2.e2.scan.v1"},
                {
                    "params_hash": "hash_a",
                    "status": "ok",
                    "model": "lcdm",
                    "chi2_total": 4.0,
                    "chi2_cmb": 2.0,
                    "drift_metric": 0.5,
                    "drift_sign_z2_5": True,
                    "microphysics_plausible_ok": True,
                    "params": {"H0": 67.0, "Omega_m": 0.30},
                    "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.01, "r_d_scale": 1.0},
                },
            ],
        )
        self._write_jsonl(
            shard_b,
            [
                {
                    "params_hash": "hash_b",
                    "status": "ok",
                    "model": "lcdm",
                    "chi2_total": 4.8,
                    "chi2_cmb": 2.3,
                    "drift_metric": 0.6,
                    "drift_sign_z2_5": True,
                    "microphysics_plausible_ok": True,
                    "params": {"H0": 68.0, "Omega_m": 0.31},
                    "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.02, "r_d_scale": 1.01},
                },
            ],
        )

        bundle_dir = td_path / "bundle_dir"
        bundle_proc = self._run(
            [
                sys.executable,
                str(BUNDLE_SCRIPT),
                "--in",
                str(shard_a),
                "--in",
                str(shard_b),
                "--outdir",
                str(bundle_dir),
                "--steps",
                "merge,pareto,manifest,meta",
            ]
        )
        self.assertEqual(bundle_proc.returncode, 0, msg=(bundle_proc.stdout or "") + (bundle_proc.stderr or ""))
        self.assertTrue((bundle_dir / "manifest.json").is_file())

        bundle_zip = td_path / "bundle.zip"
        with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(bundle_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(bundle_dir).as_posix()
                zf.write(path, arcname=str(PurePosixPath("bundle") / rel))
        return bundle_zip

    def test_reviewer_pack_zip_is_deterministic_and_hygienic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_zip = self._make_bundle_zip(td_path)

            outdir = td_path / "reviewer_pack_out"
            zip1 = td_path / "reviewer_pack_1.zip"
            zip2 = td_path / "reviewer_pack_2.zip"
            summary1 = td_path / "reviewer_pack_summary_1.json"
            summary2 = td_path / "reviewer_pack_summary_2.json"

            cmd = [
                sys.executable,
                str(REVIEWER_PACK_SCRIPT),
                "--bundle",
                str(bundle_zip),
                "--snapshot-profile",
                "share",
                "--outdir",
                str(outdir),
                "--zip-out",
                str(zip1),
                "--skip-portable-content-lint",
                "--format",
                "json",
                "--json-out",
                str(summary1),
            ]
            first = self._run(cmd)
            self.assertEqual(first.returncode, 0, msg=(first.stdout or "") + (first.stderr or ""))
            self.assertTrue(zip1.is_file(), msg=str(zip1))

            shutil.rmtree(outdir)
            cmd[cmd.index(str(zip1))] = str(zip2)
            cmd[cmd.index(str(summary1))] = str(summary2)
            second = self._run(cmd)
            self.assertEqual(second.returncode, 0, msg=(second.stdout or "") + (second.stderr or ""))
            self.assertTrue(zip2.is_file(), msg=str(zip2))

            self.assertEqual(_sha256_path(zip1), _sha256_path(zip2))

            summary_payload = json.loads(summary1.read_text(encoding="utf-8"))
            subtools = summary_payload.get("subtools")
            self.assertIsInstance(subtools, list)
            verify_rows = [row for row in subtools if isinstance(row, dict) and row.get("name") == "phase2_e2_verify_bundle"]
            self.assertEqual(len(verify_rows), 1)
            verify_cmd = [str(x) for x in verify_rows[0].get("command", [])]
            self.assertIn("--validate-schemas", verify_cmd)
            self.assertNotIn("--lint-portable-content", verify_cmd)

            with zipfile.ZipFile(zip1, "r") as zf:
                names = sorted(zf.namelist())
                self.assertIn("reviewer_pack/README.md", names)
                self.assertIn("reviewer_pack/REVIEWER_GUIDE.md", names)
                self.assertIn("reviewer_pack/boltzmann_export.sh", names)
                self.assertIn("reviewer_pack/boltzmann_run_class.sh", names)
                self.assertIn("reviewer_pack/boltzmann_run_camb.sh", names)
                self.assertIn("reviewer_pack/boltzmann_results.sh", names)
                self.assertIn("reviewer_pack/manifest.json", names)
                self.assertIn("reviewer_pack/bundle/bundle.zip", names)
                self.assertIn("reviewer_pack/bundle/bundle.sha256", names)
                self.assertIn("reviewer_pack/bundle/LINEAGE.json", names)
                self.assertIn("reviewer_pack/repo_snapshot/repo_share.zip", names)
                self.assertIn("reviewer_pack/repo_snapshot/repo_share.sha256", names)
                self.assertIn("reviewer_pack/paper_assets/paper_assets_manifest.json", names)
                self.assertIn("reviewer_pack/verify/verify.txt", names)
                self.assertIn("reviewer_pack/verify/verify.json", names)
                self.assertIn("reviewer_pack/docs/project_status_and_roadmap.md", names)
                self.assertIn("reviewer_pack/docs/external_reviewer_feedback.md", names)
                self.assertIn("reviewer_pack/docs/early_time_e2_status.md", names)
                self.assertIn("reviewer_pack/docs/structure_formation_status.md", names)
                self.assertIn("reviewer_pack/docs/perturbations_and_dm_scope.md", names)
                self.assertIn("reviewer_pack/docs/sigma_field_origin_status.md", names)
                guide_text = zf.read("reviewer_pack/REVIEWER_GUIDE.md").decode("utf-8")
                self.assertIn("## What to read first", guide_text)
                self.assertIn("## Boltzmann export (perturbations)", guide_text)
                self.assertIn("docs/project_status_and_roadmap.md", guide_text)
                self.assertIn("docs/external_reviewer_feedback.md", guide_text)
                self.assertIn("docs/perturbations_and_dm_scope.md", guide_text)
                script_text = zf.read("reviewer_pack/boltzmann_export.sh").decode("utf-8")
                self.assertIn("phase2_pt_boltzmann_export_pack.py", script_text)
                run_class_script_text = zf.read("reviewer_pack/boltzmann_run_class.sh").decode("utf-8")
                self.assertIn("phase2_pt_boltzmann_run_harness.py", run_class_script_text)
                run_camb_script_text = zf.read("reviewer_pack/boltzmann_run_camb.sh").decode("utf-8")
                self.assertIn("phase2_pt_boltzmann_run_harness.py", run_camb_script_text)
                results_script_text = zf.read("reviewer_pack/boltzmann_results.sh").decode("utf-8")
                self.assertIn("phase2_pt_boltzmann_results_pack.py", results_script_text)

                forbidden_fragments = (
                    "/.git/",
                    "/.venv/",
                    "/__macosx/",
                    "/site-packages/",
                    ".ds_store",
                    "/v11.0.0/archive/packs/",
                    "/v11.0.0/b/",
                    "submission_bundle",
                    "referee_pack",
                    "toe_bundle",
                    "publication_bundle",
                )
                for name in names:
                    lowered = "/" + name.lower().strip("/") + "/"
                    for fragment in forbidden_fragments:
                        self.assertNotIn(fragment, lowered, msg=name)

                manifest = json.loads(zf.read("reviewer_pack/manifest.json").decode("utf-8"))
                self.assertEqual(list(manifest.keys()), sorted(manifest.keys()))
                self.assertEqual(manifest.get("tool_marker"), "phase2_e2_reviewer_pack_v1")
                self.assertEqual(manifest.get("bundle", {}).get("basename"), "bundle.zip")

                artifact_rows = manifest.get("artifacts")
                self.assertIsInstance(artifact_rows, list)
                by_path = {str(row.get("path")): row for row in artifact_rows if isinstance(row, dict)}
                self.assertIn("bundle/bundle.zip", by_path)
                self.assertIn("repo_snapshot/repo_share.zip", by_path)
                self.assertIn("paper_assets/paper_assets_manifest.json", by_path)
                self.assertIn("verify/verify.txt", by_path)
                for row in by_path.values():
                    if "sha256" in row:
                        self.assertRegex(str(row.get("sha256")), r"^[0-9a-f]{64}$")

            with zipfile.ZipFile(zip1, "r") as zf1, zipfile.ZipFile(zip2, "r") as zf2:
                self.assertEqual(
                    zf1.read("reviewer_pack/REVIEWER_GUIDE.md"),
                    zf2.read("reviewer_pack/REVIEWER_GUIDE.md"),
                )


if __name__ == "__main__":
    unittest.main()
