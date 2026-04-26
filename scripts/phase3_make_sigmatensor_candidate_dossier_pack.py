#!/usr/bin/env python3
"""Build deterministic Phase-3 candidate dossier packs from scan analysis."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TOOL = "phase3_make_sigmatensor_candidate_dossier_pack"
SCHEMA = "phase3_sigmatensor_candidate_dossier_manifest_v1"
ANALYSIS_SCHEMA = "phase3_sigmatensor_lowz_scan_analysis_v1"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
FAIL_MARKER = "PHASE3_CANDIDATE_DOSSIER_FAILED"
LINT_FAIL_MARKER = "PHASE3_DOSSIER_PORTABLE_LINT_FAILED"
ZIP_BUDGET_FAIL_MARKER = "PHASE3_DOSSIER_ZIP_BUDGET_EXCEEDED"
QUICKLOOK_FAIL_MARKER = "PHASE3_DOSSIER_QUICKLOOK_FAILED"
CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SANITIZE_ID_RE = re.compile(r"[^a-z0-9_]+")
ABS_WIN_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+")
ABS_UNIX_RE = re.compile(r"(?<![A-Za-z0-9_.-])/[^\s\"']+")
FIXED_ZIP_DT = (2000, 1, 1, 0, 0, 0)

SCRIPT_JOINT = ROOT / "scripts" / "phase3_joint_sigmatensor_lowz_report.py"
SCRIPT_FSIGMA8 = ROOT / "scripts" / "phase3_sf_sigmatensor_fsigma8_report.py"
SCRIPT_EFT = ROOT / "scripts" / "phase3_pt_sigmatensor_eft_export_pack.py"
SCRIPT_CLASS = ROOT / "scripts" / "phase3_pt_sigmatensor_class_export_pack.py"
SCRIPT_CLASS_MAPPING = ROOT / "scripts" / "phase3_pt_sigmatensor_class_mapping_report.py"
SCRIPT_QUICKLOOK = ROOT / "scripts" / "phase3_dossier_quicklook_report.py"
SCRIPT_CLASS_RUN = ROOT / "scripts" / "phase2_pt_boltzmann_run_harness.py"
SCRIPT_CLASS_RESULTS = ROOT / "scripts" / "phase2_pt_boltzmann_results_pack.py"
SCRIPT_SPECTRA_SANITY = ROOT / "scripts" / "phase3_pt_spectra_sanity_report.py"
SCRIPT_PORTABLE_LINT = ROOT / "scripts" / "phase2_portable_content_lint.py"

SUBTOOL_MARKERS: Mapping[str, Tuple[str, ...]] = {
    "joint": ("PHASE3_LOWZ_JOINT_FAILED",),
    "fsigma8": ("PHASE3_SIGMATENSOR_FSIGMA8_FAILED",),
    "eft": ("PHASE3_SIGMATENSOR_EFT_EXPORT_FAILED",),
    "class": ("PHASE3_SIGMATENSOR_CLASS_EXPORT_FAILED",),
    "class_mapping": ("PHASE3_CLASS_MAPPING_FAILED",),
    "class_run": ("HARNESS_UNPINNED_DOCKER_IMAGE",),
    "class_results": (
        "MISSING_ANY_OUTPUTS_FOR_RESULTS_PACK",
        "MISSING_TT_SPECTRUM_FOR_RESULTS_PACK",
        "RESULTS_PACK_ZIP_BUDGET_EXCEEDED",
    ),
    "spectra_sanity": ("PHASE3_SPECTRA_SANITY_FAILED",),
}


class UsageError(Exception):
    """Usage/configuration or IO failure (exit 1)."""


class GateError(Exception):
    """Gate failure (exit 2)."""


def _json_compact(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_created_utc(raw: str) -> str:
    text = str(raw or "").strip()
    if not CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise UsageError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise UsageError(f"{name} must be a finite float")
    return float(out)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sanitize_message(text: str) -> str:
    out = " ".join(str(text or "").split())
    out = out.replace(str(ROOT.resolve()), ".")
    out = out.replace(str(ROOT.parent.resolve()), ".")
    out = ABS_WIN_RE.sub("[abs]", out)
    out = ABS_UNIX_RE.sub("[abs]", out)
    out = out.strip()
    if len(out) > 300:
        return out[:300]
    return out


def _is_absolute_token(token: str) -> bool:
    text = str(token or "").strip()
    if not text:
        return False
    if text.startswith("/"):
        return True
    if ABS_WIN_RE.search(text):
        return True
    return False


def _flag_value(tokens: Sequence[str], flag: str) -> Optional[str]:
    out: Optional[str] = None
    for i, token in enumerate(tokens):
        if str(token) != str(flag):
            continue
        if i + 1 >= len(tokens):
            continue
        out = str(tokens[i + 1])
    return out


def _has_flag(tokens: Sequence[str], flag: str) -> bool:
    return any(str(token) == str(flag) for token in tokens)


def _normalize_fsigma8_args(tokens: Sequence[str]) -> List[str]:
    out = [str(x) for x in tokens]
    rsd_value = _flag_value(out, "--rsd")
    if rsd_value != "0":
        return out
    mode_value = _flag_value(out, "--sigma8-mode")
    has_sigma8_0 = _has_flag(out, "--sigma8-0")
    if mode_value is None:
        out.extend(["--sigma8-mode", "fixed"])
        mode_value = "fixed"
    if mode_value == "fixed" and not has_sigma8_0:
        out.extend(["--sigma8-0", "0.8"])
    return out


def _sanitize_plan_prefix(plan_point_id: str) -> str:
    text = str(plan_point_id or "").strip().lower()
    if not text:
        return "unknown"
    text = SANITIZE_ID_RE.sub("_", text)
    text = text.strip("_")
    if not text:
        return "unknown"
    return text[:12]


def _basename_or_empty(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return Path(text).name


def _image_ref_for_manifest(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    token = text.split("/")[-1]
    if token:
        return token
    return text


def _parse_ranks_csv(raw: Optional[str]) -> Optional[List[int]]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return []
    out: List[int] = []
    seen: set[int] = set()
    for token in text.split(","):
        part = str(token).strip()
        if not part:
            continue
        try:
            rank = int(part)
        except Exception as exc:
            raise UsageError(f"--ranks has invalid integer token: {part!r}") from exc
        if rank < 1:
            raise UsageError("--ranks values must be >= 1")
        if rank in seen:
            continue
        seen.add(rank)
        out.append(int(rank))
    return out


def _ensure_empty_outdir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise UsageError(f"--outdir exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise UsageError(f"--outdir must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _select_candidates(
    analysis: Mapping[str, Any],
    *,
    top_k: int,
    ranks: Optional[List[int]],
) -> List[Mapping[str, Any]]:
    raw = analysis.get("best_candidates")
    if not isinstance(raw, list):
        raise UsageError("analysis JSON missing best_candidates list")
    by_rank: Dict[int, Mapping[str, Any]] = {}
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        rank = row.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool):
            continue
        by_rank[int(rank)] = row
    if ranks is not None:
        out: List[Mapping[str, Any]] = []
        for rank in ranks:
            if rank not in by_rank:
                raise UsageError(f"--ranks requested missing rank: {rank}")
            out.append(by_rank[rank])
        return out
    if top_k < 1:
        raise UsageError("--top-k must be >= 1")
    ordered = sorted(by_rank.items(), key=lambda kv: int(kv[0]))
    return [row for _rank, row in ordered[: int(top_k)]]


def _collect_file_table(root: Path) -> List[Tuple[str, str]]:
    table: List[Tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel in {"DOSSIER_MANIFEST.json", "DOSSIER_MANIFEST.md"}:
                continue
            table.append((rel, _sha256_file(path)))
    return sorted(table, key=lambda row: row[0])


def _refresh_file_table_digest(payload: Dict[str, Any], outdir: Path) -> None:
    table = _collect_file_table(outdir)
    table_text = "".join(f"{rel},{sha}\n" for rel, sha in table)
    digests = payload.get("digests")
    if not isinstance(digests, Mapping):
        payload["digests"] = {}
        digests = payload["digests"]
    if isinstance(digests, dict):
        digests["dossier_file_table_sha256"] = _sha256_text(table_text)


def _collect_named_reports(outdir: Path, relnames: Sequence[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for rel in relnames:
        relpath = Path(str(rel))
        path = outdir / relpath
        if not path.is_file():
            continue
        rows.append({"rel": relpath.as_posix(), "sha256": _sha256_file(path)})
    return sorted(rows, key=lambda row: str(row["rel"]))


def _detect_marker(stderr: str, tool_name: str) -> Optional[str]:
    markers = SUBTOOL_MARKERS.get(str(tool_name))
    if markers is None:
        return None
    text = str(stderr or "")
    for marker in markers:
        if str(marker) in text:
            return str(marker)
    return None


def _subtool_entry(*, returncode: int, ok: bool, report_files: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "returncode": int(returncode),
        "ok": bool(ok),
        "report_files": [dict(row) for row in list(report_files)],
    }


def _collect_tool_reports(candidate_root: Path, tool_outdir: Path) -> List[Dict[str, Any]]:
    if not tool_outdir.exists() or not tool_outdir.is_dir():
        return []
    rows: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(tool_outdir):
        dirnames.sort()
        filenames.sort()
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if not path.is_file():
                continue
            rel = path.relative_to(candidate_root).as_posix()
            rows.append({"rel": rel, "sha256": _sha256_file(path)})
    return sorted(rows, key=lambda row: str(row["rel"]))


def _build_base_model_args(params: Mapping[str, Any]) -> List[str]:
    H0 = _finite_float(params.get("H0_km_s_Mpc"), name="candidate.params.H0_km_s_Mpc")
    omega_m = _finite_float(params.get("Omega_m"), name="candidate.params.Omega_m")
    w0 = _finite_float(params.get("w0"), name="candidate.params.w0")
    lambda_ = _finite_float(params.get("lambda"), name="candidate.params.lambda")
    Tcmb = _finite_float(params.get("Tcmb_K"), name="candidate.params.Tcmb_K")
    N_eff = _finite_float(params.get("N_eff"), name="candidate.params.N_eff")
    sign_u0 = params.get("sign_u0")
    if not isinstance(sign_u0, int) or isinstance(sign_u0, bool):
        raise UsageError("candidate.params.sign_u0 must be integer +/-1")
    args: List[str] = [
        "--H0-km-s-Mpc",
        f"{float(H0):.17g}",
        "--Omega-m",
        f"{float(omega_m):.17g}",
        "--w0",
        f"{float(w0):.17g}",
        "--lambda",
        f"{float(lambda_):.17g}",
        "--Tcmb-K",
        f"{float(Tcmb):.17g}",
        "--N-eff",
        f"{float(N_eff):.17g}",
        "--sign-u0",
        str(int(sign_u0)),
    ]
    omega_r0_override = params.get("Omega_r0_override")
    if omega_r0_override is not None:
        ovr = _finite_float(omega_r0_override, name="candidate.params.Omega_r0_override")
        args.extend(["--Omega-r0-override", f"{float(ovr):.17g}"])
    return args


def _parse_extra_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build deterministic candidate dossier pack from SCAN_ANALYSIS.json")
    ap.add_argument("--analysis", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--ranks", default=None)
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--joint-extra-arg", action="append", default=[])
    ap.add_argument("--fsigma8-extra-arg", action="append", default=[])
    ap.add_argument("--eft-extra-arg", action="append", default=[])
    ap.add_argument("--class-extra-arg", action="append", default=[])
    ap.add_argument("--include-class-mapping-report", choices=("0", "1"), default="1")
    ap.add_argument("--include-class-run", choices=("0", "1"), default="0")
    ap.add_argument("--class-runner", choices=("native", "docker"), default="native")
    ap.add_argument("--class-bin", default=None)
    ap.add_argument("--class-docker-image", default=None)
    ap.add_argument("--class-require-pinned-image", choices=("0", "1"), default="0")
    ap.add_argument("--spectra-require-tt", choices=("0", "1"), default="1")
    ap.add_argument("--spectra-require-ell-max-ge", type=int, default=None)
    ap.add_argument("--emit-quicklook", choices=("0", "1"), default="1")
    ap.add_argument("--emit-zip", choices=("0", "1"), default="0")
    ap.add_argument("--zip-out", type=Path, default=None)
    ap.add_argument("--max-mb", type=float, default=800.0)
    ap.add_argument("--lint-portable-content", choices=("0", "1"), default="1")
    ap.add_argument("--skip-portable-content-lint", choices=("0", "1"), default="0")
    ap.add_argument("--fail-fast", choices=("0", "1"), default="0")
    ap.add_argument("--format", choices=("text", "json"), default="text")

    raw = list(sys.argv[1:] if argv is None else list(argv))
    normalized: List[str] = []
    i = 0
    token_flags = {
        "--joint-extra-arg",
        "--fsigma8-extra-arg",
        "--eft-extra-arg",
        "--class-extra-arg",
    }
    while i < len(raw):
        token = str(raw[i])
        if token in token_flags:
            if i + 1 >= len(raw):
                ap.error(f"argument {token}: expected one argument")
            normalized.append(f"{token}={raw[i + 1]}")
            i += 2
            continue
        normalized.append(token)
        i += 1
    args = ap.parse_args(normalized)

    for name in ("joint_extra_arg", "fsigma8_extra_arg", "eft_extra_arg", "class_extra_arg"):
        values = list(getattr(args, name) or [])
        for value in values:
            if _is_absolute_token(str(value)):
                raise UsageError(f"{name.replace('_', '-')} cannot contain absolute path tokens: {value}")
    if args.spectra_require_ell_max_ge is not None and int(args.spectra_require_ell_max_ge) < 0:
        raise UsageError("--spectra-require-ell-max-ge must be >= 0")
    return args


def _run_subtool(
    *,
    tool_name: str,
    script_path: Path,
    base_args: Sequence[str],
    extra_args: Sequence[str],
    created_utc: str,
    tool_outdir: Path,
    candidate_root: Path,
    include_created_utc: bool,
) -> Tuple[Dict[str, Any], Optional[Dict[str, str]]]:
    tool_outdir.mkdir(parents=True, exist_ok=True)
    cmd: List[str] = [sys.executable, str(script_path), *list(base_args), *list(extra_args), "--outdir", str(tool_outdir)]
    if include_created_utc:
        cmd.extend(["--created-utc", str(created_utc)])
    cmd.extend(["--format", "text"])
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT.parent),
        text=True,
        capture_output=True,
    )
    rc = int(proc.returncode)
    report_files = _collect_tool_reports(candidate_root, tool_outdir)
    entry = {
        "returncode": rc,
        "ok": bool(rc == 0),
        "report_files": report_files,
    }
    if rc == 0:
        return entry, None
    marker = _detect_marker(proc.stderr or "", tool_name)
    error = {
        "tool": str(tool_name),
        "marker": str(marker or ""),
        "message": _sanitize_message(proc.stderr if (proc.stderr or "").strip() else (proc.stdout or "")),
    }
    return entry, error


def _run_custom_subtool(
    *,
    tool_name: str,
    cmd: Sequence[str],
    tool_outdir: Path,
    candidate_root: Path,
    env_overrides: Optional[Mapping[str, str]] = None,
) -> Tuple[Dict[str, Any], Optional[Dict[str, str]]]:
    tool_outdir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if isinstance(env_overrides, Mapping):
        for key, value in env_overrides.items():
            env[str(key)] = str(value)
    proc = subprocess.run(
        [str(x) for x in list(cmd)],
        cwd=str(ROOT.parent),
        text=True,
        capture_output=True,
        env=env,
    )
    rc = int(proc.returncode)
    report_files = _collect_tool_reports(candidate_root, tool_outdir)
    entry = _subtool_entry(returncode=rc, ok=(rc == 0), report_files=report_files)
    if rc == 0:
        return entry, None
    message = proc.stderr if (proc.stderr or "").strip() else (proc.stdout or "")
    marker = _detect_marker(str(message), tool_name)
    return entry, {
        "tool": str(tool_name),
        "marker": str(marker or ""),
        "message": _sanitize_message(message),
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_executable(path: Path, text: str) -> None:
    _write_text(path, text)
    path.chmod(0o755)


def _write_manifest_files(outdir: Path, payload: Mapping[str, Any]) -> None:
    _write_text(outdir / "DOSSIER_MANIFEST.json", _json_pretty(payload))
    _write_text(outdir / "DOSSIER_MANIFEST.md", _build_manifest_markdown(payload))


def _build_candidate_reproduce_script(
    *,
    rel_candidate_dir: str,
    base_args: Sequence[str],
    created_utc: str,
    joint_extra_args: Sequence[str],
    fsigma8_extra_args: Sequence[str],
    eft_extra_args: Sequence[str],
    class_extra_args: Sequence[str],
    include_class_mapping_report: bool,
    include_class_run: bool,
    class_runner: str,
    class_bin_basename: str,
    class_require_pinned_image: bool,
    spectra_require_tt: str,
    spectra_require_ell_max_ge: Optional[int],
    class_docker_image_ref: str,
) -> str:
    quoted = shlex.quote
    lines: List[str] = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "cd \"$(dirname \"$0\")/../..\"",
        "",
    ]

    def _emit(script_rel: str, out_rel: str, extras: Sequence[str], include_created: bool) -> None:
        cmd = [
            "python3",
            f"v11.0.0/scripts/{script_rel}",
            *list(base_args),
            *list(extras),
            "--outdir",
            str(out_rel),
        ]
        if include_created:
            cmd.extend(["--created-utc", str(created_utc)])
        cmd.extend(["--format", "text"])
        lines.append(" ".join(quoted(token) for token in cmd))

    _emit(
        "phase3_joint_sigmatensor_lowz_report.py",
        f"{rel_candidate_dir}/joint",
        joint_extra_args,
        True,
    )
    _emit(
        "phase3_sf_sigmatensor_fsigma8_report.py",
        f"{rel_candidate_dir}/fsigma8",
        fsigma8_extra_args,
        True,
    )
    _emit(
        "phase3_pt_sigmatensor_eft_export_pack.py",
        f"{rel_candidate_dir}/eft",
        eft_extra_args,
        False,
    )
    _emit(
        "phase3_pt_sigmatensor_class_export_pack.py",
        f"{rel_candidate_dir}/class",
        class_extra_args,
        False,
    )
    if bool(include_class_mapping_report):
        class_mapping_cmd = [
            "python3",
            "v11.0.0/scripts/phase3_pt_sigmatensor_class_mapping_report.py",
            "--export-pack",
            f"{rel_candidate_dir}/class",
            "--outdir",
            f"{rel_candidate_dir}/class_mapping",
            "--created-utc",
            str(created_utc),
            "--format",
            "text",
        ]
        lines.append(" ".join(quoted(token) for token in class_mapping_cmd))
    if bool(include_class_run):
        if str(class_runner) == "native":
            lines.extend(
                [
                    "",
                    "# Optional CLASS run pipeline (native)",
                    "# Set GSC_CLASS_BIN if --class-bin was not provided to dossier generation.",
                ]
            )
            if str(class_bin_basename):
                lines.append(f"# class-bin basename captured at dossier build time: {class_bin_basename}")
            class_run_cmd = [
                "python3",
                "v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py",
                "--export-pack",
                f"{rel_candidate_dir}/class",
                "--code",
                "class",
                "--runner",
                "native",
                "--run-dir",
                f"{rel_candidate_dir}/class_run",
                "--created-utc",
                str(created_utc),
                "--overwrite",
                "--format",
                "text",
            ]
            if str(class_bin_basename):
                class_run_cmd.extend(["--bin", str(class_bin_basename)])
            lines.append(" ".join(quoted(token) for token in class_run_cmd))
        else:
            lines.extend(
                [
                    "",
                    "# Optional CLASS run pipeline (docker)",
                    "# Ensure docker is installed and optionally set GSC_CLASS_DOCKER_IMAGE.",
                ]
            )
            if str(class_docker_image_ref):
                lines.append(f"# docker image ref fragment captured: {class_docker_image_ref}")
            class_run_cmd = [
                "python3",
                "v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py",
                "--export-pack",
                f"{rel_candidate_dir}/class",
                "--code",
                "class",
                "--runner",
                "docker",
                "--run-dir",
                f"{rel_candidate_dir}/class_run",
                "--created-utc",
                str(created_utc),
                "--overwrite",
                "--format",
                "text",
            ]
            if bool(class_require_pinned_image):
                class_run_cmd.append("--require-pinned-image")
            lines.append(" ".join(quoted(token) for token in class_run_cmd))

        class_results_cmd = [
            "python3",
            "v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py",
            "--export-pack",
            f"{rel_candidate_dir}/class",
            "--run-dir",
            f"{rel_candidate_dir}/class_run",
            "--code",
            "class",
            "--outdir",
            f"{rel_candidate_dir}/class_results",
            "--created-utc",
            str(created_utc),
            "--overwrite",
            "--format",
            "text",
        ]
        lines.append(" ".join(quoted(token) for token in class_results_cmd))

        spectra_cmd = [
            "python3",
            "v11.0.0/scripts/phase3_pt_spectra_sanity_report.py",
            "--path",
            f"{rel_candidate_dir}/class_results",
            "--outdir",
            f"{rel_candidate_dir}/spectra_sanity",
            "--created-utc",
            str(created_utc),
            "--require-tt",
            str(spectra_require_tt),
            "--format",
            "text",
        ]
        if spectra_require_ell_max_ge is not None:
            spectra_cmd.extend(["--require-ell-max-ge", str(int(spectra_require_ell_max_ge))])
        lines.append(" ".join(quoted(token) for token in spectra_cmd))
    lines.append("")
    return "\n".join(lines)


def _build_readme() -> str:
    lines = [
        "# Phase-3 candidate dossier pack (diagnostic)",
        "",
        "This pack contains deterministic triage artifacts for selected scan candidates.",
        "Scope boundary: diagnostic packaging only; this is not a global-fit claim.",
        "",
        "## Contents",
        "",
        "- `DOSSIER_MANIFEST.json`",
        "- `DOSSIER_MANIFEST.md`",
        "- `DOSSIER_QUICKLOOK.json/.csv/.md` (when quicklook emission is enabled)",
        "- `REPRODUCE_ALL.sh`",
        "- `candidates/cand_*/` with per-candidate subtool outputs and `REPRODUCE.sh`",
        "",
        "## Re-run",
        "",
        "Run `bash REPRODUCE_ALL.sh` from the dossier root.",
        "",
    ]
    return "\n".join(lines)


def _build_manifest_markdown(payload: Mapping[str, Any]) -> str:
    selection = _as_mapping(payload.get("selection"))
    counts = _as_mapping(payload.get("counts"))
    candidates = payload.get("candidates")
    rows = candidates if isinstance(candidates, list) else []
    lines: List[str] = []
    lines.append("# Phase-3 candidate dossier manifest (diagnostic)")
    lines.append("")
    lines.append("Scope boundary: deterministic triage packaging only.")
    lines.append("")
    lines.append("## Selection")
    lines.append("")
    lines.append(f"- created_utc: `{payload.get('created_utc')}`")
    lines.append(f"- top_k: `{selection.get('top_k')}`")
    lines.append(f"- ranks: `{selection.get('ranks')}`")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- candidates_selected: `{counts.get('candidates_selected')}`")
    lines.append(f"- candidates_ok: `{counts.get('candidates_ok')}`")
    lines.append(f"- candidates_error: `{counts.get('candidates_error')}`")
    lines.append("")
    lines.append("## Candidates")
    lines.append("")
    lines.append("| rank | plan_point_id | status | outdir_rel |")
    lines.append("| --- | --- | --- | --- |")
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| {row.get('rank')} | {row.get('plan_point_id')} | {row.get('status')} | {row.get('outdir_rel')} |"
        )
    if not rows:
        lines.append("| NA | NA | NA | NA |")
    lines.append("")
    return "\n".join(lines) + "\n"


def _run_portable_lint(path: Path) -> Tuple[bool, str]:
    cmd: List[str] = [
        sys.executable,
        str(SCRIPT_PORTABLE_LINT),
        "--path",
        str(path),
        "--format",
        "text",
        "--include-glob",
        "*.json",
        "--include-glob",
        "*.jsonl",
        "--include-glob",
        "*.md",
        "--include-glob",
        "*.csv",
        "--include-glob",
        "*.ini",
        "--include-glob",
        "*.sh",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT.parent),
        text=True,
        capture_output=True,
    )
    ok = int(proc.returncode) == 0
    text = proc.stdout if (proc.stdout or "").strip() else (proc.stderr or "")
    return bool(ok), _sanitize_message(text)


def _write_deterministic_zip(outdir: Path, zip_out: Path) -> Tuple[int, str]:
    zip_out.parent.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(outdir):
        dirnames.sort()
        filenames.sort()
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if not path.is_file():
                continue
            if path.resolve() == zip_out.resolve():
                continue
            files.append(path)
    files = sorted(files, key=lambda p: p.relative_to(outdir).as_posix())
    with zipfile.ZipFile(zip_out, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = path.relative_to(outdir).as_posix()
            arcname = f"GSC_DOSSIER/{rel}"
            info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_ZIP_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = path.stat().st_mode & 0o777
            info.create_system = 3
            info.external_attr = ((0o100000 | mode) & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return int(zip_out.stat().st_size), _sha256_file(zip_out)


def _write_zip_sha256_sidecar(zip_out: Path, sha256_hex: str) -> Path:
    sidecar = Path(str(zip_out) + ".sha256")
    _write_text(sidecar, f"{sha256_hex}  {zip_out.name}\n")
    return sidecar


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_extra_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        analysis_path = Path(args.analysis).expanduser().resolve()
        if not analysis_path.is_file():
            raise UsageError(f"--analysis not found: {analysis_path}")
        try:
            analysis_payload = json.loads(analysis_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise UsageError(f"--analysis parse failed: {exc}") from exc
        if not isinstance(analysis_payload, Mapping):
            raise UsageError("--analysis root must be a JSON object")
        schema = str(analysis_payload.get("schema") or "")
        if schema != ANALYSIS_SCHEMA:
            raise UsageError(f"--analysis schema mismatch: expected {ANALYSIS_SCHEMA}, got {schema or 'missing'}")

        ranks = _parse_ranks_csv(args.ranks)
        selected = _select_candidates(analysis_payload, top_k=int(args.top_k), ranks=ranks)
        if not selected:
            raise GateError("no candidates selected from analysis input")

        outdir = Path(args.outdir).expanduser().resolve()
        _ensure_empty_outdir(outdir)
        candidates_root = outdir / "candidates"
        candidates_root.mkdir(parents=True, exist_ok=True)

        _write_text(outdir / "README.md", _build_readme())

        joint_extra_args = [str(x) for x in list(args.joint_extra_arg or [])]
        fsigma8_extra_args = _normalize_fsigma8_args([str(x) for x in list(args.fsigma8_extra_arg or [])])
        eft_extra_args = [str(x) for x in list(args.eft_extra_arg or [])]
        class_extra_args = [str(x) for x in list(args.class_extra_arg or [])]
        include_class_mapping_report = bool(str(args.include_class_mapping_report) == "1")
        include_class_run = bool(str(args.include_class_run) == "1")
        emit_quicklook = bool(str(args.emit_quicklook) == "1")
        class_runner = str(args.class_runner)
        class_bin_raw = str(args.class_bin).strip() if args.class_bin is not None else ""
        class_bin_basename = _basename_or_empty(class_bin_raw)
        class_docker_image_raw = str(args.class_docker_image).strip() if args.class_docker_image is not None else ""
        class_docker_image_ref = _image_ref_for_manifest(class_docker_image_raw)
        class_require_pinned_image = bool(str(args.class_require_pinned_image) == "1")
        spectra_require_tt = str(args.spectra_require_tt)
        spectra_require_ell_max_ge = (
            int(args.spectra_require_ell_max_ge) if args.spectra_require_ell_max_ge is not None else None
        )

        subtool_names: List[str] = ["joint", "fsigma8", "eft", "class"]
        if include_class_mapping_report:
            subtool_names.append("class_mapping")
        if include_class_run:
            subtool_names.extend(["class_run", "class_results", "spectra_sanity"])

        def _failed_subtools(returncode: int) -> Dict[str, Any]:
            return {
                str(name): _subtool_entry(returncode=int(returncode), ok=False, report_files=[])
                for name in list(subtool_names)
            }

        manifest_candidates: List[Dict[str, Any]] = []
        fail_fast = str(args.fail_fast) == "1"
        stop_after_index: Optional[int] = None

        for idx, candidate in enumerate(selected):
            if stop_after_index is not None:
                break
            rank = candidate.get("rank")
            if not isinstance(rank, int) or isinstance(rank, bool):
                raise UsageError("analysis best_candidates contains non-integer rank")
            plan_point_id = str(candidate.get("plan_point_id") or "").strip()
            if not plan_point_id:
                raise UsageError("analysis best_candidates contains empty plan_point_id")
            safe_prefix = _sanitize_plan_prefix(plan_point_id)
            cand_name = f"cand_{int(rank):02d}_{safe_prefix}"
            cand_root = candidates_root / cand_name
            (cand_root / "params").mkdir(parents=True, exist_ok=True)
            rel_candidate_dir = f"candidates/{cand_name}"

            params_raw = _as_mapping(candidate.get("params"))
            params_payload = {
                "schema": "phase3_sigmatensor_candidate_params_v1",
                "rank": int(rank),
                "plan_point_id": str(plan_point_id),
                "params": {
                    "Omega_m": params_raw.get("Omega_m"),
                    "w0": params_raw.get("w0"),
                    "lambda": params_raw.get("lambda"),
                    "H0_km_s_Mpc": params_raw.get("H0_km_s_Mpc"),
                    "Tcmb_K": params_raw.get("Tcmb_K"),
                    "N_eff": params_raw.get("N_eff"),
                    "Omega_r0_override": params_raw.get("Omega_r0_override"),
                    "sign_u0": params_raw.get("sign_u0"),
                },
                "source": {
                    "analysis_rank": int(rank),
                    "analysis_plan_source_sha256": str(candidate.get("plan_source_sha256") or ""),
                    "analysis_scan_config_sha256": str(candidate.get("scan_config_sha256") or ""),
                },
            }
            _write_text(cand_root / "params" / "CANDIDATE_PARAMS.json", _json_pretty(params_payload))

            candidate_row: Dict[str, Any] = {
                "rank": int(rank),
                "plan_point_id": str(plan_point_id),
                "outdir_rel": rel_candidate_dir,
                "status": "ok",
                "params": _as_mapping(params_payload.get("params")),
                "subtools": {},
                "errors": [],
            }

            try:
                base_args = _build_base_model_args(params_raw)
            except UsageError as exc:
                candidate_row["status"] = "error"
                candidate_row["errors"] = [{"tool": "params", "marker": "", "message": _sanitize_message(str(exc))}]
                candidate_row["subtools"] = _failed_subtools(returncode=1)
                manifest_candidates.append(candidate_row)
                if fail_fast:
                    stop_after_index = idx
                continue

            subtools: Dict[str, Any] = {}
            candidate_errors: List[Dict[str, str]] = []

            joint_entry, joint_error = _run_subtool(
                tool_name="joint",
                script_path=SCRIPT_JOINT,
                base_args=base_args,
                extra_args=joint_extra_args,
                created_utc=created_utc,
                tool_outdir=cand_root / "joint",
                candidate_root=cand_root,
                include_created_utc=True,
            )
            subtools["joint"] = joint_entry
            if joint_error is not None:
                candidate_errors.append(joint_error)

            fsigma8_entry, fsigma8_error = _run_subtool(
                tool_name="fsigma8",
                script_path=SCRIPT_FSIGMA8,
                base_args=base_args,
                extra_args=fsigma8_extra_args,
                created_utc=created_utc,
                tool_outdir=cand_root / "fsigma8",
                candidate_root=cand_root,
                include_created_utc=True,
            )
            subtools["fsigma8"] = fsigma8_entry
            if fsigma8_error is not None:
                candidate_errors.append(fsigma8_error)

            eft_entry, eft_error = _run_subtool(
                tool_name="eft",
                script_path=SCRIPT_EFT,
                base_args=base_args,
                extra_args=eft_extra_args,
                created_utc=created_utc,
                tool_outdir=cand_root / "eft",
                candidate_root=cand_root,
                include_created_utc=False,
            )
            subtools["eft"] = eft_entry
            if eft_error is not None:
                candidate_errors.append(eft_error)

            class_entry, class_error = _run_subtool(
                tool_name="class",
                script_path=SCRIPT_CLASS,
                base_args=base_args,
                extra_args=class_extra_args,
                created_utc=created_utc,
                tool_outdir=cand_root / "class",
                candidate_root=cand_root,
                include_created_utc=False,
            )
            subtools["class"] = class_entry
            if class_error is not None:
                candidate_errors.append(class_error)

            if include_class_mapping_report:
                if bool(class_entry.get("ok") is True):
                    class_mapping_cmd: List[str] = [
                        sys.executable,
                        str(SCRIPT_CLASS_MAPPING),
                        "--export-pack",
                        str(cand_root / "class"),
                        "--outdir",
                        str(cand_root / "class_mapping"),
                        "--created-utc",
                        str(created_utc),
                        "--format",
                        "text",
                    ]
                    class_mapping_entry, class_mapping_error = _run_custom_subtool(
                        tool_name="class_mapping",
                        cmd=class_mapping_cmd,
                        tool_outdir=cand_root / "class_mapping",
                        candidate_root=cand_root,
                    )
                    subtools["class_mapping"] = class_mapping_entry
                    if class_mapping_error is not None:
                        candidate_errors.append(class_mapping_error)
                else:
                    subtools["class_mapping"] = _subtool_entry(returncode=2, ok=False, report_files=[])

            if include_class_run:
                class_pipeline_should_run = bool(class_entry.get("ok") is True)
                if not class_pipeline_should_run:
                    subtools["class_run"] = _subtool_entry(returncode=2, ok=False, report_files=[])
                    subtools["class_results"] = _subtool_entry(returncode=2, ok=False, report_files=[])
                    subtools["spectra_sanity"] = _subtool_entry(returncode=2, ok=False, report_files=[])
                    candidate_errors.append(
                        {
                            "tool": "class_pipeline",
                            "marker": FAIL_MARKER,
                            "message": "class pipeline skipped because class export failed",
                        }
                    )
                else:
                    class_run_cmd: List[str] = [
                        sys.executable,
                        str(SCRIPT_CLASS_RUN),
                        "--export-pack",
                        str(cand_root / "class"),
                        "--code",
                        "class",
                        "--runner",
                        str(class_runner),
                        "--run-dir",
                        str(cand_root / "class_run"),
                        "--created-utc",
                        str(created_utc),
                        "--overwrite",
                        "--format",
                        "text",
                    ]
                    class_run_env: Dict[str, str] = {}
                    if str(class_runner) == "native" and str(class_bin_raw):
                        class_run_cmd.extend(["--bin", str(class_bin_raw)])
                    if str(class_runner) == "docker":
                        if str(class_docker_image_raw):
                            class_run_env["GSC_CLASS_DOCKER_IMAGE"] = str(class_docker_image_raw)
                        if bool(class_require_pinned_image):
                            class_run_cmd.append("--require-pinned-image")

                    class_run_entry, class_run_error = _run_custom_subtool(
                        tool_name="class_run",
                        cmd=class_run_cmd,
                        tool_outdir=cand_root / "class_run",
                        candidate_root=cand_root,
                        env_overrides=class_run_env,
                    )
                    subtools["class_run"] = class_run_entry
                    if class_run_error is not None:
                        candidate_errors.append(class_run_error)

                    if bool(class_run_entry.get("ok") is True):
                        class_results_cmd: List[str] = [
                            sys.executable,
                            str(SCRIPT_CLASS_RESULTS),
                            "--export-pack",
                            str(cand_root / "class"),
                            "--run-dir",
                            str(cand_root / "class_run"),
                            "--code",
                            "class",
                            "--outdir",
                            str(cand_root / "class_results"),
                            "--created-utc",
                            str(created_utc),
                            "--overwrite",
                            "--format",
                            "text",
                        ]
                        class_results_entry, class_results_error = _run_custom_subtool(
                            tool_name="class_results",
                            cmd=class_results_cmd,
                            tool_outdir=cand_root / "class_results",
                            candidate_root=cand_root,
                        )
                        subtools["class_results"] = class_results_entry
                        if class_results_error is not None:
                            candidate_errors.append(class_results_error)

                        if bool(class_results_entry.get("ok") is True):
                            spectra_cmd: List[str] = [
                                sys.executable,
                                str(SCRIPT_SPECTRA_SANITY),
                                "--path",
                                str(cand_root / "class_results"),
                                "--outdir",
                                str(cand_root / "spectra_sanity"),
                                "--created-utc",
                                str(created_utc),
                                "--require-tt",
                                str(spectra_require_tt),
                                "--format",
                                "text",
                            ]
                            if spectra_require_ell_max_ge is not None:
                                spectra_cmd.extend(["--require-ell-max-ge", str(int(spectra_require_ell_max_ge))])
                            spectra_entry, spectra_error = _run_custom_subtool(
                                tool_name="spectra_sanity",
                                cmd=spectra_cmd,
                                tool_outdir=cand_root / "spectra_sanity",
                                candidate_root=cand_root,
                            )
                            subtools["spectra_sanity"] = spectra_entry
                            if spectra_error is not None:
                                candidate_errors.append(spectra_error)
                        else:
                            subtools["spectra_sanity"] = _subtool_entry(returncode=2, ok=False, report_files=[])
                    else:
                        subtools["class_results"] = _subtool_entry(returncode=2, ok=False, report_files=[])
                        subtools["spectra_sanity"] = _subtool_entry(returncode=2, ok=False, report_files=[])

            candidate_row["subtools"] = subtools
            candidate_row["errors"] = candidate_errors
            if candidate_errors:
                candidate_row["status"] = "error"
                if fail_fast:
                    stop_after_index = idx

            _write_executable(
                cand_root / "REPRODUCE.sh",
                _build_candidate_reproduce_script(
                    rel_candidate_dir=rel_candidate_dir,
                    base_args=base_args,
                    created_utc=created_utc,
                    joint_extra_args=joint_extra_args,
                    fsigma8_extra_args=fsigma8_extra_args,
                    eft_extra_args=eft_extra_args,
                    class_extra_args=class_extra_args,
                    include_class_mapping_report=include_class_mapping_report,
                    include_class_run=include_class_run,
                    class_runner=class_runner,
                    class_bin_basename=class_bin_basename,
                    class_require_pinned_image=class_require_pinned_image,
                    spectra_require_tt=spectra_require_tt,
                    spectra_require_ell_max_ge=spectra_require_ell_max_ge,
                    class_docker_image_ref=class_docker_image_ref,
                ),
            )
            manifest_candidates.append(candidate_row)

        if stop_after_index is not None:
            for row in selected[int(stop_after_index) + 1 :]:
                rank = int(row.get("rank"))
                plan_point_id = str(row.get("plan_point_id") or "")
                safe_prefix = _sanitize_plan_prefix(plan_point_id)
                cand_name = f"cand_{int(rank):02d}_{safe_prefix}"
                manifest_candidates.append(
                    {
                        "rank": int(rank),
                        "plan_point_id": str(plan_point_id),
                        "outdir_rel": f"candidates/{cand_name}",
                        "status": "error",
                        "params": _as_mapping(row.get("params")),
                        "subtools": _failed_subtools(returncode=2),
                        "errors": [
                            {
                                "tool": "dossier",
                                "marker": FAIL_MARKER,
                                "message": "skipped due --fail-fast after previous candidate failure",
                            }
                        ],
                    }
                )

        manifest_candidates = sorted(manifest_candidates, key=lambda row: int(row.get("rank", 10**9)))

        reproduce_all_lines: List[str] = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
        ]
        for row in manifest_candidates:
            rel = str(row.get("outdir_rel") or "")
            if not rel:
                continue
            reproduce_all_lines.append(f"bash {shlex.quote(rel + '/REPRODUCE.sh')}")
        reproduce_all_lines.append("")
        _write_executable(outdir / "REPRODUCE_ALL.sh", "\n".join(reproduce_all_lines))

        selection_ranks = [int(row.get("rank")) for row in manifest_candidates if isinstance(row.get("rank"), int)]
        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "created_utc": str(created_utc),
            "analysis_input": {
                "basename": str(analysis_path.name),
                "sha256": _sha256_file(analysis_path),
            },
            "selection": {
                "top_k": int(args.top_k),
                "ranks": (selection_ranks if ranks is None else [int(x) for x in ranks]),
                "joint_extra_args": list(joint_extra_args),
                "fsigma8_extra_args": list(fsigma8_extra_args),
                "eft_extra_args": list(eft_extra_args),
                "class_extra_args": list(class_extra_args),
                "include_class_mapping_report": bool(include_class_mapping_report),
                "include_class_run": bool(include_class_run),
                "emit_quicklook": bool(emit_quicklook),
                "class_runner": str(class_runner),
                "class_bin_basename": str(class_bin_basename),
                "class_docker_image_ref": str(class_docker_image_ref),
                "class_require_pinned_image": bool(class_require_pinned_image),
                "spectra_require_tt": str(spectra_require_tt),
                "spectra_require_ell_max_ge": (
                    int(spectra_require_ell_max_ge) if spectra_require_ell_max_ge is not None else None
                ),
            },
            "counts": {
                "candidates_selected": int(len(manifest_candidates)),
                "candidates_ok": int(sum(1 for row in manifest_candidates if str(row.get("status")) == "ok")),
                "candidates_error": int(sum(1 for row in manifest_candidates if str(row.get("status")) != "ok")),
            },
            "candidates": manifest_candidates,
            "portable_content_lint": {
                "enabled": bool(str(args.lint_portable_content) == "1" and str(args.skip_portable_content_lint) != "1"),
                "ok": None,
                "message": "",
            },
            "dossier_reports": [],
            "digests": {},
        }
        _refresh_file_table_digest(payload, outdir)

        lint_enabled = bool(str(args.lint_portable_content) == "1" and str(args.skip_portable_content_lint) != "1")
        _write_manifest_files(outdir, payload)

        if bool(emit_quicklook):
            quicklook_cmd: List[str] = [
                sys.executable,
                str(SCRIPT_QUICKLOOK),
                "--dossier",
                str(outdir),
                "--outdir",
                str(outdir),
                "--created-utc",
                str(created_utc),
                "--format",
                "text",
            ]
            quicklook_proc = subprocess.run(
                quicklook_cmd,
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            quicklook_rc = int(quicklook_proc.returncode)
            quicklook_reports = _collect_named_reports(
                outdir,
                ("DOSSIER_QUICKLOOK.json", "DOSSIER_QUICKLOOK.csv", "DOSSIER_QUICKLOOK.md"),
            )
            payload["dossier_reports"] = quicklook_reports
            _refresh_file_table_digest(payload, outdir)
            if quicklook_rc != 0:
                quicklook_stderr = str(quicklook_proc.stderr or "")
                quicklook_stdout = str(quicklook_proc.stdout or "")
                quicklook_msg = _sanitize_message(
                    quicklook_stderr if quicklook_stderr.strip() else quicklook_stdout
                )
                payload.setdefault("errors", [])
                if isinstance(payload.get("errors"), list):
                    payload["errors"].append(
                        {
                            "tool": "quicklook",
                            "marker": QUICKLOOK_FAIL_MARKER,
                            "message": str(quicklook_msg or "quicklook report failed"),
                        }
                    )
            _write_manifest_files(outdir, payload)

        if lint_enabled:
            lint_ok_1, lint_message_1 = _run_portable_lint(outdir)
            payload["portable_content_lint"] = {
                "enabled": True,
                "ok": bool(lint_ok_1),
                "message": str(lint_message_1),
                "passes": [
                    {"name": "initial", "ok": bool(lint_ok_1), "message": str(lint_message_1)},
                ],
            }
            if not lint_ok_1:
                payload.setdefault("errors", [])
                if isinstance(payload.get("errors"), list):
                    payload["errors"].append(
                        {
                            "tool": "portable_content_lint",
                            "marker": LINT_FAIL_MARKER,
                            "message": str(lint_message_1),
                        }
                    )
            _write_manifest_files(outdir, payload)

            lint_ok_2, lint_message_2 = _run_portable_lint(outdir)
            lint_ok = bool(lint_ok_1 and lint_ok_2)
            lint_message = (
                f"initial={str(lint_message_1)}; final={str(lint_message_2)}"
            )
            payload["portable_content_lint"] = {
                "enabled": True,
                "ok": bool(lint_ok),
                "message": str(lint_message),
                "passes": [
                    {"name": "initial", "ok": bool(lint_ok_1), "message": str(lint_message_1)},
                    {"name": "final", "ok": bool(lint_ok_2), "message": str(lint_message_2)},
                ],
            }
            if not lint_ok and (lint_ok_1 and not lint_ok_2):
                payload.setdefault("errors", [])
                if isinstance(payload.get("errors"), list):
                    payload["errors"].append(
                        {
                            "tool": "portable_content_lint",
                            "marker": LINT_FAIL_MARKER,
                            "message": str(lint_message_2),
                        }
                    )
            _write_manifest_files(outdir, payload)
        else:
            payload["portable_content_lint"] = {
                "enabled": False,
                "ok": None,
                "message": "disabled",
            }
            _write_manifest_files(outdir, payload)

        emit_zip = str(args.emit_zip) == "1"
        zip_summary: Optional[Dict[str, Any]] = None
        if emit_zip:
            max_mb = _finite_float(args.max_mb, name="--max-mb")
            if max_mb < 0.0:
                raise UsageError("--max-mb must be >= 0")
            zip_out = Path(args.zip_out).expanduser().resolve() if args.zip_out is not None else outdir.parent / f"{outdir.name}.zip"
            lint_ok_flag = True
            if lint_enabled:
                lint_state = _as_mapping(payload.get("portable_content_lint"))
                lint_ok_flag = bool(lint_state.get("ok") is True)
            if lint_ok_flag:
                zip_bytes, zip_sha256 = _write_deterministic_zip(outdir, zip_out)
                _write_zip_sha256_sidecar(zip_out, zip_sha256)
                zip_summary = {
                    "basename": str(zip_out.name),
                    "bytes": int(zip_bytes),
                    "sha256": str(zip_sha256),
                    "sha256_sidecar_basename": f"{zip_out.name}.sha256",
                }
                if float(zip_bytes) > float(max_mb) * 1024.0 * 1024.0:
                    payload.setdefault("errors", [])
                    if isinstance(payload.get("errors"), list):
                        payload["errors"].append(
                            {
                                "tool": "zip",
                                "marker": ZIP_BUDGET_FAIL_MARKER,
                                "message": (
                                    f"zip size exceeds budget: bytes={zip_bytes} max_mb={float(max_mb):.6g}"
                                ),
                            }
                        )
                    _write_manifest_files(outdir, payload)
        elif args.zip_out is not None:
            raise UsageError("--zip-out is only valid when --emit-zip 1")

        summary = {
            "schema": "phase3_sigmatensor_candidate_dossier_summary_v1",
            "tool": TOOL,
            "created_utc": str(created_utc),
            "candidates_selected": int(payload["counts"]["candidates_selected"]),
            "candidates_ok": int(payload["counts"]["candidates_ok"]),
            "candidates_error": int(payload["counts"]["candidates_error"]),
            "outdir": outdir.name,
        }
        if emit_zip and isinstance(zip_summary, Mapping):
            summary["zip"] = dict(zip_summary)

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
        sys.stdout.write(
            "dossier "
            f"selected={int(summary['candidates_selected'])} "
            f"ok={int(summary['candidates_ok'])} "
            f"error={int(summary['candidates_error'])}\n"
        )

    payload_errors = payload.get("errors")
    has_payload_errors = isinstance(payload_errors, list) and len(payload_errors) > 0
    if int(summary["candidates_error"]) > 0 or has_payload_errors:
        print(FAIL_MARKER, file=sys.stderr)
        if isinstance(payload_errors, list):
            for row in payload_errors:
                if not isinstance(row, Mapping):
                    continue
                marker = str(row.get("marker") or "")
                message = str(row.get("message") or "")
                if marker:
                    print(marker, file=sys.stderr)
                if message:
                    print(f"ERROR: {message}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
