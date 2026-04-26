#!/usr/bin/env python3
"""Deterministic Phase-4 epsilon-framework readiness audit (Task 4A.9 pre-check)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


TOOL = "phase4_epsilon_framework_readiness_audit"
TOOL_VERSION = "m147-v1"
SCHEMA = "phase4_epsilon_framework_readiness_audit_report_v1"
DEFAULT_REPO_ROOT = "v11.0.0"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")

TEXT_EXTS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".tex",
    ".bib",
}

PATH_HINTS = (
    "epsilon",
    "measurement_model",
    "precision",
    "equivalence",
    "clock",
    "drift",
    "pantheon",
    "bao",
    "likelihood",
    "constraint",
)

CONTENT_HINTS = (
    "epsilon",
    "equivalence principle",
    "precision test",
    "measurement model",
    "coupling model",
    "pantheon",
    "desi",
    "bao",
    "fine-structure",
    "alpha variation",
    "mu variation",
)


class UsageError(Exception):
    """Usage/configuration error (exit 1)."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _to_iso_utc(epoch_seconds: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    except Exception as exc:
        raise UsageError("--created-utc must be a valid integer epoch-seconds value") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_rel(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    for token in ABS_TOKENS:
        rel = rel.replace(token, "[abs]/")
    return rel


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _discover_epsilon_assets(repo_root: Path) -> List[str]:
    found: List[str] = []
    for p in sorted(repo_root.rglob("*")):
        if not p.is_file():
            continue
        rel = _safe_rel(p, repo_root)
        rel_l = rel.lower()

        if any(part.startswith(".") for part in Path(rel).parts):
            continue

        path_hit = any(hint in rel_l for hint in PATH_HINTS)
        content_hit = False

        if (not path_hit) and (p.suffix.lower() in TEXT_EXTS):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")[:200000]
            except Exception:
                text = ""
            text_l = text.lower()
            content_hit = any(hint in text_l for hint in CONTENT_HINTS)

        if path_hit or content_hit:
            found.append(rel)

    return sorted(set(found))


def _flag_any(paths: Iterable[str], patterns: Sequence[re.Pattern[str]]) -> bool:
    for rel in paths:
        for pat in patterns:
            if pat.search(rel):
                return True
    return False


def _build_code_support_flags(repo_root: Path, detected_assets: Sequence[str]) -> Dict[str, bool]:
    all_files = sorted(
        _safe_rel(p, repo_root) for p in repo_root.rglob("*") if p.is_file()
    )

    def _has(rel: str) -> bool:
        return (repo_root / rel).is_file()

    patterns = {
        "translator": (
            re.compile(r"(^|/)gsc/epsilon/translator(_module)?\.py$"),
            re.compile(r"(^|/)scripts/phase4_.*translator.*\.py$"),
        ),
        "precision_constraints": (
            re.compile(r"(^|/)gsc/epsilon/.*(precision|constraint|bound).*\.py$"),
            re.compile(r"(^|/)scripts/phase4_.*(precision|constraint|bound).*\.py$"),
        ),
        "coupling_combiner": (
            re.compile(r"(^|/).*(coupling_model|combine_bounds|joint_bound).*\.py$"),
        ),
        "pantheon_wiring": (
            re.compile(r"(^|/).*(pantheon|sn).*(epsilon|translator|likelihood).*\.py$"),
        ),
        "desi_bao_wiring": (
            re.compile(r"(^|/).*(desi|bao).*(epsilon|translator|likelihood).*\.py$"),
        ),
        "gitless_e2e": (
            re.compile(r"(^|/)tests/test_phase4_.*epsilon.*gitless.*\.py$"),
        ),
    }

    flags: Dict[str, bool] = {
        "has_translator_module": _flag_any(all_files, patterns["translator"]),
        "has_precision_constraints_code": _flag_any(all_files, patterns["precision_constraints"]),
        "has_coupling_model_combiner": _flag_any(all_files, patterns["coupling_combiner"]),
        "has_pantheon_plus_wiring": _flag_any(all_files, patterns["pantheon_wiring"]),
        "has_desi_bao_wiring": _flag_any(all_files, patterns["desi_bao_wiring"]),
        "has_measurement_model_core": _has("gsc/measurement_model.py"),
        "has_drift_sign_diagnostic": _has("scripts/phase4_sigmatensor_drift_sign_diagnostic.py"),
        "has_gap_diagnostic": _has("scripts/phase4_sigmatensor_optimal_control_gap_diagnostic.py"),
        "has_pantheon_plus_data": _has("data/sn/pantheon_plus_shoes/pantheon_plus_shoes_mu.csv"),
        "has_desi_bao_data": any(
            rel.startswith("data/bao/") and "desi" in rel.lower()
            for rel in all_files
        ),
        "has_epsilon_readiness_doc": _has("docs/EPSILON_FRAMEWORK_READINESS.md"),
        "has_epsilon_audit_schema": _has("schemas/phase4_epsilon_framework_readiness_audit_report_v1.schema.json"),
        "has_gitless_epsilon_audit_test": _flag_any(all_files, patterns["gitless_e2e"]),
    }

    return {k: bool(flags[k]) for k in sorted(flags.keys())}


def _gap_templates() -> List[Dict[str, Any]]:
    return [
        {
            "id": "TH-001",
            "severity": "high",
            "description": "Coupling-model conditionality for combining epsilon bounds is not encoded as a machine-readable policy.",
            "blocks": ["Paper-2", "Paper-3"],
            "suggested_owner": "theory",
            "requires_flag_false": "has_coupling_model_combiner",
        },
        {
            "id": "TH-002",
            "severity": "high",
            "description": "Translator module from SigmaTensor/measurement outputs to epsilon observables is missing.",
            "blocks": ["Paper-2"],
            "suggested_owner": "theory",
            "requires_flag_false": "has_translator_module",
        },
        {
            "id": "TH-003",
            "severity": "medium",
            "description": "No explicit basis/normalization contract for epsilon parameters across probes.",
            "blocks": ["Paper-2"],
            "suggested_owner": "theory",
            "requires_flag_false": "has_translator_module",
        },
        {
            "id": "TH-004",
            "severity": "medium",
            "description": "No canonical consistency checker for cross-probe sign conventions in epsilon mappings.",
            "blocks": ["Paper-2", "Paper-3"],
            "suggested_owner": "theory",
            "requires_flag_false": "has_precision_constraints_code",
        },
        {
            "id": "DATA-001",
            "severity": "high",
            "description": "Pantheon+ likelihood is not wired to epsilon translator outputs.",
            "blocks": ["Paper-2"],
            "suggested_owner": "data",
            "requires_flag_false": "has_pantheon_plus_wiring",
        },
        {
            "id": "DATA-002",
            "severity": "high",
            "description": "DESI BAO likelihood path is not wired to epsilon translator outputs.",
            "blocks": ["Paper-2"],
            "suggested_owner": "data",
            "requires_flag_false": "has_desi_bao_wiring",
        },
        {
            "id": "DATA-003",
            "severity": "medium",
            "description": "No deterministic joint low-z + epsilon diagnostic report combining SN/BAO with epsilon constraints.",
            "blocks": ["Paper-2", "Paper-3"],
            "suggested_owner": "data",
            "requires_flag_false": "has_pantheon_plus_wiring",
        },
        {
            "id": "IMPL-001",
            "severity": "high",
            "description": "No dedicated gsc/epsilon package API contract (module layout + typed I/O) for production use.",
            "blocks": ["Paper-2"],
            "suggested_owner": "implementation",
            "requires_flag_false": "has_translator_module",
        },
        {
            "id": "IMPL-002",
            "severity": "medium",
            "description": "No deterministic epsilon-focused report generator that couples translator outputs with precision constraints.",
            "blocks": ["Paper-2"],
            "suggested_owner": "implementation",
            "requires_flag_false": "has_precision_constraints_code",
        },
        {
            "id": "IMPL-003",
            "severity": "medium",
            "description": "No epsilon-specific unit/regression tests for translator outputs and coupling-policy branches.",
            "blocks": ["Paper-2", "Paper-3"],
            "suggested_owner": "implementation",
            "requires_flag_false": "has_translator_module",
        },
        {
            "id": "IMPL-004",
            "severity": "medium",
            "description": "No git-less end-to-end epsilon pipeline smoke test from snapshot to schema-validated outputs.",
            "blocks": ["Paper-2"],
            "suggested_owner": "implementation",
            "requires_flag_false": "has_gitless_epsilon_audit_test",
        },
        {
            "id": "IMPL-005",
            "severity": "low",
            "description": "No reviewer-pack integration row for epsilon artifacts in verification matrix bundles.",
            "blocks": ["Paper-2", "Paper-3"],
            "suggested_owner": "reviewer-ux",
            "requires_flag_false": "has_translator_module",
        },
    ]


def _build_gap_list(flags: Mapping[str, bool]) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    for row in _gap_templates():
        key = str(row.get("requires_flag_false"))
        if bool(flags.get(key, False)):
            continue
        out = {
            "id": str(row["id"]),
            "severity": str(row["severity"]),
            "description": str(row["description"]),
            "blocks": [str(x) for x in row.get("blocks", [])],
            "suggested_owner": str(row["suggested_owner"]),
        }
        gaps.append(out)
    return sorted(gaps, key=lambda x: (str(x.get("id")), str(x.get("severity"))))


def _recommended_tasks() -> List[str]:
    return [
        "M150: Pantheon+/DESI BAO epsilon wiring smoke path (gitless)",
        "M151: conditional bound-combination policy checker (coupling-model aware)",
        "M152: epsilon reviewer-pack integration profile with acceptance checks",
        "M153: epsilon precision-data report with explicit coupling-policy metadata",
    ]


def _snapshot_fingerprint(repo_root: Path) -> Dict[str, str]:
    candidates = [
        repo_root / "repo_snapshot_manifest.json",
        repo_root.parent / "repo_snapshot_manifest.json",
    ]
    for path in candidates:
        if path.is_file():
            return {
                "repo_snapshot_manifest_sha256": _sha256_file(path),
                "repo_snapshot_manifest_source": path.name,
            }

    git_dir = repo_root.parent / ".git"
    if git_dir.exists():
        proc = subprocess.run(
            ["git", "-C", str(repo_root.parent), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
        )
        if proc.returncode == 0:
            sha = (proc.stdout or "").strip()
            if re.fullmatch(r"[0-9a-f]{40}", sha):
                return {
                    "repo_snapshot_manifest_sha256": f"git:{sha}",
                    "repo_snapshot_manifest_source": "git_head_fallback",
                }

    return {
        "repo_snapshot_manifest_sha256": "unavailable",
        "repo_snapshot_manifest_source": "unavailable",
    }


def _render_md(payload: Mapping[str, Any]) -> str:
    flags = payload.get("code_support_flags") if isinstance(payload.get("code_support_flags"), Mapping) else {}
    gaps = payload.get("gap_list") if isinstance(payload.get("gap_list"), list) else []
    tasks = payload.get("recommended_next_tasks") if isinstance(payload.get("recommended_next_tasks"), list) else []

    lines: List[str] = []
    lines.append("# Epsilon Framework Readiness Audit")
    lines.append("")
    lines.append(f"- schema: `{payload.get('schema')}`")
    lines.append(f"- repo_version_dir: `{payload.get('repo_version_dir')}`")
    lines.append(f"- paths_redacted: `{bool(payload.get('paths_redacted'))}`")
    lines.append(f"- detected_assets_count: `{int(payload.get('detected_assets_count', 0))}`")
    lines.append("")
    lines.append("## Code support flags")
    for key in sorted(flags.keys()):
        lines.append(f"- {key}: `{bool(flags.get(key))}`")
    lines.append("")
    lines.append("## Gap list")
    lines.append("| id | severity | blocks | owner |")
    lines.append("|---|---|---|---|")
    for row in gaps:
        if not isinstance(row, Mapping):
            continue
        blocks = ", ".join(str(x) for x in row.get("blocks", []))
        lines.append(
            f"| {row.get('id')} | {row.get('severity')} | {blocks} | {row.get('suggested_owner')} |"
        )
    lines.append("")
    lines.append("## Recommended next tasks")
    for task in tasks:
        lines.append(f"- {task}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _render_text(payload: Mapping[str, Any]) -> str:
    lines = [
        f"schema={payload.get('schema')}",
        f"repo_version_dir={payload.get('repo_version_dir')}",
        f"detected_assets_count={int(payload.get('detected_assets_count', 0))}",
        f"gap_count={int(payload.get('gap_count', 0))}",
        f"paths_redacted={bool(payload.get('paths_redacted'))}",
    ]
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic readiness audit for epsilon-framework Phase-4 planning.")
    ap.add_argument("--repo-root", default=DEFAULT_REPO_ROOT)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--created-utc", type=int, default=None)
    ap.add_argument("--format", choices=("json", "text"), default="json")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        repo_root = Path(str(args.repo_root)).expanduser().resolve()
        if not repo_root.is_dir():
            raise UsageError(f"--repo-root directory not found: {repo_root}")

        if args.outdir is None:
            outdir = repo_root / "out" / "epsilon_readiness"
        else:
            outdir = Path(str(args.outdir)).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        deterministic = bool(int(args.deterministic))
        if args.created_utc is not None:
            created_epoch = int(args.created_utc)
        elif deterministic:
            created_epoch = DEFAULT_CREATED_UTC_EPOCH
        else:
            created_epoch = int(time.time())

        created_utc = _to_iso_utc(created_epoch)

        detected_assets = _discover_epsilon_assets(repo_root)
        flags = _build_code_support_flags(repo_root, detected_assets)
        gaps = _build_gap_list(flags)
        snapshot = _snapshot_fingerprint(repo_root)

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "repo_version_dir": repo_root.name,
            "paths_redacted": True,
            "deterministic_mode": deterministic,
            "repo_snapshot_manifest_sha256": str(snapshot["repo_snapshot_manifest_sha256"]),
            "repo_snapshot_manifest_source": str(snapshot["repo_snapshot_manifest_source"]),
            "detected_assets": [str(x) for x in detected_assets],
            "detected_assets_count": int(len(detected_assets)),
            "code_support_flags": flags,
            "gap_list": gaps,
            "gap_count": int(len(gaps)),
            "recommended_next_tasks": _recommended_tasks(),
        }

        json_path = outdir / "EPSILON_FRAMEWORK_READINESS_AUDIT.json"
        md_path = outdir / "EPSILON_FRAMEWORK_READINESS_AUDIT.md"

        json_path.write_text(_json_pretty(payload), encoding="utf-8")
        md_path.write_text(_render_md(payload), encoding="utf-8")

        if str(args.format) == "json":
            print(_json_pretty(payload), end="")
        else:
            print(_render_text(payload), end="")

        return 0
    except UsageError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
