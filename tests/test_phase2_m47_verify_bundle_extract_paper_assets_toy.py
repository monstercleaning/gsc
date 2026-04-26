import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M47VerifyBundleExtractPaperAssetsToy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _snapshot_tree(self, root: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                out[rel] = _sha256(path)
        return out

    def _build_bundle_dir(self, td_path: Path) -> Path:
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

        outdir = td_path / "bundle_dir"
        bundle_script = ROOT / "scripts" / "phase2_e2_bundle.py"
        proc = self._run(
            [
                sys.executable,
                str(bundle_script),
                "--in",
                str(shard_a),
                "--in",
                str(shard_b),
                "--outdir",
                str(outdir),
                "--steps",
                "merge,pareto,paper_assets,manifest,meta",
                "--paper-assets",
                "data",
            ]
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)
        self.assertTrue((outdir / "manifest.json").is_file())
        return outdir

    def test_extract_paper_assets_is_idempotent_and_writes_expected_dirs(self):
        verify_script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"
        self.assertTrue(verify_script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_dir = self._build_bundle_dir(td_path)
            extract_root = td_path / "extract_root"

            cmd = [
                sys.executable,
                str(verify_script),
                "--bundle",
                str(bundle_dir),
                "--paper-assets",
                "require",
                "--extract-paper-assets",
                "--extract-root",
                str(extract_root),
                "--extract-mode",
                "clean_overwrite",
            ]

            first = self._run(cmd)
            out_first = (first.stdout or "") + (first.stderr or "")
            self.assertEqual(first.returncode, 0, msg=out_first)

            drift_dir = extract_root / "v11.0.0" / "paper_assets_cmb_e2_drift_constrained_closure_bound"
            knobs_dir = extract_root / "v11.0.0" / "paper_assets_cmb_e2_closure_to_physical_knobs"
            self.assertTrue(drift_dir.is_dir(), msg=str(drift_dir))
            self.assertTrue(knobs_dir.is_dir(), msg=str(knobs_dir))

            drift_snippet = drift_dir / "snippets" / "phase2_e2_appendix.tex"
            knobs_snippet = knobs_dir / "snippets" / "phase2_e2_appendix.tex"
            drift_summary_snippet = drift_dir / "snippets" / "phase2_e2_summary.tex"
            drift_best_candidates_tex = drift_dir / "snippets" / "phase2_e2_best_candidates.tex"
            drift_best_candidates_md = drift_dir / "snippets" / "phase2_e2_best_candidates.md"
            drift_table_snippet = drift_dir / "snippets" / "phase2_e2_drift_table.tex"
            drift_tension_snippet_tex = drift_dir / "snippets" / "phase2_e2_cmb_tension.tex"
            drift_tension_snippet_md = drift_dir / "snippets" / "phase2_e2_cmb_tension.md"
            drift_audit_snippet = drift_dir / "snippets" / "phase2_e2_scan_audit.tex"
            drift_sf_rsd_snippet_tex = drift_dir / "snippets" / "phase2_sf_rsd_summary.tex"
            drift_sf_rsd_snippet_md = drift_dir / "snippets" / "phase2_sf_rsd_summary.md"
            drift_sf_fsigma8_snippet_tex = drift_dir / "snippets" / "phase2_sf_fsigma8.tex"
            drift_sf_fsigma8_snippet_md = drift_dir / "snippets" / "phase2_sf_fsigma8.md"
            drift_rg_flow_snippet_tex = drift_dir / "snippets" / "phase2_rg_flow_table.tex"
            drift_rg_flow_snippet_md = drift_dir / "snippets" / "phase2_rg_flow_table.md"
            drift_rg_pade_snippet_tex = drift_dir / "snippets" / "phase2_rg_pade_fit.tex"
            drift_rg_pade_snippet_md = drift_dir / "snippets" / "phase2_rg_pade_fit.md"
            drift_all_snippet_tex = drift_dir / "snippets" / "phase2_e2_all.tex"
            drift_all_snippet_md = drift_dir / "snippets" / "phase2_e2_all.md"
            knobs_consistency_json = knobs_dir / "consistency" / "CONSISTENCY_REPORT.json"
            knobs_consistency_md = knobs_dir / "consistency" / "CONSISTENCY_REPORT.md"
            self.assertTrue(drift_snippet.is_file(), msg=str(drift_snippet))
            self.assertTrue(knobs_snippet.is_file(), msg=str(knobs_snippet))
            self.assertTrue(drift_summary_snippet.is_file(), msg=str(drift_summary_snippet))
            self.assertTrue(drift_best_candidates_tex.is_file(), msg=str(drift_best_candidates_tex))
            self.assertTrue(drift_best_candidates_md.is_file(), msg=str(drift_best_candidates_md))
            self.assertTrue(drift_table_snippet.is_file(), msg=str(drift_table_snippet))
            self.assertTrue(drift_tension_snippet_tex.is_file(), msg=str(drift_tension_snippet_tex))
            self.assertTrue(drift_tension_snippet_md.is_file(), msg=str(drift_tension_snippet_md))
            self.assertTrue(drift_audit_snippet.is_file(), msg=str(drift_audit_snippet))
            self.assertTrue(drift_sf_rsd_snippet_tex.is_file(), msg=str(drift_sf_rsd_snippet_tex))
            self.assertTrue(drift_sf_rsd_snippet_md.is_file(), msg=str(drift_sf_rsd_snippet_md))
            self.assertTrue(drift_sf_fsigma8_snippet_tex.is_file(), msg=str(drift_sf_fsigma8_snippet_tex))
            self.assertTrue(drift_sf_fsigma8_snippet_md.is_file(), msg=str(drift_sf_fsigma8_snippet_md))
            self.assertTrue(drift_rg_flow_snippet_tex.is_file(), msg=str(drift_rg_flow_snippet_tex))
            self.assertTrue(drift_rg_flow_snippet_md.is_file(), msg=str(drift_rg_flow_snippet_md))
            self.assertTrue(drift_rg_pade_snippet_tex.is_file(), msg=str(drift_rg_pade_snippet_tex))
            self.assertTrue(drift_rg_pade_snippet_md.is_file(), msg=str(drift_rg_pade_snippet_md))
            self.assertTrue(drift_all_snippet_tex.is_file(), msg=str(drift_all_snippet_tex))
            self.assertTrue(drift_all_snippet_md.is_file(), msg=str(drift_all_snippet_md))
            self.assertTrue(knobs_consistency_json.is_file(), msg=str(knobs_consistency_json))
            self.assertTrue(knobs_consistency_md.is_file(), msg=str(knobs_consistency_md))
            self.assertIn(
                "phase2_e2_best_candidates_snippet_v2",
                drift_best_candidates_tex.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_e2_best_candidates_snippet_v2",
                drift_best_candidates_md.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_rg_flow_table_snippet_v1",
                drift_rg_flow_snippet_tex.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_rg_flow_table_snippet_v1",
                drift_rg_flow_snippet_md.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_sf_fsigma8_snippet_v1",
                drift_sf_fsigma8_snippet_tex.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_sf_fsigma8_snippet_v1",
                drift_sf_fsigma8_snippet_md.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_rg_pade_fit_snippet_v1",
                drift_rg_pade_snippet_tex.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_rg_pade_fit_snippet_v1",
                drift_rg_pade_snippet_md.read_text(encoding="utf-8"),
            )

            snapshot_a = self._snapshot_tree(extract_root)
            self.assertGreater(len(snapshot_a), 0)

            second = self._run(cmd)
            out_second = (second.stdout or "") + (second.stderr or "")
            self.assertEqual(second.returncode, 0, msg=out_second)
            snapshot_b = self._snapshot_tree(extract_root)
            self.assertEqual(snapshot_a, snapshot_b)


if __name__ == "__main__":
    unittest.main()
