#!/usr/bin/env python3
"""Deterministic spectra-sanity report for external CLASS/CAMB outputs.

Scope:
- file-format and finite-value sanity checks only
- no likelihood fitting and no claim of data agreement
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile


TOOL_NAME = "phase3_pt_spectra_sanity_report"
SCHEMA_NAME = "phase3_spectra_sanity_report_v1"
FAIL_MARKER = "PHASE3_SPECTRA_SANITY_FAILED"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"

_CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")


class UsageError(Exception):
    """CLI/IO usage error (exit 1)."""


class GateError(Exception):
    """Deterministic gate failure (exit 2)."""


def _normalize_created_utc(value: str) -> str:
    text = str(value or "").strip()
    if not _CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _safe_zip_name(name: str) -> bool:
    p = PurePosixPath(str(name).replace("\\", "/"))
    return not p.is_absolute() and ".." not in p.parts


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (int(info.external_attr) >> 16) & 0xFFFF
    return (mode & 0o170000) == 0o120000


def _find_root_with_layout(extract_root: Path) -> Path:
    candidates: List[Path] = []
    for path in [extract_root, *sorted([p for p in extract_root.rglob("*") if p.is_dir()], key=lambda p: p.as_posix())]:
        if (path / "RESULTS_SUMMARY.json").is_file() and (path / "outputs").is_dir():
            candidates.append(path)
    if candidates:
        return sorted(candidates, key=lambda p: p.as_posix())[0]

    run_candidates: List[Path] = []
    for path in [extract_root, *sorted([p for p in extract_root.rglob("*") if p.is_dir()], key=lambda p: p.as_posix())]:
        if (path / "RUN_METADATA.json").is_file():
            run_candidates.append(path)
    if run_candidates:
        return sorted(run_candidates, key=lambda p: p.as_posix())[0]

    top_dirs = sorted([p for p in extract_root.iterdir() if p.is_dir()], key=lambda p: p.name)
    top_files = sorted([p for p in extract_root.iterdir() if p.is_file()], key=lambda p: p.name)
    if len(top_dirs) == 1 and not top_files:
        return top_dirs[0]
    return extract_root


def _prepare_input_root(path_arg: str) -> Tuple[str, Path, Optional[tempfile.TemporaryDirectory]]:
    src = Path(str(path_arg)).expanduser().resolve()
    if src.is_dir():
        return "dir", src, None
    if src.is_file() and src.suffix.lower() == ".zip":
        td = tempfile.TemporaryDirectory(prefix="phase3_spectra_sanity_")
        root = Path(td.name)
        with zipfile.ZipFile(src, "r") as zf:
            for info in sorted(zf.infolist(), key=lambda x: x.filename):
                name = str(info.filename).replace("\\", "/")
                if not name or name.endswith("/"):
                    continue
                if not _safe_zip_name(name):
                    td.cleanup()
                    raise UsageError(f"unsafe zip member path: {name}")
                if _is_zip_symlink(info):
                    td.cleanup()
                    raise UsageError(f"zip symlink member is not allowed: {name}")
                dst = root / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(zf.read(info))
        return "zip", _find_root_with_layout(root), td
    raise UsageError("--path must be an existing directory or .zip file")


def _infer_layout(root: Path) -> Tuple[str, Path]:
    if (root / "RESULTS_SUMMARY.json").is_file() and (root / "outputs").is_dir():
        return "results_pack", root / "outputs"
    if (root / "RUN_METADATA.json").is_file():
        return "run_dir", root
    return "unknown", root


def _infer_code(root: Path, layout: str) -> Optional[str]:
    if layout == "results_pack":
        try:
            payload = json.loads((root / "RESULTS_SUMMARY.json").read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        code = payload.get("code") if isinstance(payload, Mapping) else None
        if isinstance(code, Mapping):
            name = str(code.get("name", "")).strip().lower()
            if name in {"class", "camb"}:
                return name
    if (root / "RUN_METADATA.json").is_file():
        try:
            payload = json.loads((root / "RUN_METADATA.json").read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        code = str(payload.get("code", "")).strip().lower() if isinstance(payload, Mapping) else ""
        if code in {"class", "camb"}:
            return code
    return None


def _split_line_tokens(line: str) -> List[str]:
    normalized = str(line).replace(",", " ").replace(";", " ").replace("\t", " ")
    return [tok for tok in normalized.split() if tok]


def _norm_header_token(tok: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", str(tok).strip().lower())


def _extract_header_and_map(path: Path) -> Tuple[List[str], Dict[str, int]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], {}
    lines = text.splitlines()[:100]
    header_tokens: List[str] = []
    column_map: Dict[str, int] = {}

    for raw in lines:
        line = str(raw).strip()
        if not line:
            continue
        if not (line.startswith("#") or line.startswith("%") or line.startswith("//")):
            # stop header search at first non-comment line
            break
        body = line.lstrip("#%/ ").strip()
        if not body:
            continue
        toks = _split_line_tokens(body)
        if not toks:
            continue
        norm = [_norm_header_token(t) for t in toks]
        if not any(any(c.isalpha() for c in n) for n in norm):
            continue
        header_tokens = toks
        for idx, nt in enumerate(norm):
            if "ell" not in column_map and nt in {"l", "ell"}:
                column_map["ell"] = idx
            if "TT" not in column_map and nt in {"tt", "cltt"}:
                column_map["TT"] = idx
            if "EE" not in column_map and nt in {"ee", "clee"}:
                column_map["EE"] = idx
            if "TE" not in column_map and nt in {"te", "clte"}:
                column_map["TE"] = idx
            if "BB" not in column_map and nt in {"bb", "clbb"}:
                column_map["BB"] = idx
        if header_tokens:
            break
    return header_tokens, column_map


def _score_candidate(relpath: str, header_map: Mapping[str, int]) -> int:
    score = 0
    if "TT" in header_map:
        score += 50
    if "EE" in header_map or "TE" in header_map:
        score += 10
    name = relpath.lower()
    if "cl" in name:
        score += 5
    if name.endswith("cl.dat"):
        score += 2
    return score


def _collect_candidates(base_root: Path, outputs_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(outputs_root.rglob("*.dat")):
        if not path.is_file():
            continue
        rel = path.relative_to(base_root).as_posix()
        if rel.startswith("inputs/") or "/inputs/" in f"/{rel}":
            continue
        header_tokens, column_map = _extract_header_and_map(path)
        rows.append(
            {
                "relpath": rel,
                "path": path,
                "header_tokens": header_tokens,
                "column_map": column_map,
                "score": _score_candidate(rel, column_map),
            }
        )
    rows.sort(key=lambda r: (-int(r["score"]), str(r["relpath"])))
    return rows


def _parse_spectrum_rows(
    path: Path,
    *,
    column_map: Mapping[str, int],
) -> Tuple[List[Tuple[float, float, Optional[float], Optional[float]]], Dict[str, int]]:
    ell_idx = int(column_map.get("ell", 0))
    tt_idx = int(column_map.get("TT", 1))
    ee_idx = int(column_map["EE"]) if "EE" in column_map else None
    te_idx = int(column_map["TE"]) if "TE" in column_map else None
    rows: List[Tuple[float, float, Optional[float], Optional[float]]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = str(raw).strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("%") or line.startswith("//"):
                continue
            parts = _split_line_tokens(line)
            need_idx = max(ell_idx, tt_idx, ee_idx if ee_idx is not None else -1, te_idx if te_idx is not None else -1)
            if len(parts) <= need_idx:
                continue
            ell = _finite_float(parts[ell_idx])
            tt = _finite_float(parts[tt_idx])
            if ell is None or tt is None:
                continue
            if ell <= 1.0:
                continue
            ee = _finite_float(parts[ee_idx]) if ee_idx is not None and len(parts) > ee_idx else None
            te = _finite_float(parts[te_idx]) if te_idx is not None and len(parts) > te_idx else None
            rows.append((float(ell), float(tt), ee, te))
    rows.sort(key=lambda r: r[0])
    used = {"ell": ell_idx, "TT": tt_idx}
    if ee_idx is not None:
        used["EE"] = ee_idx
    if te_idx is not None:
        used["TE"] = te_idx
    return rows, used


def _stable_digest(rows: Sequence[Tuple[float, float, Optional[float], Optional[float]]], *, include_ee_te: bool) -> str:
    lines: List[str] = []
    for ell, tt, ee, te in rows:
        if include_ee_te:
            ee_txt = _CSV_FMT(float(ee)) if ee is not None else "nan"
            te_txt = _CSV_FMT(float(te)) if te is not None else "nan"
            lines.append(f"{_CSV_FMT(ell)},{_CSV_FMT(tt)},{ee_txt},{te_txt}\n")
        else:
            lines.append(f"{_CSV_FMT(ell)},{_CSV_FMT(tt)}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _CSV_FMT(value: float) -> str:
    return f"{float(value):.12e}"


def _sanitize_no_abs(text: str) -> str:
    out = str(text)
    for token in _ABS_TOKENS:
        out = out.replace(token, "[abs]/")
    return out


def _build_payload(
    *,
    path_kind: str,
    base_root: Path,
    layout: str,
    outputs_root: Path,
    code_inferred: Optional[str],
    selected: Optional[Dict[str, Any]],
    rows: Sequence[Tuple[float, float, Optional[float], Optional[float]]],
    column_used: Mapping[str, int],
    created_utc: str,
    require_tt: bool,
    require_ell_max_ge: Optional[int],
) -> Dict[str, Any]:
    has_tt = bool(selected is not None and len(rows) >= 5)
    tt_metrics: Dict[str, Any] = {
        "has_tt": has_tt,
        "n_rows": int(len(rows)),
        "ell_min": None,
        "ell_max": None,
        "peak1_ell": None,
        "tt_min": None,
        "tt_max": None,
        "tt_negative_fraction": None,
        "note": "no parseable TT rows" if not has_tt else "parsed_tt_rows",
    }

    digest_rows = ""
    if has_tt:
        ells = [r[0] for r in rows]
        tts = [r[1] for r in rows]
        tt_metrics.update(
            {
                "ell_min": int(round(min(ells))),
                "ell_max": int(round(max(ells))),
                "tt_min": float(min(tts)),
                "tt_max": float(max(tts)),
                "tt_negative_fraction": float(sum(1 for x in tts if x < 0.0) / len(tts)),
            }
        )
        in_peak = [r for r in rows if 50.0 <= r[0] <= 4000.0]
        peak_pool = in_peak if in_peak else list(rows)
        peak = max(peak_pool, key=lambda r: r[1])
        tt_metrics["peak1_ell"] = int(round(peak[0]))
        include_ee_te = "EE" in column_used or "TE" in column_used
        digest_rows = _stable_digest(rows, include_ee_te=include_ee_te)

    gates: List[Dict[str, Any]] = []
    gate_require_tt = {
        "name": "require_tt",
        "enabled": bool(require_tt),
        "passed": True if not require_tt else bool(has_tt),
        "detail": f"has_tt={str(bool(has_tt)).lower()}",
    }
    gates.append(gate_require_tt)

    gate_ell = {
        "name": "require_ell_max_ge",
        "enabled": require_ell_max_ge is not None,
        "passed": True,
        "detail": f"ell_max={tt_metrics.get('ell_max')}",
    }
    if require_ell_max_ge is not None:
        ell_max_val = tt_metrics.get("ell_max")
        gate_ell["passed"] = bool(ell_max_val is not None and int(ell_max_val) >= int(require_ell_max_ge))
        gate_ell["detail"] = f"ell_max={ell_max_val} threshold={int(require_ell_max_ge)}"
    gates.append(gate_ell)

    selected_payload = {
        "relpath": selected["relpath"] if selected is not None else None,
        "sha256": _sha256_path(selected["path"]) if selected is not None else None,
        "header_tokens": list(selected.get("header_tokens", [])) if selected is not None else [],
        "column_map": {str(k): int(v) for k, v in sorted(column_used.items(), key=lambda kv: str(kv[0]))},
    }

    payload: Dict[str, Any] = {
        "tool": TOOL_NAME,
        "schema": SCHEMA_NAME,
        "created_utc": created_utc,
        "input": {
            "kind": str(path_kind),
            "inferred_layout": str(layout),
            "code_inferred": code_inferred,
            "used_outputs_root": outputs_root.relative_to(base_root).as_posix()
            if outputs_root != base_root
            else ".",
        },
        "selected_spectra_file": selected_payload,
        "tt_metrics": tt_metrics,
        "gates": gates,
        "digests": {
            "sha256_rows": digest_rows if digest_rows else None,
        },
    }
    return payload


def _render_md(*, payload: Mapping[str, Any]) -> str:
    inp = payload.get("input") if isinstance(payload.get("input"), Mapping) else {}
    sel = payload.get("selected_spectra_file") if isinstance(payload.get("selected_spectra_file"), Mapping) else {}
    tt = payload.get("tt_metrics") if isinstance(payload.get("tt_metrics"), Mapping) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []
    lines: List[str] = [
        "# Spectra sanity report",
        "",
        "Claim-safe scope: external spectra format/consistency sanity only.",
        "No likelihood fit and no model-selection claim is made here.",
        "",
        "## Input",
        f"- kind: `{inp.get('kind')}`",
        f"- inferred_layout: `{inp.get('inferred_layout')}`",
        f"- code_inferred: `{inp.get('code_inferred')}`",
        f"- used_outputs_root: `{inp.get('used_outputs_root')}`",
        "",
        "## Selected spectra file",
        f"- relpath: `{sel.get('relpath')}`",
        f"- sha256: `{sel.get('sha256')}`",
        f"- column_map: `{json.dumps(sel.get('column_map') or {}, sort_keys=True)}`",
        "",
        "## TT metrics",
        f"- has_tt: `{tt.get('has_tt')}`",
        f"- n_rows: `{tt.get('n_rows')}`",
        f"- ell range: `[{tt.get('ell_min')}, {tt.get('ell_max')}]`",
        f"- peak1_ell: `{tt.get('peak1_ell')}`",
        f"- tt_min/tt_max: `[{tt.get('tt_min')}, {tt.get('tt_max')}]`",
        f"- tt_negative_fraction: `{tt.get('tt_negative_fraction')}`",
        "",
        "## Gates",
    ]
    for row in gates:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- {row.get('name')}: enabled={bool(row.get('enabled'))} passed={bool(row.get('passed'))} detail=`{row.get('detail')}`"
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "```bash",
            "python3 v11.0.0/scripts/phase3_pt_spectra_sanity_report.py \\",
            "  --path <results_or_run_dir_or_zip> \\",
            "  --outdir <outdir> \\",
            "  --created-utc 2000-01-01T00:00:00Z \\",
            "  --require-tt 1 \\",
            "  --format text",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _render_text(payload: Mapping[str, Any]) -> str:
    inp = payload.get("input") if isinstance(payload.get("input"), Mapping) else {}
    sel = payload.get("selected_spectra_file") if isinstance(payload.get("selected_spectra_file"), Mapping) else {}
    tt = payload.get("tt_metrics") if isinstance(payload.get("tt_metrics"), Mapping) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []
    gate_failed = any(bool(g.get("enabled")) and not bool(g.get("passed")) for g in gates if isinstance(g, Mapping))
    return (
        f"tool={TOOL_NAME} layout={inp.get('inferred_layout')} code={inp.get('code_inferred')} "
        f"has_tt={tt.get('has_tt')} file={sel.get('relpath')} ell_min={tt.get('ell_min')} "
        f"ell_max={tt.get('ell_max')} peak1_ell={tt.get('peak1_ell')} "
        f"gates_ok={str(not gate_failed).lower()}\n"
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic spectra sanity report for external CLASS/CAMB outputs.")
    ap.add_argument("--path", required=True, help="results-pack/run-dir path or zip containing one")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--require-tt", choices=("0", "1"), default="1")
    ap.add_argument("--require-ell-max-ge", type=int, default=None)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    extracted_ctx: Optional[tempfile.TemporaryDirectory] = None
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        path_kind, base_root, extracted_ctx = _prepare_input_root(str(args.path))
        layout, outputs_root = _infer_layout(base_root)
        code_inferred = _infer_code(base_root, layout)

        candidates = _collect_candidates(base_root, outputs_root)
        selected = candidates[0] if candidates else None

        parsed_rows: List[Tuple[float, float, Optional[float], Optional[float]]] = []
        used_cols: Dict[str, int] = {}
        if selected is not None:
            parsed_rows, used_cols = _parse_spectrum_rows(
                selected["path"],
                column_map=selected.get("column_map", {}),
            )
            if len(parsed_rows) < 5:
                selected = selected.copy()
                selected["header_tokens"] = list(selected.get("header_tokens", []))
                selected["column_map"] = dict(selected.get("column_map", {}))
                # keep selected file reference for diagnostics; has_tt will stay false

        payload = _build_payload(
            path_kind=path_kind,
            base_root=base_root,
            layout=layout,
            outputs_root=outputs_root,
            code_inferred=code_inferred,
            selected=selected,
            rows=parsed_rows,
            column_used=used_cols,
            created_utc=created_utc,
            require_tt=(str(args.require_tt) == "1"),
            require_ell_max_ge=(None if args.require_ell_max_ge is None else int(args.require_ell_max_ge)),
        )

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        json_text = _json_text(payload)
        md_text = _render_md(payload=payload)
        # enforce portability text-level guard
        for token in _ABS_TOKENS:
            if token in json_text or token in md_text:
                json_text = _sanitize_no_abs(json_text)
                md_text = _sanitize_no_abs(md_text)
                break
        (outdir / "SPECTRA_SANITY_REPORT.json").write_text(json_text, encoding="utf-8")
        (outdir / "SPECTRA_SANITY_REPORT.md").write_text(md_text, encoding="utf-8")

        failed = [g for g in payload.get("gates", []) if isinstance(g, Mapping) and bool(g.get("enabled")) and not bool(g.get("passed"))]
        if failed:
            names = ",".join(str(g.get("name")) for g in failed)
            raise GateError(f"enabled gate(s) failed: {names}")

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
    finally:
        if extracted_ctx is not None:
            extracted_ctx.cleanup()

    if str(args.format) == "json":
        sys.stdout.write(json_text)
    else:
        sys.stdout.write(_render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

