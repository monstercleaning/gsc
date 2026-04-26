#!/usr/bin/env python3
"""One-command offline release-candidate check for canonical artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shlex
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence

from bundle_tex_drift_detector import compare_bundle_tex_vs_repo
from _outdir import resolve_outdir, resolve_path_under_outdir
import verify_all_canonical_artifacts as verify_all


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
DEFAULT_CATALOG = V101_DIR / "canonical_artifacts.json"
SCRIPTS_DIR = Path(__file__).resolve().parent
CMB_REPORT_SCHEMA_VERSION = "phase2.m4.cmb_priors_report.v1"
EARLY_TIME_INVARIANTS_SCHEMA_VERSION = "phase2.m8.early_time_invariants_report.v1"
EARLY_TIME_MODEL_INVARIANTS_SCHEMA_VERSION = 1
EARLY_TIME_REQUIRED_CHECK_IDS = (
    "finite_positive_core",
    "alias_theta_star_100theta_star",
    "identity_lA_equals_pi_over_theta_star",
    "identity_rd_m_equals_rd_Mpc_times_MPC_SI",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_json_report(target: str, payload: Dict[str, Any]) -> None:
    if "steps" in payload and "summary" not in payload:
        steps = payload.get("steps") or []
        payload["summary"] = {
            "step_count": len(steps),
            "pass_count": sum(1 for s in steps if s.get("status") == "PASS"),
            "fail_count": sum(1 for s in steps if s.get("status") != "PASS"),
            "duration_sec_total": round(sum(float(s.get("duration_sec", 0.0)) for s in steps), 6),
        }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if target == "-":
        sys.stdout.write(text)
        return
    out = Path(target).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def _run_step(name: str, cmd: Sequence[str], step_log: list[Dict[str, Any]] | None = None) -> int:
    print(f"[step] {name}")
    print("  $ " + " ".join(cmd))
    t0 = time.monotonic()
    started = _now_utc()
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    finished = _now_utc()
    dur = round(time.monotonic() - t0, 6)
    if r.returncode != 0:
        print(f"[fail] {name}")
        if out:
            print(out)
        if step_log is not None:
            step_log.append(
                {
                    "name": name,
                    "cmd": list(cmd),
                    "status": "FAIL",
                    "exit_code": r.returncode,
                    "started_utc": started,
                    "finished_utc": finished,
                    "duration_sec": dur,
                }
            )
        return r.returncode
    print(f"[ok] {name}")
    if step_log is not None:
        step_log.append(
            {
                "name": name,
                "cmd": list(cmd),
                "status": "PASS",
                "exit_code": 0,
                "started_utc": started,
                "finished_utc": finished,
                "duration_sec": dur,
            }
        )
    return 0


def _resolve_rc_entries(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    artifacts = catalog.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("catalog.artifacts must be an object")

    late = artifacts.get("late_time")
    submission = artifacts.get("submission")
    referee = artifacts.get("referee_pack")
    toe = artifacts.get("toe_bundle")
    if not all(isinstance(v, dict) for v in (late, submission, referee, toe)):
        raise ValueError("catalog artifacts must define late_time/submission/referee_pack/toe_bundle objects")

    return {
        "late_time": dict(late),
        "submission": dict(submission),
        "referee_pack": dict(referee),
        "toe_bundle": dict(toe),
    }


def _print_required(entries: Dict[str, Dict[str, Any]], artifacts_dir: Path) -> None:
    print("Required canonical artifacts (from catalog):")
    for key in ("late_time", "submission", "referee_pack", "toe_bundle"):
        rec = entries[key]
        asset = str(rec["asset"])
        resolved = verify_all._resolve_asset_path(artifacts_dir, asset)
        print(f"- {key}")
        print(f"  asset: {asset}")
        print(f"  expected_sha256: {rec['sha256']}")
        print(f"  tag: {rec['tag']}")
        print(f"  release: {rec['release_url']}")
        print(f"  resolved_path: {resolved}")


def _check_required_files_exist(entries: Dict[str, Dict[str, Any]], artifacts_dir: Path) -> list[Dict[str, str]]:
    missing: list[Dict[str, str]] = []
    for key in ("late_time", "submission", "referee_pack", "toe_bundle"):
        rec = entries[key]
        asset = str(rec["asset"])
        resolved = verify_all._resolve_asset_path(artifacts_dir, asset)
        if not resolved.is_file():
            missing.append(
                {
                    "id": key,
                    "asset": asset,
                    "expected_sha256": str(rec["sha256"]),
                    "tag": str(rec["tag"]),
                    "release_url": str(rec["release_url"]),
                    "looked_at": str(resolved),
                }
            )
            print("ERROR: missing required canonical artifact", file=sys.stderr)
            print(f"  id: {key}", file=sys.stderr)
            print(f"  expected_asset: {asset}", file=sys.stderr)
            print(f"  expected_sha256: {rec['sha256']}", file=sys.stderr)
            print(f"  tag: {rec['tag']}", file=sys.stderr)
            print(f"  release: {rec['release_url']}", file=sys.stderr)
            print(f"  looked_at: {resolved}", file=sys.stderr)
    if missing:
        print("To fetch missing canonical artifacts:", file=sys.stderr)
        print(
            "  bash v11.0.0/scripts/fetch_canonical_artifacts.sh "
            f"--artifacts-dir {shlex.quote(str(artifacts_dir))} --fetch-missing",
            file=sys.stderr,
        )
    return missing


def _run_bundle_vs_repo_tex_check(submission_zip: Path, repo_tex: Path) -> Dict[str, Any]:
    print("[step] bundle_vs_repo_tex_drift")
    result = compare_bundle_tex_vs_repo(submission_zip, repo_tex)
    if result.get("match"):
        print("[ok] bundle_vs_repo_tex_drift")
        print(f"  sha_bundle: {result.get('sha_bundle')}")
        print(f"  sha_repo:   {result.get('sha_repo')}")
        return result

    print("[warn] bundle_vs_repo_tex_drift")
    if result.get("warning"):
        print(f"  warning: {result['warning']}")
    print(f"  sha_bundle: {result.get('sha_bundle')}")
    print(f"  sha_repo:   {result.get('sha_repo')}")
    for cmd in result.get("hint_cmds", []):
        print(f"  hint: {cmd}")
    return result


def _run_cmb_reports_check_step(
    *,
    report_json: Path,
    report_csv: Path,
    require_reports: bool,
    step_log: list[Dict[str, Any]],
) -> tuple[int, Dict[str, Any]]:
    name = "validate_early_time_cmb_reports"
    print(f"[step] {name}")
    print(f"  json: {report_json}")
    print(f"  csv:  {report_csv}")
    t0 = time.monotonic()
    started = _now_utc()
    payload: Dict[str, Any] = {
        "required": bool(require_reports),
        "json_path": str(report_json),
        "csv_path": str(report_csv),
        "json_exists": report_json.is_file(),
        "csv_exists": report_csv.is_file(),
    }

    if not require_reports and not payload["json_exists"] and not payload["csv_exists"]:
        print(f"[ok] {name} (not requested; reports absent)")
        payload["status"] = "SKIP"
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-cmb-reports", str(report_json), str(report_csv)],
                "status": "PASS",
                "exit_code": 0,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 0, payload

    if not payload["json_exists"] or not payload["csv_exists"]:
        print("ERROR: required early-time CMB reports are missing", file=sys.stderr)
        if not payload["json_exists"]:
            print(f"  missing JSON: {report_json}", file=sys.stderr)
        if not payload["csv_exists"]:
            print(f"  missing CSV:  {report_csv}", file=sys.stderr)
        payload["status"] = "FAIL"
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-cmb-reports", str(report_json), str(report_csv)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload

    try:
        obj = json.loads(report_json.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: failed to parse CMB report JSON: {exc}", file=sys.stderr)
        payload["status"] = "FAIL"
        payload["error"] = f"failed to parse JSON: {exc}"
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-cmb-reports", str(report_json), str(report_csv)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload

    schema = str(obj.get("schema_version", ""))
    if schema != CMB_REPORT_SCHEMA_VERSION:
        print("ERROR: unexpected CMB report schema version", file=sys.stderr)
        print(f"  got:      {schema!r}", file=sys.stderr)
        print(f"  expected: {CMB_REPORT_SCHEMA_VERSION!r}", file=sys.stderr)
        payload["status"] = "FAIL"
        payload["schema_version"] = schema
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-cmb-reports", str(report_json), str(report_csv)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload

    with report_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        first_row = next(reader, None)
    if not header:
        print(f"ERROR: CMB report CSV is empty: {report_csv}", file=sys.stderr)
        payload["status"] = "FAIL"
        payload["schema_version"] = schema
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-cmb-reports", str(report_json), str(report_csv)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload
    if first_row is None:
        print(f"ERROR: CMB report CSV has no data rows: {report_csv}", file=sys.stderr)
        payload["status"] = "FAIL"
        payload["schema_version"] = schema
        payload["csv_header"] = list(header)
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-cmb-reports", str(report_json), str(report_csv)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload

    payload["status"] = "PASS"
    payload["schema_version"] = schema
    payload["csv_header"] = list(header)
    payload["model_count"] = int((obj.get("summary") or {}).get("model_count", 0))
    print(f"[ok] {name}")
    step_log.append(
        {
            "name": name,
            "cmd": ["validate-cmb-reports", str(report_json), str(report_csv)],
            "status": "PASS",
            "exit_code": 0,
            "started_utc": started,
            "finished_utc": _now_utc(),
            "duration_sec": round(time.monotonic() - t0, 6),
        }
    )
    return 0, payload


def _run_early_time_invariants_check_step(
    *,
    report_json: Path,
    require_report: bool,
    step_log: list[Dict[str, Any]],
) -> tuple[int, Dict[str, Any]]:
    name = "validate_early_time_numerics_invariants"
    print(f"[step] {name}")
    print(f"  json: {report_json}")
    t0 = time.monotonic()
    started = _now_utc()
    payload: Dict[str, Any] = {
        "required": bool(require_report),
        "json_path": str(report_json),
        "json_exists": report_json.is_file(),
    }

    if not require_report and not payload["json_exists"]:
        print(f"[ok] {name} (not requested; report absent)")
        payload["status"] = "SKIP"
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-early-time-invariants", str(report_json)],
                "status": "PASS",
                "exit_code": 0,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 0, payload

    if not payload["json_exists"]:
        print("ERROR: required early-time invariants report is missing", file=sys.stderr)
        print(f"  missing JSON: {report_json}", file=sys.stderr)
        payload["status"] = "FAIL"
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-early-time-invariants", str(report_json)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload

    def _finish(status: str, exit_code: int) -> tuple[int, Dict[str, Any]]:
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-early-time-invariants", str(report_json)],
                "status": status,
                "exit_code": int(exit_code),
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return exit_code, payload

    def _fail(msg: str) -> tuple[int, Dict[str, Any]]:
        print(f"ERROR: {msg}", file=sys.stderr)
        payload["status"] = "FAIL"
        payload["error"] = msg
        return _finish("FAIL", 2)

    try:
        obj = json.loads(report_json.read_text(encoding="utf-8"))
    except Exception as exc:
        return _fail(f"failed to parse early-time invariants JSON: {exc}")
    if not isinstance(obj, dict):
        return _fail("early-time invariants JSON root must be an object")

    schema = str(obj.get("schema_version", ""))
    if schema != EARLY_TIME_INVARIANTS_SCHEMA_VERSION:
        print("ERROR: unexpected early-time invariants schema version", file=sys.stderr)
        print(f"  got:      {schema!r}", file=sys.stderr)
        print(f"  expected: {EARLY_TIME_INVARIANTS_SCHEMA_VERSION!r}", file=sys.stderr)
        payload["status"] = "FAIL"
        payload["schema_version"] = schema
        payload["error"] = "unexpected schema version"
        return _finish("FAIL", 2)

    strict = obj.get("strict")
    if strict is not True:
        return _fail(f"early-time invariants report must be strict=true, got {strict!r}")

    report_required_raw = obj.get("required_check_ids")
    if not isinstance(report_required_raw, list):
        return _fail("early-time invariants report missing required_check_ids list")
    report_required = {str(x) for x in report_required_raw}
    missing_report_required = [cid for cid in EARLY_TIME_REQUIRED_CHECK_IDS if cid not in report_required]
    if missing_report_required:
        return _fail(
            "early-time invariants report missing required check ids: "
            + ", ".join(missing_report_required)
        )

    model_schema = obj.get("model_invariants_schema_version")
    try:
        model_schema_i = int(model_schema)
    except Exception:
        return _fail(f"invalid model_invariants_schema_version: {model_schema!r}")
    if model_schema_i != EARLY_TIME_MODEL_INVARIANTS_SCHEMA_VERSION:
        return _fail(
            "unexpected model_invariants_schema_version: "
            f"{model_schema_i} (expected {EARLY_TIME_MODEL_INVARIANTS_SCHEMA_VERSION})"
        )

    if bool(obj.get("ok")) is not True:
        return _fail("early-time invariants report indicates failure (ok != true)")

    summary = obj.get("summary")
    if not isinstance(summary, dict):
        return _fail("early-time invariants report missing summary object")

    checks = obj.get("checks")
    if not isinstance(checks, dict) or not checks:
        return _fail("early-time invariants report missing non-empty checks object")

    per_model_failures: list[str] = []
    for model_id, model_payload in checks.items():
        model_label = str(model_id)
        if not isinstance(model_payload, dict):
            per_model_failures.append(f"{model_label}: model payload is not an object")
            continue
        if int(model_payload.get("schema_version", -1)) != EARLY_TIME_MODEL_INVARIANTS_SCHEMA_VERSION:
            per_model_failures.append(
                f"{model_label}: schema_version mismatch "
                f"(got {model_payload.get('schema_version')!r})"
            )
        if model_payload.get("strict") is not True:
            per_model_failures.append(f"{model_label}: strict must be true")
        model_required_raw = model_payload.get("required_check_ids")
        if not isinstance(model_required_raw, list):
            per_model_failures.append(f"{model_label}: missing required_check_ids list")
            model_required: set[str] = set()
        else:
            model_required = {str(x) for x in model_required_raw}
        missing_model_required = [cid for cid in EARLY_TIME_REQUIRED_CHECK_IDS if cid not in model_required]
        if missing_model_required:
            per_model_failures.append(
                f"{model_label}: missing required_check_ids: {', '.join(missing_model_required)}"
            )

        model_checks = model_payload.get("checks")
        if not isinstance(model_checks, dict):
            per_model_failures.append(f"{model_label}: missing checks object")
            continue
        for check_id in EARLY_TIME_REQUIRED_CHECK_IDS:
            check_payload = model_checks.get(check_id)
            if not isinstance(check_payload, dict):
                per_model_failures.append(f"{model_label}: missing required check '{check_id}'")
                continue
            status = str(check_payload.get("status", "")).upper()
            ok = bool(check_payload.get("ok"))
            if not ok or status != "PASS":
                per_model_failures.append(
                    f"{model_label}: check '{check_id}' failed (ok={ok}, status={status or 'UNKNOWN'})"
                )

    if per_model_failures:
        print("ERROR: early-time invariants required checks failed", file=sys.stderr)
        for row in per_model_failures:
            print(f"  - {row}", file=sys.stderr)
        payload["status"] = "FAIL"
        payload["schema_version"] = schema
        payload["ok"] = False
        payload["required_check_ids"] = list(EARLY_TIME_REQUIRED_CHECK_IDS)
        payload["failures"] = per_model_failures
        payload["error"] = "required invariants checks failed"
        return _finish("FAIL", 2)

    payload["status"] = "PASS"
    payload["schema_version"] = schema
    payload["ok"] = True
    payload["strict"] = True
    payload["required_check_ids"] = list(EARLY_TIME_REQUIRED_CHECK_IDS)
    payload["model_invariants_schema_version"] = int(model_schema_i)
    payload["summary"] = {
        "model_count": int(summary.get("model_count", 0)),
        "failing_model_count": int(summary.get("failing_model_count", 0)),
        "violation_count": int(summary.get("violation_count", 0)),
        "missing_required_count": int(summary.get("missing_required_count", 0)),
    }
    print(f"[ok] {name}")
    return _finish("PASS", 0)


def _run_derived_rd_check_step(
    *,
    fit_dir: Path,
    require_derived_rd: bool,
    step_log: list[Dict[str, Any]],
) -> tuple[int, Dict[str, Any]]:
    name = "validate_derived_rd_outputs"
    print(f"[step] {name}")
    print(f"  fit_dir: {fit_dir}")
    t0 = time.monotonic()
    started = _now_utc()

    files = sorted(fit_dir.glob("*_bestfit.json")) if fit_dir.is_dir() else []
    payload: Dict[str, Any] = {
        "required": bool(require_derived_rd),
        "fit_dir": str(fit_dir),
        "fit_dir_exists": fit_dir.is_dir(),
        "bestfit_count": len(files),
    }

    if not require_derived_rd and not files:
        payload["status"] = "SKIP"
        print(f"[ok] {name} (not requested; no bestfit files found)")
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-derived-rd", str(fit_dir)],
                "status": "PASS",
                "exit_code": 0,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 0, payload

    if require_derived_rd and not files:
        print("ERROR: derived-rd validation requested but no *_bestfit.json files found", file=sys.stderr)
        print(f"  fit_dir: {fit_dir}", file=sys.stderr)
        payload["status"] = "FAIL"
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-derived-rd", str(fit_dir)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload

    failures: list[Dict[str, Any]] = []
    checked: list[Dict[str, Any]] = []
    for path in files:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append({"bestfit_file": str(path), "errors": [f"failed to parse JSON: {exc}"]})
            continue

        rd_block = obj.get("rd") if isinstance(obj, dict) else None
        if not isinstance(rd_block, dict):
            rd_block = {}
        best_block = obj.get("best") if isinstance(obj, dict) else None
        best_parts = best_block.get("parts") if isinstance(best_block, dict) else None
        bao_block = best_parts.get("bao") if isinstance(best_parts, dict) else None
        if not isinstance(bao_block, dict):
            bao_block = {}

        errors: list[str] = []
        rd_mode = str(bao_block.get("rd_mode", rd_block.get("rd_mode", ""))).strip().lower()
        if rd_mode != "early":
            errors.append(f"expected rd_mode='early' but got {rd_mode!r}")

        rd_fit_mode = str(bao_block.get("rd_fit_mode", "")).strip().lower()
        if rd_fit_mode != "fixed":
            errors.append(f"expected bao.rd_fit_mode='fixed' but got {rd_fit_mode!r}")

        rd_mpc_raw = bao_block.get("rd_Mpc", rd_block.get("rd_Mpc"))
        rd_m_raw = bao_block.get("rd_m", rd_block.get("rd_m"))
        try:
            rd_mpc = float(rd_mpc_raw)
            if not (math.isfinite(rd_mpc) and rd_mpc > 0.0):
                raise ValueError("non-positive")
        except Exception:
            errors.append(f"expected positive rd_Mpc but got {rd_mpc_raw!r}")
            rd_mpc = float("nan")
        try:
            rd_m = float(rd_m_raw)
            if not (math.isfinite(rd_m) and rd_m > 0.0):
                raise ValueError("non-positive")
        except Exception:
            errors.append(f"expected positive rd_m but got {rd_m_raw!r}")
            rd_m = float("nan")

        if errors:
            failures.append({"bestfit_file": str(path), "errors": errors})
            continue
        checked.append(
            {
                "bestfit_file": str(path),
                "rd_mode": rd_mode,
                "rd_fit_mode": rd_fit_mode,
                "rd_Mpc": rd_mpc,
                "rd_m": rd_m,
            }
        )

    payload["checked"] = checked
    payload["failures"] = failures
    if failures:
        print("ERROR: derived-rd validation failed", file=sys.stderr)
        for row in failures:
            print(f"  bestfit: {row.get('bestfit_file')}", file=sys.stderr)
            for err in row.get("errors") or []:
                print(f"    - {err}", file=sys.stderr)
        payload["status"] = "FAIL"
        step_log.append(
            {
                "name": name,
                "cmd": ["validate-derived-rd", str(fit_dir)],
                "status": "FAIL",
                "exit_code": 2,
                "started_utc": started,
                "finished_utc": _now_utc(),
                "duration_sec": round(time.monotonic() - t0, 6),
            }
        )
        return 2, payload

    payload["status"] = "PASS"
    print(f"[ok] {name}")
    step_log.append(
        {
            "name": name,
            "cmd": ["validate-derived-rd", str(fit_dir)],
            "status": "PASS",
            "exit_code": 0,
            "started_utc": started,
            "finished_utc": _now_utc(),
            "duration_sec": round(time.monotonic() - t0, 6),
        }
    )
    return 0, payload


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="release_candidate_check",
        description="One-command offline RC validation for canonical submission/referee/toe artifacts.",
    )
    ap.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="outdir",
        type=Path,
        default=None,
        help="Output root (CLI > GSC_OUTDIR > v11.0.0/artifacts/release).",
    )
    ap.add_argument("--artifacts-dir", type=Path, default=Path.cwd())
    ap.add_argument("--skip-smoke-compile", action="store_true")
    ap.add_argument("--skip-arxiv-preflight", action="store_true")
    ap.add_argument("--skip-extracted-submission-lint", action="store_true")
    ap.add_argument("--skip-pointer-sot-lint", action="store_true")
    ap.add_argument("--skip-docs-claims-lint", action="store_true")
    ap.add_argument("--skip-status-doc-check", action="store_true")
    ap.add_argument(
        "--require-cmb-reports",
        action="store_true",
        help="Require early_time CMB report JSON/CSV under outdir and validate schema/content.",
    )
    ap.add_argument(
        "--require-early-time-invariants",
        action="store_true",
        help="Require early-time numerics invariants report JSON and validate strict schema + required checks.",
    )
    ap.add_argument(
        "--require-derived-rd",
        action="store_true",
        help="Require derived-rd metadata checks against *_bestfit.json under fit dir.",
    )
    ap.add_argument(
        "--derived-rd-fit-dir",
        type=Path,
        default=Path("late_time_fit"),
        help="Fit directory for derived-rd validation (relative paths resolve under outdir).",
    )
    ap.add_argument(
        "--cmb-report-json",
        type=Path,
        default=Path("early_time/cmb_priors_report.json"),
        help="Path to early-time CMB report JSON (relative paths resolve under outdir).",
    )
    ap.add_argument(
        "--cmb-report-csv",
        type=Path,
        default=Path("early_time/cmb_priors_table.csv"),
        help="Path to early-time CMB report CSV (relative paths resolve under outdir).",
    )
    ap.add_argument(
        "--early-time-invariants-report",
        type=Path,
        default=Path("early_time/numerics_invariants_report.json"),
        help="Path to early-time numerics invariants report JSON (relative paths resolve under outdir).",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--print-required", action="store_true", help="Print required artifact filenames/SHA/tag and exit")
    ap.add_argument(
        "--json",
        nargs="?",
        const="-",
        default=None,
        help="Write structured RC output JSON to PATH, or to stdout when used without value.",
    )
    args = ap.parse_args(argv)

    out_root = resolve_outdir(args.outdir, v101_dir=V101_DIR)
    print(f"[info] OUTDIR={out_root}")
    cmb_report_json = resolve_path_under_outdir(args.cmb_report_json, out_root=out_root)
    cmb_report_csv = resolve_path_under_outdir(args.cmb_report_csv, out_root=out_root)
    early_time_invariants_report = resolve_path_under_outdir(args.early_time_invariants_report, out_root=out_root)
    derived_rd_fit_dir = resolve_path_under_outdir(args.derived_rd_fit_dir, out_root=out_root)
    if cmb_report_json is None or cmb_report_csv is None or early_time_invariants_report is None:  # pragma: no cover
        raise SystemExit("failed to resolve early-time report paths")
    if derived_rd_fit_dir is None:  # pragma: no cover
        raise SystemExit("failed to resolve derived-rd fit dir")
    json_target = args.json
    if isinstance(json_target, str) and json_target != "-":
        resolved_json = resolve_path_under_outdir(Path(json_target), out_root=out_root)
        json_target = str(resolved_json) if resolved_json is not None else None

    artifacts_dir = args.artifacts_dir.expanduser().resolve()
    report: Dict[str, Any] = {
        "timestamp_utc": _now_utc(),
        "catalog": str(args.catalog.expanduser().resolve()),
        "artifacts_dir": str(artifacts_dir),
        "dry_run": bool(args.dry_run),
        "steps": [],
        "warnings": [],
        "result": "FAIL",
        "overall_status": "FAIL",
    }
    try:
        catalog = verify_all.load_catalog(args.catalog.expanduser().resolve())
        entries = _resolve_rc_entries(catalog)
    except Exception as exc:  # pragma: no cover - defensive path
        print(f"ERROR: unable to load RC catalog/context: {exc}", file=sys.stderr)
        report["error"] = f"unable to load RC catalog/context: {exc}"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 2

    report["required"] = [
        {
            "id": key,
            "asset": str(entries[key]["asset"]),
            "expected_sha256": str(entries[key]["sha256"]),
            "tag": str(entries[key]["tag"]),
            "release_url": str(entries[key]["release_url"]),
            "resolved_path": str(verify_all._resolve_asset_path(artifacts_dir, str(entries[key]["asset"]))),
        }
        for key in ("late_time", "submission", "referee_pack", "toe_bundle")
    ]
    report["cmb_reports"] = {
        "required": bool(args.require_cmb_reports),
        "json_path": str(cmb_report_json),
        "csv_path": str(cmb_report_csv),
    }
    report["early_time_invariants"] = {
        "required": bool(args.require_early_time_invariants),
        "json_path": str(early_time_invariants_report),
    }
    report["derived_rd"] = {
        "required": bool(args.require_derived_rd),
        "fit_dir": str(derived_rd_fit_dir),
    }

    if args.print_required:
        _print_required(entries, artifacts_dir)
        report["print_required"] = True
        report["result"] = "PASS"
        report["overall_status"] = "PASS"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 0

    should_check_cmb = bool(args.require_cmb_reports) or cmb_report_json.is_file() or cmb_report_csv.is_file()
    if should_check_cmb:
        cmb_rc, cmb_payload = _run_cmb_reports_check_step(
            report_json=cmb_report_json,
            report_csv=cmb_report_csv,
            require_reports=bool(args.require_cmb_reports),
            step_log=report["steps"],
        )
        report["cmb_reports"] = cmb_payload
        if cmb_rc != 0:
            report["error"] = "validate_early_time_cmb_reports failed"
            if json_target:
                _emit_json_report(str(json_target), report)
            return 2

    should_check_early_time_invariants = bool(args.require_early_time_invariants) or early_time_invariants_report.is_file()
    if should_check_early_time_invariants:
        invariants_rc, invariants_payload = _run_early_time_invariants_check_step(
            report_json=early_time_invariants_report,
            require_report=bool(args.require_early_time_invariants),
            step_log=report["steps"],
        )
        report["early_time_invariants"] = invariants_payload
        if invariants_rc != 0:
            report["error"] = "validate_early_time_numerics_invariants failed"
            if json_target:
                _emit_json_report(str(json_target), report)
            return 2

    should_check_derived_rd = bool(args.require_derived_rd) or derived_rd_fit_dir.is_dir()
    if should_check_derived_rd:
        derived_rc, derived_payload = _run_derived_rd_check_step(
            fit_dir=derived_rd_fit_dir,
            require_derived_rd=bool(args.require_derived_rd),
            step_log=report["steps"],
        )
        report["derived_rd"] = derived_payload
        if derived_rc != 0:
            report["error"] = "validate_derived_rd_outputs failed"
            if json_target:
                _emit_json_report(str(json_target), report)
            return 2

    missing = _check_required_files_exist(entries, artifacts_dir)
    if missing:
        report["missing_artifacts"] = missing
        report["error"] = "missing required canonical artifacts"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 2

    assets = {
        key: verify_all._resolve_asset_path(artifacts_dir, str(rec["asset"]))
        for key, rec in entries.items()
    }

    cmd_verify_all = [
        sys.executable,
        str(SCRIPTS_DIR / "verify_all_canonical_artifacts.py"),
        "--catalog",
        str(args.catalog),
        "--artifacts-dir",
        str(artifacts_dir),
    ]
    if args.skip_status_doc_check:
        cmd_verify_all.append("--skip-status-doc-check")
    if args.dry_run:
        cmd_verify_all.append("--dry-run")

    if _run_step("verify_all_canonical_artifacts", cmd_verify_all, report["steps"]) != 0:
        report["error"] = "verify_all_canonical_artifacts failed"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 2

    if not args.skip_pointer_sot_lint:
        cmd_ptr = [
            sys.executable,
            str(SCRIPTS_DIR / "pointer_sot_lint.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--catalog",
            str(args.catalog),
        ]
        if _run_step("pointer_sot_lint", cmd_ptr, report["steps"]) != 0:
            report["error"] = "pointer_sot_lint failed"
            if json_target:
                _emit_json_report(str(json_target), report)
            return 2

    if not args.skip_docs_claims_lint:
        cmd_docs_claims = [
            sys.executable,
            str(SCRIPTS_DIR / "docs_claims_lint.py"),
            "--repo-root",
            str(V101_DIR),
        ]
        if _run_step("docs_claims_lint", cmd_docs_claims, report["steps"]) != 0:
            report["error"] = "docs_claims_lint failed"
            if json_target:
                _emit_json_report(str(json_target), report)
            return 2

    if args.dry_run:
        print("RC OK (dry-run)")
        report["result"] = "PASS"
        report["overall_status"] = "PASS"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 0

    cmd_submission = [
        sys.executable,
        str(SCRIPTS_DIR / "verify_submission_bundle.py"),
        str(assets["submission"]),
    ]
    if not args.skip_smoke_compile:
        cmd_submission.append("--smoke-compile")
    if _run_step("verify_submission_bundle", cmd_submission, report["steps"]) != 0:
        report["error"] = "verify_submission_bundle failed"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 2

    if not args.skip_arxiv_preflight:
        with tempfile.TemporaryDirectory(prefix="gsc_rc_arxiv_") as td:
            preflight_json = Path(td) / "arxiv_preflight.json"
            cmd_arxiv_preflight = [
                sys.executable,
                str(SCRIPTS_DIR / "arxiv_preflight_check.py"),
                str(assets["submission"]),
                "--json",
                str(preflight_json),
            ]
            arxiv_rc = _run_step("arxiv_preflight_check", cmd_arxiv_preflight, report["steps"])
            if preflight_json.is_file():
                try:
                    report["arxiv_preflight"] = json.loads(preflight_json.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    report["warnings"].append(f"arxiv_preflight JSON parse failed: {exc}")
            if isinstance(report.get("arxiv_preflight"), dict):
                arxiv_result = str(report["arxiv_preflight"].get("result", "PASS"))
                if arxiv_result == "WARN":
                    warnings = report["arxiv_preflight"].get("warnings") or []
                    if warnings:
                        report["warnings"].append(f"arxiv_preflight: WARN - {warnings[0]}")
                    else:
                        report["warnings"].append("arxiv_preflight: WARN")
            if arxiv_rc != 0:
                report["error"] = "arxiv_preflight_check failed"
                if json_target:
                    _emit_json_report(str(json_target), report)
                return 2

    bundle_vs_repo = _run_bundle_vs_repo_tex_check(assets["submission"], V101_DIR / "GSC_Framework_v10_1_FINAL.tex")
    report["bundle_vs_repo_tex"] = bundle_vs_repo
    if not bundle_vs_repo.get("match", False):
        report["warnings"].append(
            "bundle_vs_repo_tex_drift: "
            + str(bundle_vs_repo.get("warning") or "submission bundle TeX differs from repo TeX")
        )

    cmd_referee = [
        sys.executable,
        str(SCRIPTS_DIR / "verify_referee_pack.py"),
        str(assets["referee_pack"]),
    ]
    if _run_step("verify_referee_pack", cmd_referee, report["steps"]) != 0:
        report["error"] = "verify_referee_pack failed"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 2

    cmd_toe = [
        sys.executable,
        str(SCRIPTS_DIR / "verify_toe_bundle.py"),
        str(assets["toe_bundle"]),
    ]
    if _run_step("verify_toe_bundle", cmd_toe, report["steps"]) != 0:
        report["error"] = "verify_toe_bundle failed"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 2

    cmd_lint_repo = [
        sys.executable,
        str(SCRIPTS_DIR / "paper_readiness_lint.py"),
        "--tex",
        str(V101_DIR / "GSC_Framework_v10_1_FINAL.tex"),
        "--md",
        str(V101_DIR / "GSC_Framework_v10_1_FINAL.md"),
    ]
    if _run_step("paper_readiness_lint (repo)", cmd_lint_repo, report["steps"]) != 0:
        report["error"] = "paper_readiness_lint (repo) failed"
        if json_target:
            _emit_json_report(str(json_target), report)
        return 2

    if not args.skip_extracted_submission_lint:
        with tempfile.TemporaryDirectory(prefix="gsc_rc_submission_") as td:
            tmp = Path(td)
            with zipfile.ZipFile(assets["submission"], "r") as zf:
                zf.extractall(tmp)
            tex = tmp / "GSC_Framework_v10_1_FINAL.tex"
            if not tex.is_file():
                print(f"ERROR: extracted submission bundle missing TeX file: {tex}", file=sys.stderr)
                report["error"] = f"extracted submission bundle missing TeX file: {tex}"
                if json_target:
                    _emit_json_report(str(json_target), report)
                return 2
            cmd_lint_submission = [
                sys.executable,
                str(SCRIPTS_DIR / "paper_readiness_lint.py"),
                "--tex",
                str(tex),
                "--profile",
                "submission",
                "--skip-md-check",
            ]
            if _run_step("paper_readiness_lint (submission tree)", cmd_lint_submission, report["steps"]) != 0:
                report["error"] = "paper_readiness_lint (submission tree) failed"
                if json_target:
                    _emit_json_report(str(json_target), report)
                return 2

    print("RC OK")
    report["result"] = "PASS"
    report["overall_status"] = "PASS"
    report["summary"] = {
        "step_count": len(report["steps"]),
        "pass_count": sum(1 for s in report["steps"] if s.get("status") == "PASS"),
        "fail_count": sum(1 for s in report["steps"] if s.get("status") != "PASS"),
        "duration_sec_total": round(sum(float(s.get("duration_sec", 0.0)) for s in report["steps"]), 6),
    }
    if json_target:
        _emit_json_report(str(json_target), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
