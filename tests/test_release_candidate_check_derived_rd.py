import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_catalog(path: Path, *, asset_name: str, sha: str) -> None:
    catalog = {
        "schema_version": 2,
        "artifacts": {
            "late_time": {
                "type": "late-time",
                "tier": "frozen",
                "tag": "vL",
                "release_url": "https://example.com/L",
                "asset": asset_name,
                "sha256": sha,
            },
            "submission": {
                "type": "submission",
                "tier": "frozen",
                "tag": "vS",
                "release_url": "https://example.com/S",
                "asset": asset_name,
                "sha256": sha,
            },
            "referee_pack": {
                "type": "referee",
                "tier": "recommended",
                "tag": "vR",
                "release_url": "https://example.com/R",
                "asset": asset_name,
                "sha256": sha,
            },
            "toe_bundle": {
                "type": "toe",
                "tier": "recommended",
                "tag": "vT",
                "release_url": "https://example.com/T",
                "asset": asset_name,
                "sha256": sha,
            },
        },
    }
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


def _run_rc(script: Path, *, catalog: Path, root: Path, out_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(script),
            "--catalog",
            str(catalog),
            "--artifacts-dir",
            str(root),
            "--skip-status-doc-check",
            "--skip-pointer-sot-lint",
            "--dry-run",
            "--out-dir",
            str(out_root),
            "--require-derived-rd",
        ],
        capture_output=True,
        text=True,
    )


class TestReleaseCandidateCheckDerivedRD(unittest.TestCase):
    def test_require_derived_rd_fails_when_bestfit_missing(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            r = _run_rc(script, catalog=catalog_path, root=td_p, out_root=td_p / "out")
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("derived-rd validation requested but no *_bestfit.json files found", out)

    def test_require_derived_rd_fails_when_mode_is_not_early(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            fit_dir = td_p / "out" / "late_time_fit"
            fit_dir.mkdir(parents=True, exist_ok=True)
            (fit_dir / "lcdm_bestfit.json").write_text(
                json.dumps(
                    {
                        "rd": {"rd_mode": "nuisance"},
                        "best": {
                            "parts": {
                                "bao": {
                                    "rd_mode": "nuisance",
                                    "rd_fit_mode": "profile",
                                    "rd_Mpc": 147.0,
                                    "rd_m": 147.0 * 3.085677581491367e22,
                                }
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            r = _run_rc(script, catalog=catalog_path, root=td_p, out_root=td_p / "out")
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("expected rd_mode='early'", out)

    def test_require_derived_rd_passes_with_valid_bestfit(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            fit_dir = td_p / "out" / "late_time_fit"
            fit_dir.mkdir(parents=True, exist_ok=True)
            (fit_dir / "lcdm_bestfit.json").write_text(
                json.dumps(
                    {
                        "rd": {
                            "rd_mode": "early",
                            "rd_Mpc": 147.0,
                            "rd_m": 147.0 * 3.085677581491367e22,
                        },
                        "best": {
                            "parts": {
                                "bao": {
                                    "rd_mode": "early",
                                    "rd_fit_mode": "fixed",
                                    "rd_Mpc": 147.0,
                                    "rd_m": 147.0 * 3.085677581491367e22,
                                }
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            r = _run_rc(script, catalog=catalog_path, root=td_p, out_root=td_p / "out")
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("validate_derived_rd_outputs", out)


if __name__ == "__main__":
    unittest.main()
