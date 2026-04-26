import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M43BundleIncludesPaperAssetsToy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[str]) -> None:
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _make_input_shards(self, td_path: Path) -> tuple[Path, Path]:
        shard_a = td_path / "shard_a.jsonl"
        shard_b = td_path / "shard_b.jsonl"
        self._write_jsonl(
            shard_a,
            [
                json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                json.dumps(
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
                    }
                ),
            ],
        )
        self._write_jsonl(
            shard_b,
            [
                json.dumps(
                    {
                        "params_hash": "hash_b",
                        "status": "ok",
                        "model": "lcdm",
                        "chi2_total": 4.8,
                        "chi2_cmb": 2.4,
                        "drift_metric": 0.6,
                        "drift_sign_z2_5": True,
                        "microphysics_plausible_ok": True,
                        "params": {"H0": 68.0, "Omega_m": 0.31},
                        "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.02, "r_d_scale": 1.01},
                    }
                ),
            ],
        )
        return shard_a, shard_b

    def _run_bundle(self, *, outdir: Path, shard_a: Path, shard_b: Path, paper_mode: str) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_bundle.py"
        cmd = [
            sys.executable,
            str(script),
            "--in",
            str(shard_a),
            "--in",
            str(shard_b),
            "--outdir",
            str(outdir),
            "--steps",
            "merge,pareto,paper_assets,manifest,meta",
            "--paper-assets",
            str(paper_mode),
        ]
        return self._run(cmd)

    def _run_verify(self, *, bundle_dir: Path) -> subprocess.CompletedProcess:
        verify_script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"
        cmd = [
            sys.executable,
            str(verify_script),
            "--bundle",
            str(bundle_dir),
            "--paper-assets",
            "require",
        ]
        return self._run(cmd)

    def test_bundle_with_paper_assets_data_and_snippets(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a, shard_b = self._make_input_shards(td_path)

            for mode in ("data", "snippets"):
                outdir = td_path / f"bundle_{mode}"
                proc = self._run_bundle(outdir=outdir, shard_a=shard_a, shard_b=shard_b, paper_mode=mode)
                output = (proc.stdout or "") + (proc.stderr or "")
                self.assertEqual(proc.returncode, 0, msg=output)

                pa_manifest = outdir / "paper_assets" / "paper_assets_manifest.json"
                drift_table = outdir / "paper_assets" / "paper_assets_cmb_e2_drift_constrained_closure_bound" / "tables" / "pareto_front.csv"
                knobs_table = outdir / "paper_assets" / "paper_assets_cmb_e2_closure_to_physical_knobs" / "tables" / "top_models_knobs.csv"
                self.assertTrue(pa_manifest.is_file(), msg=str(pa_manifest))
                self.assertTrue(drift_table.is_file(), msg=str(drift_table))
                self.assertTrue(knobs_table.is_file(), msg=str(knobs_table))

                if mode == "snippets":
                    snippet_md = (
                        outdir
                        / "paper_assets"
                        / "paper_assets_cmb_e2_drift_constrained_closure_bound"
                        / "snippets"
                        / "drift_closure_bound.md"
                    )
                    self.assertTrue(snippet_md.is_file(), msg=str(snippet_md))

                verify = self._run_verify(bundle_dir=outdir)
                self.assertEqual(verify.returncode, 0, msg=(verify.stdout or "") + (verify.stderr or ""))


if __name__ == "__main__":
    unittest.main()

