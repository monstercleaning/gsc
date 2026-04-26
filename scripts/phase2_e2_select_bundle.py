#!/usr/bin/env python3
"""Deterministic stdlib-only selector for Phase-2 E2 bundles."""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
from pathlib import Path, PurePosixPath
import sys
import tarfile
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import zipfile


SCHEMA_ID = "phase2_e2_bundle_selector_v1"
SUPPORTED_ARCHIVE_SUFFIXES: Tuple[str, ...] = (".tar.gz", ".tgz", ".tar", ".zip")
MANIFEST_CANDIDATES: Tuple[str, ...] = (
    "manifest.json",
    "phase2_e2_manifest.json",
    "phase2_e2_manifest_v1.json",
)
CERTIFICATE_PREFERRED_SUFFIXES: Tuple[str, ...] = (
    "paper_assets/paper_assets_cmb_e2_drift_constrained_closure_bound/e2_certificate.json",
    "paper_assets/paper_assets_cmb_e2_closure_to_physical_knobs/e2_certificate.json",
)
MERGE_REPORT_SUFFIX = "merge_report.json"


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_relpath(text: str) -> str:
    raw = str(text or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("empty relpath")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe relpath: {raw}")
    norm = str(path)
    if norm in {"", "."}:
        raise ValueError(f"invalid relpath: {raw}")
    return norm


def _supports_archive(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(sfx) for sfx in SUPPORTED_ARCHIVE_SUFFIXES)


def _looks_like_extracted_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    for name in MANIFEST_CANDIDATES:
        if (path / name).is_file():
            return True
    matches = sorted(
        p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".json" and "manifest" in p.name.lower()
    )
    return len(matches) == 1


def _expand_path_token(token: str) -> List[Path]:
    if any(ch in token for ch in "*?["):
        p = Path(token)
        parent = Path(p.parent if str(p.parent) else ".")
        if not parent.exists():
            return []
        items = [child.resolve() for child in parent.iterdir() if fnmatch.fnmatch(child.name, p.name)]
        return sorted(items, key=lambda x: str(x))
    return [Path(token).expanduser().resolve()]


def _discover_bundles(inputs: Sequence[str]) -> Tuple[List[Path], int]:
    bundles: List[Path] = []
    seen: set[Path] = set()
    n_inputs = 0

    for raw in inputs:
        token = str(raw).strip()
        if not token:
            continue
        n_inputs += 1
        expanded = _expand_path_token(token)
        if not expanded:
            raise SystemExit(f"--input path not found: {token}")

        for item in expanded:
            if not item.exists():
                raise SystemExit(f"--input path not found: {item}")

            if item.is_file():
                if not _supports_archive(item):
                    raise SystemExit(f"Unsupported bundle file type: {item}")
                if item not in seen:
                    seen.add(item)
                    bundles.append(item)
                continue

            if not item.is_dir():
                raise SystemExit(f"Unsupported --input path: {item}")

            if _looks_like_extracted_root(item):
                if item not in seen:
                    seen.add(item)
                    bundles.append(item)
                continue

            discovered: List[Path] = []
            for child in sorted(item.iterdir(), key=lambda p: str(p)):
                if child.is_file() and _supports_archive(child):
                    discovered.append(child.resolve())
                elif child.is_dir() and _looks_like_extracted_root(child):
                    discovered.append(child.resolve())
            if not discovered:
                raise SystemExit(
                    f"No bundles found under directory: {item} "
                    "(expected archives *.tar.gz/*.tgz/*.tar/*.zip or extracted bundle dirs)"
                )
            for found in discovered:
                if found not in seen:
                    seen.add(found)
                    bundles.append(found)

    bundles = sorted(bundles, key=lambda p: str(p))
    if not bundles:
        raise SystemExit("No bundles resolved from --input")
    return bundles, n_inputs


class _BundleContent:
    def list_files(self) -> List[str]:
        raise NotImplementedError

    def read_bytes(self, relpath: str) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        return


class _DirContent(_BundleContent):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._files = sorted(
            _safe_relpath(str(p.relative_to(self.root)).replace("\\", "/"))
            for p in self.root.rglob("*")
            if p.is_file()
        )

    def list_files(self) -> List[str]:
        return list(self._files)

    def read_bytes(self, relpath: str) -> bytes:
        norm = _safe_relpath(relpath)
        path = (self.root / norm).resolve()
        try:
            path.relative_to(self.root)
        except Exception as exc:
            raise ValueError(f"unsafe read path: {relpath}") from exc
        return path.read_bytes()


class _TarContent(_BundleContent):
    def __init__(self, archive: Path) -> None:
        self.archive = archive.resolve()
        self._tar = tarfile.open(self.archive, "r:*")
        members: Dict[str, tarfile.TarInfo] = {}
        for member in self._tar.getmembers():
            if not member.isfile():
                continue
            try:
                rel = _safe_relpath(str(member.name))
            except ValueError:
                continue
            members[rel] = member
        self._members = members
        self._files = sorted(self._members.keys())

    def list_files(self) -> List[str]:
        return list(self._files)

    def read_bytes(self, relpath: str) -> bytes:
        norm = _safe_relpath(relpath)
        member = self._members.get(norm)
        if member is None:
            raise KeyError(norm)
        fh = self._tar.extractfile(member)
        if fh is None:
            raise KeyError(norm)
        return fh.read()

    def close(self) -> None:
        self._tar.close()


class _ZipContent(_BundleContent):
    def __init__(self, archive: Path) -> None:
        self.archive = archive.resolve()
        self._zip = zipfile.ZipFile(self.archive, "r")
        members: Dict[str, str] = {}
        for name in self._zip.namelist():
            if name.endswith("/"):
                continue
            try:
                rel = _safe_relpath(name)
            except ValueError:
                continue
            members[rel] = name
        self._members = members
        self._files = sorted(self._members.keys())

    def list_files(self) -> List[str]:
        return list(self._files)

    def read_bytes(self, relpath: str) -> bytes:
        norm = _safe_relpath(relpath)
        member = self._members.get(norm)
        if member is None:
            raise KeyError(norm)
        return self._zip.read(member)

    def close(self) -> None:
        self._zip.close()


class _BundleReader:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        if self.path.is_dir():
            self.kind = "directory"
            self.content: _BundleContent = _DirContent(self.path)
        elif self.path.name.lower().endswith(".zip"):
            self.kind = "zip"
            self.content = _ZipContent(self.path)
        else:
            self.kind = "tar"
            self.content = _TarContent(self.path)

    def close(self) -> None:
        self.content.close()


def _resolve_relpath(available: Sequence[str], target: str) -> Optional[str]:
    norm = _safe_relpath(target)
    if norm in available:
        return norm
    suffix = sorted(p for p in available if p.endswith("/" + norm))
    if len(suffix) == 1:
        return suffix[0]
    return None


def _detect_certificate_path(available: Sequence[str]) -> Optional[str]:
    normalized = sorted(_safe_relpath(p) for p in available)
    for preferred in CERTIFICATE_PREFERRED_SUFFIXES:
        resolved = _resolve_relpath(normalized, preferred)
        if resolved is not None:
            return resolved

    fallback = sorted(
        p
        for p in normalized
        if PurePosixPath(p).name == "e2_certificate.json" and "/paper_assets" in ("/" + p)
    )
    if fallback:
        return fallback[0]

    fuzzy = sorted(
        p
        for p in normalized
        if PurePosixPath(p).suffix.lower() == ".json"
        and "certificate" in PurePosixPath(p).name.lower()
        and "/paper_assets" in ("/" + p)
    )
    return fuzzy[0] if fuzzy else None


def _detect_merge_report_path(available: Sequence[str]) -> Optional[str]:
    normalized = sorted(_safe_relpath(p) for p in available)
    return _resolve_relpath(normalized, MERGE_REPORT_SUFFIX)


def _coverage_from_certificate(cert: Mapping[str, Any]) -> Tuple[Optional[float], Optional[bool]]:
    coverage = cert.get("coverage")
    if not isinstance(coverage, Mapping):
        return None, None
    cov = {str(k): coverage[k] for k in coverage.keys()}
    frac = _finite_float(cov.get("fraction"))
    if frac is None:
        n_total = cov.get("n_plan_points")
        n_seen = cov.get("n_seen_plan_point_ids")
        if isinstance(n_total, int) and isinstance(n_seen, int) and n_total >= 0:
            frac = 1.0 if n_total == 0 else float(n_seen) / float(n_total)
    if frac is None:
        return None, None
    complete = bool(frac >= 1.0 - 1e-12)
    return float(frac), complete


def _extract_best_row(cert: Mapping[str, Any], *, select_mode: str) -> Tuple[Optional[float], Optional[bool], str, Optional[Mapping[str, Any]]]:
    best = _as_mapping(cert.get("best"))
    topk = _as_mapping(cert.get("top_k"))

    if select_mode == "best_eligible":
        row = _as_mapping(best.get("best_overall"))
        chi2 = _finite_float(row.get("chi2_total")) if row else None
        if chi2 is not None:
            plausible = bool(row.get("microphysics_plausible_ok", True))
            return chi2, plausible, "certificate.best.best_overall", row
        rows = [r for r in list(topk.get("overall") or []) if isinstance(r, Mapping)]
        for raw in rows:
            row2 = {str(k): raw[k] for k in raw.keys()}
            chi2_2 = _finite_float(row2.get("chi2_total"))
            if chi2_2 is None:
                continue
            plausible2 = bool(row2.get("microphysics_plausible_ok", True))
            return chi2_2, plausible2, "certificate.top_k.overall", row2
        return None, None, "missing_eligible_metrics", None

    # best_plausible
    row = _as_mapping(best.get("best_plausible"))
    chi2 = _finite_float(row.get("chi2_total")) if row else None
    if chi2 is not None:
        plausible = bool(row.get("microphysics_plausible_ok", True))
        return chi2, plausible, "certificate.best.best_plausible", row

    rows = [r for r in list(topk.get("overall") or []) if isinstance(r, Mapping)]
    for raw in rows:
        row2 = {str(k): raw[k] for k in raw.keys()}
        chi2_2 = _finite_float(row2.get("chi2_total"))
        if chi2_2 is None:
            continue
        plausible_raw = row2.get("microphysics_plausible_ok")
        plausible2 = True if plausible_raw is None else bool(plausible_raw)
        if plausible2:
            return chi2_2, plausible2, "certificate.top_k.overall(plausible_filter)", row2
    return None, None, "missing_plausible_metrics", None


def _extract_plan_source_sha(cert: Mapping[str, Any], merge_report: Optional[Mapping[str, Any]]) -> str:
    inputs = _as_mapping(cert.get("inputs"))
    plan = _as_mapping(inputs.get("plan"))
    val = str(plan.get("sha256", "")).strip()
    if val:
        return val
    if isinstance(merge_report, Mapping):
        val2 = str(merge_report.get("plan_source_sha256_chosen", "")).strip()
        if val2 and val2 != "unknown":
            return val2
    return "unknown"


def _extract_config_sha(cert: Mapping[str, Any], merge_report: Optional[Mapping[str, Any]]) -> str:
    if isinstance(merge_report, Mapping):
        val = str(merge_report.get("scan_config_sha256_chosen", "")).strip()
        if val and val != "unknown":
            return val
    options = _as_mapping(cert.get("options"))
    val2 = str(options.get("scan_config_sha256", "")).strip()
    return val2 if val2 else "unknown"


def _extract_metrics(path: Path, *, select_mode: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "path": str(path.resolve()),
        "bundle_name": path.name,
        "certificate_path": None,
        "certificate_ok": False,
        "parse_error": None,
        "selectable": False,
        "chi2_total": None,
        "plausible": None,
        "coverage_any": None,
        "coverage_complete": None,
        "config_sha": "unknown",
        "plan_source_sha": "unknown",
        "best_plan_point_id": None,
        "best_params_hash": None,
        "source_hint": None,
    }

    reader: Optional[_BundleReader] = None
    try:
        reader = _BundleReader(path)
        files = reader.content.list_files()

        cert_rel = _detect_certificate_path(files)
        row["certificate_path"] = cert_rel
        if cert_rel is None:
            row["parse_error"] = "certificate_missing"
            return row

        cert_raw = json.loads(reader.content.read_bytes(cert_rel).decode("utf-8"))
        if not isinstance(cert_raw, Mapping):
            row["parse_error"] = "certificate_not_object"
            return row
        cert = {str(k): cert_raw[k] for k in cert_raw.keys()}

        merge_report_rel = _detect_merge_report_path(files)
        merge_report: Optional[Dict[str, Any]] = None
        if merge_report_rel is not None:
            try:
                merge_raw = json.loads(reader.content.read_bytes(merge_report_rel).decode("utf-8"))
                if isinstance(merge_raw, Mapping):
                    merge_report = {str(k): merge_raw[k] for k in merge_raw.keys()}
            except Exception:
                merge_report = None

        chi2, plausible, source_hint, best_row = _extract_best_row(cert, select_mode=select_mode)
        coverage_any, coverage_complete = _coverage_from_certificate(cert)

        row["certificate_ok"] = True
        row["chi2_total"] = chi2
        row["plausible"] = plausible
        row["source_hint"] = source_hint
        row["coverage_any"] = coverage_any
        row["coverage_complete"] = coverage_complete
        row["config_sha"] = _extract_config_sha(cert, merge_report)
        row["plan_source_sha"] = _extract_plan_source_sha(cert, merge_report)

        if isinstance(best_row, Mapping):
            plan_point_id = str(best_row.get("plan_point_id", "")).strip()
            params_hash = str(best_row.get("params_hash", "")).strip()
            row["best_plan_point_id"] = plan_point_id or None
            row["best_params_hash"] = params_hash or None

        if select_mode in {"best_plausible", "best_eligible"}:
            row["selectable"] = chi2 is not None
        else:
            row["selectable"] = True

        return row
    except Exception as exc:
        row["parse_error"] = str(exc)
        return row
    finally:
        if reader is not None:
            reader.close()


def _sort_candidates(rows: Sequence[Mapping[str, Any]], *, select_mode: str) -> List[Dict[str, Any]]:
    if select_mode == "latest":
        ordered = sorted(rows, key=lambda r: (str(r.get("bundle_name", "")), str(r.get("path", ""))))
    else:
        ordered = sorted(
            rows,
            key=lambda r: (
                float(r.get("chi2_total")) if _finite_float(r.get("chi2_total")) is not None else float("inf"),
                str(r.get("bundle_name", "")),
                str(r.get("path", "")),
            ),
        )
    return [{str(k): item[k] for k in sorted(item.keys())} for item in ordered]


def _select_row(
    *,
    rows: Sequence[Mapping[str, Any]],
    select_mode: str,
    require_plan_coverage: str,
) -> Tuple[Optional[Mapping[str, Any]], str, int]:
    selectable = [row for row in rows if bool(row.get("selectable", False))]

    if require_plan_coverage == "complete":
        selectable = [row for row in selectable if bool(row.get("coverage_complete", False))]
        if not selectable:
            return None, "coverage_complete_required_but_not_satisfied", 2

    if not selectable:
        return None, "no_selectable_bundles", 2

    if select_mode == "latest":
        chosen = sorted(selectable, key=lambda r: (str(r.get("bundle_name", "")), str(r.get("path", ""))))[-1]
        return chosen, "latest_lexicographic_bundle_name", 0

    chosen = sorted(
        selectable,
        key=lambda r: (
            float(r.get("chi2_total")) if _finite_float(r.get("chi2_total")) is not None else float("inf"),
            str(r.get("bundle_name", "")),
            str(r.get("path", "")),
        ),
    )[0]

    if select_mode == "best_plausible":
        return chosen, "best_plausible_min_chi2_total", 0
    return chosen, "best_eligible_min_chi2_total", 0


def _to_output_payload(
    *,
    inputs_count: int,
    rows: Sequence[Mapping[str, Any]],
    selected: Optional[Mapping[str, Any]],
    select_reason: str,
    select_mode: str,
    require_plan_coverage: str,
) -> Dict[str, Any]:
    n_selectable = int(sum(1 for row in rows if bool(row.get("selectable", False))))
    selected_metrics: Optional[Dict[str, Any]] = None
    selected_path = None
    if isinstance(selected, Mapping):
        selected_path = str(selected.get("path", ""))
        selected_metrics = {
            "chi2_total": _finite_float(selected.get("chi2_total")),
            "plausible": (bool(selected.get("plausible")) if selected.get("plausible") is not None else None),
            "coverage_any": _finite_float(selected.get("coverage_any")),
            "coverage_complete": (bool(selected.get("coverage_complete")) if selected.get("coverage_complete") is not None else None),
            "config_sha": str(selected.get("config_sha", "unknown")),
            "plan_source_sha": str(selected.get("plan_source_sha", "unknown")),
            "best_plan_point_id": selected.get("best_plan_point_id"),
            "best_params_hash": selected.get("best_params_hash"),
            "source_hint": selected.get("source_hint"),
        }

    candidates_sorted = _sort_candidates(rows, select_mode=select_mode)
    candidates_top10 = candidates_sorted[:10]

    payload = {
        "schema": SCHEMA_ID,
        "select": str(select_mode),
        "require_plan_coverage": str(require_plan_coverage),
        "n_inputs": int(inputs_count),
        "n_bundles_found": int(len(rows)),
        "n_bundles_selectable": int(n_selectable),
        "selected_bundle_path": selected_path,
        "select_reason": str(select_reason),
        "selected_metrics": selected_metrics,
        "candidates": candidates_top10,
    }
    return payload


def _render_text(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"selected_bundle={str(payload.get('selected_bundle_path') or 'none')}")
    lines.append(
        "select={select} reason={reason} chi2={chi2} plausible={plaus} coverage={cov}".format(
            select=str(payload.get("select", "")),
            reason=str(payload.get("select_reason", "")),
            chi2=(
                f"{_finite_float(_as_mapping(payload.get('selected_metrics')).get('chi2_total')):.6g}"
                if _finite_float(_as_mapping(payload.get("selected_metrics")).get("chi2_total")) is not None
                else "unknown"
            ),
            plaus=(
                str(_as_mapping(payload.get("selected_metrics")).get("plausible")).lower()
                if _as_mapping(payload.get("selected_metrics")).get("plausible") is not None
                else "unknown"
            ),
            cov=(
                f"{_finite_float(_as_mapping(payload.get('selected_metrics')).get('coverage_any')):.6g}"
                if _finite_float(_as_mapping(payload.get("selected_metrics")).get("coverage_any")) is not None
                else "unknown"
            ),
        )
    )
    lines.append(f"n_inputs={int(payload.get('n_inputs', 0))}")
    lines.append(f"n_bundles_found={int(payload.get('n_bundles_found', 0))}")
    lines.append(f"n_bundles_selectable={int(payload.get('n_bundles_selectable', 0))}")
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic selector for Phase-2 E2 bundles.")
    parser.add_argument("--input", action="append", default=[], help="Input bundle path(s): file, directory, or glob")
    parser.add_argument("--select", choices=["best_plausible", "best_eligible", "latest"], default="best_plausible")
    parser.add_argument("--require-plan-coverage", choices=["none", "complete"], default="none")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--print-path", action="store_true", help="Print only selected bundle path")
    args = parser.parse_args(argv)

    if not args.input:
        print("At least one --input PATH is required", file=sys.stderr)
        return 1

    try:
        bundles, n_inputs = _discover_bundles([str(x) for x in list(args.input)])
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 1
        return 1 if code != 0 else 0
    except Exception as exc:
        print(f"ERROR: failed to resolve inputs: {exc}", file=sys.stderr)
        return 1

    rows = [_extract_metrics(path, select_mode=str(args.select)) for path in bundles]
    selected, reason, exit_code = _select_row(
        rows=rows,
        select_mode=str(args.select),
        require_plan_coverage=str(args.require_plan_coverage),
    )

    payload = _to_output_payload(
        inputs_count=n_inputs,
        rows=rows,
        selected=selected,
        select_reason=reason,
        select_mode=str(args.select),
        require_plan_coverage=str(args.require_plan_coverage),
    )

    if args.json_out is not None:
        _write_json(Path(args.json_out).expanduser().resolve(), payload)

    if int(exit_code) == 0 and bool(args.print_path):
        selected_path = str(payload.get("selected_bundle_path") or "")
        if not selected_path:
            return 2
        print(selected_path)
        return 0

    if bool(args.print_path):
        return int(exit_code)

    if str(args.format) == "json":
        print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    else:
        print(_render_text(payload), end="")

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
