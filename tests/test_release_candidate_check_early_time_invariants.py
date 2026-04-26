from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

INVARIANTS_SCHEMA = "phase2.m8.early_time_invariants_report.v1"
MODEL_SCHEMA = 1
REQUIRED_CHECK_IDS = (
    "finite_positive_core",
    "alias_theta_star_100theta_star",
    "identity_lA_equals_pi_over_theta_star",
    "identity_rd_m_equals_rd_Mpc_times_MPC_SI",
)


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
            "--require-early-time-invariants",
        ],
        capture_output=True,
        text=True,
    )


def _model_payload(*, failing_check: str | None = None, missing_check: str | None = None) -> dict:
    checks = {}
    for check_id in REQUIRED_CHECK_IDS:
        if check_id == missing_check:
            continue
        is_fail = check_id == failing_check
        checks[check_id] = {
            "ok": not is_fail,
            "status": "FAIL" if is_fail else "PASS",
            "required": True,
            "required_keys": [],
            "missing_keys": [],
            "violations": [f"{check_id} failed"] if is_fail else [],
        }
    missing_required = [missing_check] if missing_check is not None else []
    errors: list[str] = []
    if failing_check is not None:
        errors.append(f"required check failed: {failing_check}")
    if missing_check is not None:
        errors.append(f"required check missing: {missing_check}")
    return {
        "schema_version": MODEL_SCHEMA,
        "ok": len(errors) == 0,
        "strict": True,
        "required_check_ids": list(REQUIRED_CHECK_IDS),
        "missing_required": missing_required,
        "errors": errors,
        "violations": list(errors),
        "checks": checks,
        "checked": {"derived_keys": []},
        "meta": {"source_key_count": 4},
    }


def _top_payload(model_payload: dict) -> dict:
    model_ok = bool(model_payload.get("ok"))
    return {
        "schema_version": INVARIANTS_SCHEMA,
        "strict": True,
        "required_check_ids": list(REQUIRED_CHECK_IDS),
        "model_invariants_schema_version": MODEL_SCHEMA,
        "ok": model_ok,
        "summary": {
            "model_count": 1,
            "failing_model_count": 0 if model_ok else 1,
            "violation_count": len(model_payload.get("violations") or []),
            "missing_required_count": len(model_payload.get("missing_required") or []),
        },
        "checks": {"lcdm": model_payload},
    }


class TestReleaseCandidateCheckEarlyTimeInvariants(unittest.TestCase):
    def test_require_invariants_fails_when_missing(self):
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
            self.assertIn("required early-time invariants report is missing", out)

    def test_require_invariants_fails_when_ok_is_false(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            out_root = td_p / "out"
            early_time = out_root / "early_time"
            early_time.mkdir(parents=True, exist_ok=True)
            payload = _top_payload(_model_payload(failing_check=REQUIRED_CHECK_IDS[0]))
            (early_time / "numerics_invariants_report.json").write_text(
                json.dumps(payload) + "\n",
                encoding="utf-8",
            )

            r = _run_rc(script, catalog=catalog_path, root=td_p, out_root=out_root)
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("report indicates failure", out)

    def test_require_invariants_fails_when_required_check_missing(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            out_root = td_p / "out"
            early_time = out_root / "early_time"
            early_time.mkdir(parents=True, exist_ok=True)
            payload = _top_payload(_model_payload(missing_check=REQUIRED_CHECK_IDS[1]))
            payload["ok"] = True
            payload["summary"]["failing_model_count"] = 0
            (early_time / "numerics_invariants_report.json").write_text(
                json.dumps(payload) + "\n",
                encoding="utf-8",
            )

            r = _run_rc(script, catalog=catalog_path, root=td_p, out_root=out_root)
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("required checks failed", out)

    def test_require_invariants_passes_with_valid_file(self):
        script = SCRIPTS / "release_candidate_check.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            asset = td_p / "toy.zip"
            asset.write_bytes(b"toy")
            catalog_path = td_p / "catalog.json"
            _write_catalog(catalog_path, asset_name=asset.name, sha=_sha256_file(asset))

            out_root = td_p / "out"
            early_time = out_root / "early_time"
            early_time.mkdir(parents=True, exist_ok=True)
            payload = _top_payload(_model_payload())
            (early_time / "numerics_invariants_report.json").write_text(
                json.dumps(payload) + "\n",
                encoding="utf-8",
            )

            r = _run_rc(script, catalog=catalog_path, root=td_p, out_root=out_root)
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("validate_early_time_numerics_invariants", out)


if __name__ == "__main__":
    unittest.main()
