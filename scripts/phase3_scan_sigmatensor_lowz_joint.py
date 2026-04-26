#!/usr/bin/env python3
"""Deterministic Phase-3 mini-scan over LOWZ_JOINT objective."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.jsonl_io import open_text_auto  # noqa: E402


TOOL_NAME = "phase3_scan_sigmatensor_lowz_joint"
PLAN_SCHEMA = "phase3_sigmatensor_lowz_scan_plan_v1"
ROW_SCHEMA = "phase3_sigmatensor_lowz_scan_row_v1"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
LOWZ_JOINT_SCRIPT = ROOT / "scripts" / "phase3_joint_sigmatensor_lowz_report.py"
FAIL_MARKER = "PHASE3_LOWZ_SCAN_FAILED"
JOINT_FAIL_MARKER = "PHASE3_LOWZ_JOINT_FAILED"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")
_CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ABS_UNIX_RE = re.compile(r"/(?:Users|home|var/folders)/[^\s]+")
_ABS_WIN_RE = re.compile(r"[A-Za-z]:\\Users\\[^\s]+")


class UsageError(Exception):
    """Usage/configuration/IO error (exit 1)."""


class GateError(Exception):
    """Gate failure in fail-fast mode (exit 2)."""


def _json_compact(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise UsageError(f"{name} must be a finite float") from exc
    if not (out == out and abs(out) != float("inf")):
        raise UsageError(f"{name} must be a finite float")
    return float(out)


def _positive_float(value: Any, *, name: str) -> float:
    out = _finite_float(value, name=name)
    if out <= 0.0:
        raise UsageError(f"{name} must be > 0")
    return out


def _normalize_created_utc(value: str) -> str:
    text = str(value or "").strip()
    if not _CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_plan_slice(raw: str) -> Tuple[int, int]:
    text = str(raw or "").strip()
    if "/" not in text:
        raise UsageError("--plan-slice must be in I/N format")
    left, right = text.split("/", 1)
    try:
        idx = int(left)
        total = int(right)
    except Exception as exc:
        raise UsageError("--plan-slice requires integer I/N") from exc
    if total < 1:
        raise UsageError("--plan-slice requires N >= 1")
    if idx < 0 or idx >= total:
        raise UsageError("--plan-slice requires 0 <= I < N")
    return int(idx), int(total)


def _linspace(min_value: float, max_value: float, steps: int, *, name: str) -> List[float]:
    if steps < 1:
        raise UsageError(f"{name} must be >= 1")
    lo = _finite_float(min_value, name=f"{name} min")
    hi = _finite_float(max_value, name=f"{name} max")
    if steps == 1:
        return [float(lo)]
    delta = float(hi - lo)
    step = float(delta / float(steps - 1))
    out: List[float] = []
    for i in range(int(steps)):
        if i == int(steps - 1):
            out.append(float(hi))
        else:
            out.append(float(lo + step * float(i)))
    return out


def _sanitize_message(text: str) -> str:
    raw = " ".join(str(text or "").split())
    for token in ABS_TOKENS:
        raw = raw.replace(token, "[abs]/")
    raw = raw.replace(str(ROOT.resolve()), ".")
    raw = raw.replace(str(ROOT.parent.resolve()), ".")
    raw = _ABS_UNIX_RE.sub("[abs]", raw)
    raw = _ABS_WIN_RE.sub("[abs]", raw)
    raw = raw.strip()
    if len(raw) > 300:
        return raw[:300]
    return raw


def _canonical_plan_source_sha256(payload: Mapping[str, Any]) -> str:
    body = {str(k): payload[k] for k in payload.keys() if str(k) != "plan_source_sha256"}
    return _sha256_text(_json_compact(body))


def _plan_point_id(*, fixed_core: Mapping[str, Any], params: Mapping[str, Any]) -> str:
    payload = {"fixed_params_core": dict(fixed_core), "params": dict(params)}
    return _sha256_text(_json_compact(payload))


def _write_jsonl_line(fp, payload: Mapping[str, Any]) -> None:
    fp.write(_json_compact(payload))
    fp.write("\n")


def _parse_existing_ids(path: Path) -> Set[str]:
    out: Set[str] = set()
    if not path.exists() or not path.is_file():
        return out
    with open_text_auto(path, "r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            text = str(raw).strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except Exception:
                continue
            if not isinstance(parsed, Mapping):
                continue
            pid = parsed.get("plan_point_id")
            if isinstance(pid, str) and pid:
                out.add(pid)
    return out


def _parse_plan(path: Path) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]], Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise UsageError(f"--plan parse failed: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise UsageError("--plan root must be a JSON object")
    schema = str(payload.get("schema") or "")
    if schema != PLAN_SCHEMA:
        raise UsageError(f"--plan schema mismatch: expected {PLAN_SCHEMA}, got {schema or 'missing'}")
    created_utc = payload.get("created_utc")
    if not isinstance(created_utc, str) or not created_utc.strip():
        raise UsageError("--plan missing created_utc")
    fixed = payload.get("fixed_params")
    if not isinstance(fixed, Mapping):
        raise UsageError("--plan missing fixed_params object")
    points_raw = payload.get("points")
    if not isinstance(points_raw, list):
        raise UsageError("--plan missing points list")
    points: List[Dict[str, Any]] = []
    for row in points_raw:
        if not isinstance(row, Mapping):
            raise UsageError("--plan points entries must be objects")
        idx = row.get("index")
        params = row.get("params")
        pid = row.get("plan_point_id")
        if not isinstance(idx, int):
            raise UsageError("--plan points entry missing integer index")
        if not isinstance(params, Mapping):
            raise UsageError("--plan points entry missing params object")
        if not isinstance(pid, str) or not pid:
            raise UsageError("--plan points entry missing plan_point_id")
        omega_m = _finite_float(params.get("Omega_m"), name="plan point params.Omega_m")
        w0 = _finite_float(params.get("w0"), name="plan point params.w0")
        lambda_ = _finite_float(params.get("lambda"), name="plan point params.lambda")
        points.append(
            {
                "index": int(idx),
                "params": {
                    "Omega_m": float(omega_m),
                    "w0": float(w0),
                    "lambda": float(lambda_),
                },
                "plan_point_id": str(pid),
            }
        )

    points_sorted = sorted(points, key=lambda x: (int(x["index"]), str(x["plan_point_id"])))
    declared = payload.get("plan_source_sha256")
    expected = _canonical_plan_source_sha256(payload)
    if not isinstance(declared, str) or not declared:
        raise UsageError("--plan missing plan_source_sha256")
    if declared != expected:
        raise UsageError("plan_source_sha256 mismatch in --plan file")
    return dict(payload), str(declared), points_sorted, {str(k): fixed[k] for k in fixed.keys()}


def _build_row_error(returncode: int, stderr: str, stdout: str) -> Dict[str, Any]:
    message = _sanitize_message(stderr if str(stderr).strip() else stdout)
    marker = JOINT_FAIL_MARKER if JOINT_FAIL_MARKER in str(stderr) else None
    out: Dict[str, Any] = {
        "returncode": int(returncode),
        "message": message,
    }
    if marker is not None:
        out["error_marker"] = marker
    return out


def _select_chi2_blocks(blocks: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in ("bao", "sn", "rsd", "cmb"):
        block = blocks.get(key)
        if not isinstance(block, Mapping):
            continue
        chi2 = block.get("chi2")
        if chi2 is None:
            continue
        try:
            out[str(key)] = float(chi2)
        except Exception:
            continue
    return out


def _extract_nuisances(blocks: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    bao = blocks.get("bao")
    if isinstance(bao, Mapping) and bao.get("rd_m_bestfit") is not None:
        out["rd_m_bestfit"] = float(bao.get("rd_m_bestfit"))
    sn = blocks.get("sn")
    if isinstance(sn, Mapping) and sn.get("delta_M_bestfit") is not None:
        out["delta_M_bestfit"] = float(sn.get("delta_M_bestfit"))
    rsd = blocks.get("rsd")
    if isinstance(rsd, Mapping):
        if rsd.get("sigma8_0_bestfit") is not None:
            out["sigma8_0_bestfit"] = float(rsd.get("sigma8_0_bestfit"))
        elif rsd.get("sigma8_0_used") is not None:
            out["sigma8_0_used"] = float(rsd.get("sigma8_0_used"))
    return out


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic Phase-3 mini-scan for LOWZ_JOINT objective.")

    ap.add_argument("--plan-out", type=Path, default=None, help="Write deterministic scan plan JSON.")
    ap.add_argument("--plan", type=Path, default=None, help="Scan plan JSON for run mode.")
    ap.add_argument("--out-jsonl", type=Path, default=None, help="Output JSONL(.gz) for run mode.")
    ap.add_argument("--outdir", type=Path, default=None, help="Optional output dir for per-point reports.")
    ap.add_argument("--keep-reports", choices=("0", "1"), default="0")
    ap.add_argument("--keep-reports-on-failure", choices=("0", "1"), default="0")
    ap.add_argument("--plan-slice", default=None, help="Optional slice in I/N format.")
    ap.add_argument("--resume", choices=("0", "1"), default="1")
    ap.add_argument("--fail-fast", choices=("0", "1"), default="0")
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--joint-extra-arg", action="append", default=[], help="Repeatable passthrough arg token.")
    ap.add_argument("--format", choices=("text", "json"), default="text")

    # Fixed params (plan mode)
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, default=None)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)

    # Grid spec (plan mode)
    ap.add_argument("--Omega-m-min", dest="Omega_m_min", type=float, default=None)
    ap.add_argument("--Omega-m-max", dest="Omega_m_max", type=float, default=None)
    ap.add_argument("--Omega-m-steps", dest="Omega_m_steps", type=int, default=None)
    ap.add_argument("--w0-min", dest="w0_min", type=float, default=None)
    ap.add_argument("--w0-max", dest="w0_max", type=float, default=None)
    ap.add_argument("--w0-steps", dest="w0_steps", type=int, default=None)
    ap.add_argument("--lambda-min", dest="lambda_min", type=float, default=None)
    ap.add_argument("--lambda-max", dest="lambda_max", type=float, default=None)
    ap.add_argument("--lambda-steps", dest="lambda_steps", type=int, default=None)
    raw = list(sys.argv[1:] if argv is None else list(argv))
    normalized: List[str] = []
    i = 0
    while i < len(raw):
        token = str(raw[i])
        if token == "--joint-extra-arg":
            if i + 1 >= len(raw):
                ap.error("argument --joint-extra-arg: expected one argument")
            normalized.append(f"--joint-extra-arg={raw[i + 1]}")
            i += 2
            continue
        normalized.append(token)
        i += 1
    return ap.parse_args(normalized)


def _run_plan_mode(args: argparse.Namespace, created_utc: str) -> Tuple[int, Dict[str, Any]]:
    if args.plan_out is None:
        raise UsageError("plan mode requires --plan-out")
    required = {
        "--H0-km-s-Mpc": args.H0_km_s_Mpc,
        "--Omega-m-min": args.Omega_m_min,
        "--Omega-m-max": args.Omega_m_max,
        "--Omega-m-steps": args.Omega_m_steps,
        "--w0-min": args.w0_min,
        "--w0-max": args.w0_max,
        "--w0-steps": args.w0_steps,
        "--lambda-min": args.lambda_min,
        "--lambda-max": args.lambda_max,
        "--lambda-steps": args.lambda_steps,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise UsageError("plan mode missing required args: " + ", ".join(missing))

    H0_km = _positive_float(args.H0_km_s_Mpc, name="--H0-km-s-Mpc")
    Tcmb_K = _positive_float(args.Tcmb_K, name="--Tcmb-K")
    N_eff = _finite_float(args.N_eff, name="--N-eff")
    if N_eff < 0.0:
        raise UsageError("--N-eff must be >= 0")
    omega_r0_override = None
    if args.Omega_r0_override is not None:
        omega_r0_override = _finite_float(args.Omega_r0_override, name="--Omega-r0-override")
        if omega_r0_override < 0.0:
            raise UsageError("--Omega-r0-override must be >= 0")

    om_values = _linspace(
        _finite_float(args.Omega_m_min, name="--Omega-m-min"),
        _finite_float(args.Omega_m_max, name="--Omega-m-max"),
        int(args.Omega_m_steps),
        name="--Omega-m-steps",
    )
    w0_values = _linspace(
        _finite_float(args.w0_min, name="--w0-min"),
        _finite_float(args.w0_max, name="--w0-max"),
        int(args.w0_steps),
        name="--w0-steps",
    )
    lambda_values = _linspace(
        _finite_float(args.lambda_min, name="--lambda-min"),
        _finite_float(args.lambda_max, name="--lambda-max"),
        int(args.lambda_steps),
        name="--lambda-steps",
    )

    fixed_params = {
        "H0_km_s_Mpc": float(H0_km),
        "Tcmb_K": float(Tcmb_K),
        "N_eff": float(N_eff),
        "Omega_r0_override": (None if omega_r0_override is None else float(omega_r0_override)),
        "sign_u0": int(args.sign_u0),
    }
    fixed_core = {
        "H0_km_s_Mpc": float(H0_km),
        "Tcmb_K": float(Tcmb_K),
        "N_eff": float(N_eff),
        "Omega_r0_override": (None if omega_r0_override is None else float(omega_r0_override)),
        "sign_u0": int(args.sign_u0),
    }

    points_tmp: List[Dict[str, Any]] = []
    for om in om_values:
        for w0 in w0_values:
            for lam in lambda_values:
                params = {
                    "Omega_m": float(om),
                    "w0": float(w0),
                    "lambda": float(lam),
                }
                pid = _plan_point_id(fixed_core=fixed_core, params=params)
                points_tmp.append({"params": params, "plan_point_id": pid})
    points_sorted = sorted(
        points_tmp,
        key=lambda row: (
            float(row["params"]["Omega_m"]),
            float(row["params"]["w0"]),
            float(row["params"]["lambda"]),
            str(row["plan_point_id"]),
        ),
    )
    points: List[Dict[str, Any]] = []
    for idx, row in enumerate(points_sorted):
        points.append(
            {
                "index": int(idx),
                "params": {
                    "Omega_m": float(row["params"]["Omega_m"]),
                    "w0": float(row["params"]["w0"]),
                    "lambda": float(row["params"]["lambda"]),
                },
                "plan_point_id": str(row["plan_point_id"]),
            }
        )

    payload: Dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "tool": TOOL_NAME,
        "created_utc": str(created_utc),
        "grid_spec": {
            "Omega_m_min": float(args.Omega_m_min),
            "Omega_m_max": float(args.Omega_m_max),
            "Omega_m_steps": int(args.Omega_m_steps),
            "w0_min": float(args.w0_min),
            "w0_max": float(args.w0_max),
            "w0_steps": int(args.w0_steps),
            "lambda_min": float(args.lambda_min),
            "lambda_max": float(args.lambda_max),
            "lambda_steps": int(args.lambda_steps),
        },
        "fixed_params": fixed_params,
        "points": points,
    }
    payload["plan_source_sha256"] = _canonical_plan_source_sha256(payload)

    plan_out = Path(args.plan_out).expanduser().resolve()
    plan_out.parent.mkdir(parents=True, exist_ok=True)
    plan_out.write_text(_json_pretty(payload), encoding="utf-8")

    summary = {
        "schema": "phase3_sigmatensor_lowz_scan_plan_summary_v1",
        "mode": "plan",
        "plan_out": str(plan_out.name),
        "created_utc": str(created_utc),
        "n_points": int(len(points)),
        "plan_source_sha256": str(payload["plan_source_sha256"]),
    }
    return 0, summary


def _run_scan_mode(args: argparse.Namespace, created_utc: str) -> Tuple[int, Dict[str, Any]]:
    if args.plan is None or args.out_jsonl is None:
        raise UsageError("run mode requires both --plan and --out-jsonl")
    if args.plan_out is not None:
        raise UsageError("--plan-out cannot be combined with run mode")

    keep_reports = str(args.keep_reports) == "1"
    keep_reports_on_failure = str(args.keep_reports_on_failure) == "1"
    resume = str(args.resume) == "1"
    fail_fast = str(args.fail_fast) == "1"

    if (keep_reports or keep_reports_on_failure) and args.outdir is None:
        raise UsageError("--outdir is required when --keep-reports or --keep-reports-on-failure is enabled")

    out_jsonl = Path(args.out_jsonl).expanduser().resolve()
    if not (str(out_jsonl).endswith(".jsonl") or str(out_jsonl).endswith(".jsonl.gz")):
        raise UsageError("--out-jsonl must end with .jsonl or .jsonl.gz")
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    plan_path = Path(args.plan).expanduser().resolve()
    if not plan_path.is_file():
        raise UsageError(f"--plan not found: {plan_path}")

    _plan_payload, plan_source_sha256, points, fixed = _parse_plan(plan_path)
    if not points:
        raise UsageError("--plan contains no points")

    if args.plan_slice is not None:
        slice_i, slice_n = _normalize_plan_slice(str(args.plan_slice))
        filtered: List[Dict[str, Any]] = []
        for pos, row in enumerate(points):
            if int(pos % slice_n) == int(slice_i):
                filtered.append(row)
        points = filtered

    existing_ids: Set[str] = set()
    if resume and out_jsonl.exists():
        existing_ids = _parse_existing_ids(out_jsonl)

    scan_config_payload = {
        "joint_extra_args": [str(x) for x in list(args.joint_extra_arg or [])],
        "keep_reports": bool(keep_reports),
        "keep_reports_on_failure": bool(keep_reports_on_failure),
        "created_utc": str(created_utc),
    }
    scan_config_sha256 = _sha256_text(_json_compact(scan_config_payload))

    if args.outdir is not None:
        reports_root = Path(args.outdir).expanduser().resolve()
        reports_root.mkdir(parents=True, exist_ok=True)
    else:
        reports_root = None

    mode = "a" if (resume and out_jsonl.exists()) else "w"
    n_total = 0
    n_written = 0
    n_skipped_resume = 0
    n_ok = 0
    n_error = 0

    with open_text_auto(out_jsonl, mode, encoding="utf-8", newline="") as fp:
        for row in points:
            n_total += 1
            plan_point_id = str(row["plan_point_id"])
            if resume and plan_point_id in existing_ids:
                n_skipped_resume += 1
                continue

            point_index = int(row["index"])
            point_params = row["params"]
            omega_m = float(point_params["Omega_m"])
            w0 = float(point_params["w0"])
            lambda_ = float(point_params["lambda"])

            row_payload: Dict[str, Any] = {
                "schema": ROW_SCHEMA,
                "status": "error",
                "plan_point_id": str(plan_point_id),
                "plan_source_sha256": str(plan_source_sha256),
                "scan_config_sha256": str(scan_config_sha256),
                "point_index": int(point_index),
                "params": {
                    "Omega_m": float(omega_m),
                    "w0": float(w0),
                    "lambda": float(lambda_),
                    "H0_km_s_Mpc": float(fixed["H0_km_s_Mpc"]),
                    "Tcmb_K": float(fixed.get("Tcmb_K", 2.7255)),
                    "N_eff": float(fixed.get("N_eff", 3.046)),
                    "Omega_r0_override": (
                        None
                        if fixed.get("Omega_r0_override") is None
                        else float(fixed.get("Omega_r0_override"))
                    ),
                    "sign_u0": int(fixed.get("sign_u0", +1)),
                },
                "chi2_total": None,
                "results": {},
                "report_sha256": None,
                "error": None,
            }

            with tempfile.TemporaryDirectory(prefix=f"phase3_m130_p{point_index:06d}_") as td:
                tmp_out = Path(td)
                cmd: List[str] = [
                    sys.executable,
                    str(LOWZ_JOINT_SCRIPT),
                    "--H0-km-s-Mpc",
                    f"{float(fixed['H0_km_s_Mpc']):.17g}",
                    "--Omega-m",
                    f"{float(omega_m):.17g}",
                    "--w0",
                    f"{float(w0):.17g}",
                    "--lambda",
                    f"{float(lambda_):.17g}",
                    "--Tcmb-K",
                    f"{float(fixed.get('Tcmb_K', 2.7255)):.17g}",
                    "--N-eff",
                    f"{float(fixed.get('N_eff', 3.046)):.17g}",
                    "--sign-u0",
                    str(int(fixed.get("sign_u0", +1))),
                ]
                if fixed.get("Omega_r0_override") is not None:
                    cmd.extend(["--Omega-r0-override", f"{float(fixed.get('Omega_r0_override')):.17g}"])
                for token in list(args.joint_extra_arg or []):
                    cmd.append(str(token))
                cmd.extend(
                    [
                        "--created-utc",
                        str(created_utc),
                        "--outdir",
                        str(tmp_out),
                        "--format",
                        "json",
                    ]
                )

                proc = subprocess.run(
                    cmd,
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                )
                rc = int(proc.returncode)
                report_path = tmp_out / "LOWZ_JOINT_REPORT.json"

                should_keep = bool(keep_reports)
                if rc != 0 and keep_reports_on_failure:
                    should_keep = True
                if should_keep and reports_root is not None:
                    target = reports_root / f"point_{point_index:06d}_{plan_point_id[:12]}"
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(tmp_out, target)

                if rc == 0:
                    if not report_path.is_file():
                        row_payload["status"] = "error"
                        row_payload["error"] = {
                            "returncode": 1,
                            "message": "LOWZ_JOINT_REPORT.json missing after successful subprocess return",
                        }
                        n_error += 1
                        if fail_fast:
                            _write_jsonl_line(fp, row_payload)
                            n_written += 1
                            raise GateError("missing LOWZ_JOINT_REPORT.json in subprocess output")
                    else:
                        report_bytes = report_path.read_bytes()
                        try:
                            report = json.loads(report_bytes.decode("utf-8"))
                        except Exception:
                            row_payload["status"] = "error"
                            row_payload["error"] = {
                                "returncode": 1,
                                "message": "LOWZ_JOINT_REPORT.json parse failed",
                            }
                            n_error += 1
                            if fail_fast:
                                _write_jsonl_line(fp, row_payload)
                                n_written += 1
                                raise GateError("LOWZ_JOINT_REPORT.json parse failed")
                        else:
                            if not isinstance(report, Mapping):
                                row_payload["status"] = "error"
                                row_payload["error"] = {
                                    "returncode": 1,
                                    "message": "LOWZ_JOINT_REPORT.json root is not object",
                                }
                                n_error += 1
                                if fail_fast:
                                    _write_jsonl_line(fp, row_payload)
                                    n_written += 1
                                    raise GateError("LOWZ_JOINT_REPORT.json root is not object")
                            else:
                                blocks = report.get("blocks")
                                total = report.get("total")
                                deltas = report.get("deltas")
                                total_chi2 = None
                                ndof_total = None
                                if isinstance(total, Mapping):
                                    if total.get("chi2") is not None:
                                        total_chi2 = float(total.get("chi2"))
                                    if total.get("ndof") is not None:
                                        ndof_total = int(total.get("ndof"))
                                chi2_blocks = _select_chi2_blocks(blocks if isinstance(blocks, Mapping) else {})
                                nuisances = _extract_nuisances(blocks if isinstance(blocks, Mapping) else {})
                                row_payload["status"] = "ok"
                                row_payload["chi2_total"] = total_chi2
                                row_payload["results"] = {
                                    "chi2_total": total_chi2,
                                    "ndof_total": ndof_total,
                                    "chi2_blocks": chi2_blocks,
                                    "nuisances": nuisances,
                                    "deltas": (
                                        {
                                            str(k): float(v)
                                            for k, v in dict(deltas).items()
                                            if isinstance(v, (int, float))
                                        }
                                        if isinstance(deltas, Mapping)
                                        else {}
                                    ),
                                }
                                row_payload["report_sha256"] = _sha256_bytes(report_bytes)
                                row_payload["error"] = None
                                n_ok += 1
                else:
                    row_payload["status"] = "error"
                    row_payload["error"] = _build_row_error(
                        returncode=rc,
                        stderr=(proc.stderr or ""),
                        stdout=(proc.stdout or ""),
                    )
                    n_error += 1
                    if fail_fast:
                        _write_jsonl_line(fp, row_payload)
                        n_written += 1
                        raise GateError(f"point {point_index} failed under --fail-fast")

            _write_jsonl_line(fp, row_payload)
            n_written += 1

    summary: Dict[str, Any] = {
        "schema": "phase3_sigmatensor_lowz_scan_run_summary_v1",
        "mode": "run",
        "created_utc": str(created_utc),
        "plan_source_sha256": str(plan_source_sha256),
        "scan_config_sha256": str(scan_config_sha256),
        "out_jsonl": str(out_jsonl.name),
        "counts": {
            "points_input": int(n_total),
            "rows_written": int(n_written),
            "skipped_resume": int(n_skipped_resume),
            "ok": int(n_ok),
            "error": int(n_error),
        },
    }
    return 0, summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        if args.plan_out is not None:
            if args.plan is not None or args.out_jsonl is not None:
                raise UsageError("plan mode (--plan-out) cannot be combined with --plan/--out-jsonl")
            code, summary = _run_plan_mode(args, created_utc)
        else:
            if args.plan is None and args.out_jsonl is None:
                raise UsageError("select mode: use --plan-out (plan mode) or --plan + --out-jsonl (run mode)")
            code, summary = _run_scan_mode(args, created_utc)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except GateError as exc:
        print(FAIL_MARKER, file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(_json_pretty(summary))
    else:
        mode = str(summary.get("mode", "unknown"))
        counts = summary.get("counts") if isinstance(summary.get("counts"), Mapping) else {}
        if mode == "plan":
            sys.stdout.write(
                "mode=plan "
                f"n_points={int(summary.get('n_points', 0))} "
                f"plan_source_sha256={summary.get('plan_source_sha256', '')}\n"
            )
        else:
            sys.stdout.write(
                "mode=run "
                f"written={int(counts.get('rows_written', 0))} "
                f"ok={int(counts.get('ok', 0))} "
                f"error={int(counts.get('error', 0))} "
                f"skipped_resume={int(counts.get('skipped_resume', 0))}\n"
            )
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
