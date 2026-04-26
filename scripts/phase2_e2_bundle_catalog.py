#!/usr/bin/env python3
"""Deterministic stdlib-only catalog/dashboard across many Phase-2 E2 bundles."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA_ID = "phase2_e2_bundle_catalog_v1"
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


def _sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _to_json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _norm_relpath(text: str) -> str:
    raw = str(text or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("empty relative path")
    p = PurePosixPath(raw)
    if p.is_absolute():
        raise ValueError(f"absolute path not allowed: {raw}")
    if ".." in p.parts:
        raise ValueError(f"path traversal not allowed: {raw}")
    norm = str(p)
    if norm in {"", "."}:
        raise ValueError(f"invalid relative path: {raw}")
    return norm


def _is_supported_archive(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tgz")


def _looks_like_extracted_bundle_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    for candidate in MANIFEST_CANDIDATES:
        if (path / candidate).is_file():
            return True
    # fallback: exactly one *manifest*.json at root
    matches = sorted(p for p in path.iterdir() if p.is_file() and "manifest" in p.name.lower() and p.suffix.lower() == ".json")
    return len(matches) == 1


def _expand_glob_if_any(token: str) -> List[Path]:
    if any(ch in token for ch in "*?["):
        base = Path(token)
        parent = Path(base.parent if str(base.parent) else ".")
        pattern = base.name
        if not parent.exists():
            return []
        return sorted(
            [p.resolve() for p in parent.iterdir() if fnmatch.fnmatch(p.name, pattern)],
            key=lambda p: str(p),
        )
    return [Path(token).expanduser().resolve()]


def _collect_bundles(raw_inputs: Sequence[str]) -> Tuple[List[Path], int]:
    items: List[Path] = []
    seen: set[Path] = set()
    n_tokens = 0
    for raw in raw_inputs:
        token = str(raw).strip()
        if not token:
            continue
        n_tokens += 1
        expanded = _expand_glob_if_any(token)
        if not expanded:
            raise SystemExit(f"--bundle path not found: {token}")
        for path in expanded:
            if not path.exists():
                raise SystemExit(f"--bundle path not found: {path}")
            if path.is_file():
                if not _is_supported_archive(path):
                    raise SystemExit(f"Unsupported bundle file type: {path}")
                if path not in seen:
                    seen.add(path)
                    items.append(path)
                continue

            if not path.is_dir():
                raise SystemExit(f"Unsupported --bundle input: {path}")

            if _looks_like_extracted_bundle_root(path):
                if path not in seen:
                    seen.add(path)
                    items.append(path)
                continue

            discovered: List[Path] = []
            for child in sorted(path.iterdir(), key=lambda p: str(p)):
                if child.is_file() and _is_supported_archive(child):
                    discovered.append(child.resolve())
                elif child.is_dir() and _looks_like_extracted_bundle_root(child):
                    discovered.append(child.resolve())
            if not discovered:
                raise SystemExit(
                    f"No supported bundles found under directory: {path} "
                    "(expected *.tar.gz/*.tgz/*.tar or extracted bundle dirs with manifest)"
                )
            for found in discovered:
                if found in seen:
                    continue
                seen.add(found)
                items.append(found)

    items = sorted(items, key=lambda p: str(p))
    if not items:
        raise SystemExit("No bundle inputs resolved")
    return items, n_tokens


class BundleSource:
    def list_files(self) -> List[str]:
        raise NotImplementedError

    def read_bytes(self, relpath: str) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        return


class DirSource(BundleSource):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._files: List[str] = sorted(
            _norm_relpath(str(p.relative_to(self.root)).replace("\\", "/"))
            for p in self.root.rglob("*")
            if p.is_file()
        )

    def list_files(self) -> List[str]:
        return list(self._files)

    def read_bytes(self, relpath: str) -> bytes:
        norm = _norm_relpath(relpath)
        path = (self.root / norm).resolve()
        try:
            path.relative_to(self.root)
        except Exception as exc:
            raise ValueError(f"unsafe relative path outside bundle root: {relpath}") from exc
        return path.read_bytes()


class TarSource(BundleSource):
    def __init__(self, archive_path: Path) -> None:
        self.archive_path = archive_path.resolve()
        self._tar = tarfile.open(self.archive_path, "r:*")
        self._members: Dict[str, tarfile.TarInfo] = {}
        for member in self._tar.getmembers():
            if not member.isfile():
                continue
            try:
                rel = _norm_relpath(str(member.name))
            except ValueError:
                continue
            self._members[rel] = member
        self._files = sorted(self._members.keys())

    def list_files(self) -> List[str]:
        return list(self._files)

    def read_bytes(self, relpath: str) -> bytes:
        norm = _norm_relpath(relpath)
        member = self._members.get(norm)
        if member is None:
            raise KeyError(norm)
        fh = self._tar.extractfile(member)
        if fh is None:
            raise KeyError(norm)
        return fh.read()

    def close(self) -> None:
        self._tar.close()


class BundleReader:
    def __init__(self, bundle_path: Path) -> None:
        self.path = bundle_path.resolve()
        if self.path.is_dir():
            self.kind = "directory"
            self.source: BundleSource = DirSource(self.path)
            self.size_bytes = int(sum((self.path / p).stat().st_size for p in self.source.list_files()))
            self.bundle_sha256 = self._dir_digest()
        else:
            self.kind = "archive"
            self.source = TarSource(self.path)
            self.size_bytes = int(self.path.stat().st_size)
            self.bundle_sha256 = _sha256_file(self.path)

    def close(self) -> None:
        self.source.close()

    def _dir_digest(self) -> str:
        rows: List[str] = []
        for rel in self.source.list_files():
            data = self.source.read_bytes(rel)
            rows.append(f"{rel}\t{len(data)}\t{_sha256_bytes(data)}")
        payload = "\n".join(rows).encode("utf-8")
        return _sha256_bytes(payload)


def _resolve_relpath(relpaths: Sequence[str], target: str) -> Optional[str]:
    norm = _norm_relpath(target)
    if norm in relpaths:
        return norm
    suffix_matches = sorted(p for p in relpaths if p.endswith("/" + norm))
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    return None


def _detect_manifest_relpath(relpaths: Sequence[str]) -> Optional[str]:
    normalized = sorted(_norm_relpath(p) for p in relpaths)

    for candidate in MANIFEST_CANDIDATES:
        resolved = _resolve_relpath(normalized, candidate)
        if resolved is not None:
            return resolved

    wildcard = sorted(
        p for p in normalized if PurePosixPath(p).suffix.lower() == ".json" and "manifest" in PurePosixPath(p).name.lower()
    )
    if len(wildcard) == 1:
        return wildcard[0]
    return None


def _detect_certificate_relpath(relpaths: Sequence[str]) -> Optional[str]:
    normalized = sorted(_norm_relpath(p) for p in relpaths)
    for suffix in CERTIFICATE_PREFERRED_SUFFIXES:
        resolved = _resolve_relpath(normalized, suffix)
        if resolved is not None:
            return resolved

    candidates = sorted(
        p
        for p in normalized
        if "/paper_assets" in ("/" + p)
        and PurePosixPath(p).suffix.lower() == ".json"
        and "certificate" in PurePosixPath(p).name.lower()
    )
    if candidates:
        return candidates[0]
    return None


def _detect_merge_report_relpath(relpaths: Sequence[str]) -> Optional[str]:
    normalized = sorted(_norm_relpath(p) for p in relpaths)
    return _resolve_relpath(normalized, MERGE_REPORT_SUFFIX)


def _is_hex_sha256(value: str) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _manifest_entries(manifest: Mapping[str, Any]) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []

    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, Mapping):
                continue
            raw_path = item.get("path")
            raw_sha = item.get("sha256")
            if raw_path is None or raw_sha is None:
                continue
            rel = _norm_relpath(str(raw_path))
            sha = str(raw_sha).strip().lower()
            if not _is_hex_sha256(sha):
                raise ValueError(f"invalid sha256 in manifest for {rel}")
            rows.append((rel, sha))
        if rows:
            return sorted(rows, key=lambda t: t[0])

    files = manifest.get("files")
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, Mapping):
                continue
            raw_path = item.get("path", item.get("relpath"))
            raw_sha = item.get("sha256", item.get("sha"))
            if raw_path is None or raw_sha is None:
                continue
            rel = _norm_relpath(str(raw_path))
            sha = str(raw_sha).strip().lower()
            if not _is_hex_sha256(sha):
                raise ValueError(f"invalid sha256 in manifest for {rel}")
            rows.append((rel, sha))
        if rows:
            return sorted(rows, key=lambda t: t[0])

    mappings = [manifest.get("artifacts_sha256"), manifest.get("files_sha256")]
    for mapping in mappings:
        if not isinstance(mapping, Mapping):
            continue
        local: List[Tuple[str, str]] = []
        for key in sorted(str(k) for k in mapping.keys()):
            rel = _norm_relpath(key)
            sha = str(mapping.get(key)).strip().lower()
            if not _is_hex_sha256(sha):
                raise ValueError(f"invalid sha256 in manifest for {rel}")
            local.append((rel, sha))
        if local:
            return local

    raise ValueError("manifest does not contain supported file/hash entries")


def _extract_plan_source_from_certificate(cert: Mapping[str, Any]) -> Optional[str]:
    inputs = _as_mapping(cert.get("inputs"))
    plan = _as_mapping(inputs.get("plan"))
    sha = str(plan.get("sha256", "")).strip()
    return sha if sha else None


def _extract_git_sha(manifest: Mapping[str, Any], cert: Optional[Mapping[str, Any]]) -> Optional[str]:
    if cert is not None:
        tool = _as_mapping(cert.get("tool"))
        raw = str(tool.get("repo_git_sha", "")).strip()
        if raw:
            return raw
    git = _as_mapping(manifest.get("git"))
    sha = str(git.get("sha", "")).strip()
    return sha if sha else None


def _status_counts_from_certificate(cert: Mapping[str, Any]) -> Dict[str, int]:
    counts = _as_mapping(_as_mapping(cert.get("counts")).get("status_counts"))
    out: Dict[str, int] = {}
    for key in sorted(str(k) for k in counts.keys()):
        try:
            out[str(key)] = int(counts.get(key))
        except Exception:
            continue
    return out


def _classify_status_counts(status_counts: Mapping[str, int]) -> Tuple[int, int, int, int]:
    ok = 0
    err = 0
    skipped = 0
    unknown = 0
    for status, raw_count in sorted(((str(k), int(v)) for k, v in status_counts.items()), key=lambda kv: str(kv[0])):
        count = int(raw_count)
        if status == "ok":
            ok += count
        elif status == "error":
            err += count
        elif status.startswith("skipped"):
            skipped += count
        else:
            unknown += count
    return ok, err, skipped, unknown


def _best_from_certificate(cert: Mapping[str, Any], *, eligible_status: str) -> Mapping[str, Any]:
    best = _as_mapping(cert.get("best"))
    if eligible_status == "ok_only":
        row = _as_mapping(best.get("best_overall"))
        if row:
            return row
        return _as_mapping(best.get("best_cmb_ok"))

    # any_eligible
    for key in ("best_overall", "best_cmb_ok", "best_drift_ok", "best_joint_ok", "best_plausible"):
        row = _as_mapping(best.get(key))
        if row:
            return row
    return {}


def _best_plausible_from_certificate(cert: Mapping[str, Any]) -> Mapping[str, Any]:
    best = _as_mapping(cert.get("best"))
    return _as_mapping(best.get("best_plausible"))


def _safe_rel_for_display(relpath: Optional[str]) -> str:
    if not relpath:
        return "missing"
    return str(relpath)


def _parse_bundle(bundle_path: Path, *, eligible_status: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "path": str(bundle_path.resolve()),
        "kind": "unknown",
        "bundle_sha256": "unknown",
        "size_bytes": 0,
        "manifest_relpath": None,
        "certificate_relpath": None,
        "merge_report_relpath": None,
        "manifest_schema": None,
        "verify_ok": False,
        "verify_errors": [],
        "missing_manifest": False,
        "missing_certificate": False,
        "parse_error": None,
        "config_sha": "unknown",
        "plan_source_sha": "unknown",
        "git_sha": "unknown",
        "coverage_any": None,
        "coverage_eligible": None,
        "plan_points_total": None,
        "plan_points_seen_any": None,
        "plan_points_seen_eligible": None,
        "n_records": None,
        "status_ok": 0,
        "status_error": 0,
        "status_skipped": 0,
        "status_unknown": 0,
        "best_chi2_total": None,
        "best_plan_point_id": None,
        "best_params_hash": None,
        "fraction_plausible": None,
        "best_plausible_chi2_total": None,
    }

    reader: Optional[BundleReader] = None
    try:
        reader = BundleReader(bundle_path)
        row["kind"] = str(reader.kind)
        row["bundle_sha256"] = str(reader.bundle_sha256)
        row["size_bytes"] = int(reader.size_bytes)

        relpaths = reader.source.list_files()
        manifest_rel = _detect_manifest_relpath(relpaths)
        row["manifest_relpath"] = manifest_rel
        if manifest_rel is None:
            row["missing_manifest"] = True
            row["parse_error"] = "manifest missing"
            return row

        manifest_bytes = reader.source.read_bytes(manifest_rel)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(manifest, Mapping):
            raise ValueError("manifest is not a JSON object")
        manifest_obj = {str(k): manifest[k] for k in manifest.keys()}
        row["manifest_schema"] = str(manifest_obj.get("schema", "")) or None

        verify_errors: List[str] = []
        entries = _manifest_entries(manifest_obj)
        for rel, expected_sha in entries:
            resolved = _resolve_relpath(relpaths, rel)
            if resolved is None:
                verify_errors.append(f"missing:{rel}")
                continue
            actual_sha = _sha256_bytes(reader.source.read_bytes(resolved))
            if actual_sha != expected_sha:
                verify_errors.append(f"sha_mismatch:{rel}")

        row["verify_ok"] = (len(verify_errors) == 0)
        row["verify_errors"] = sorted(verify_errors)

        merge_rel = _detect_merge_report_relpath(relpaths)
        row["merge_report_relpath"] = merge_rel
        if merge_rel is not None:
            try:
                merge_payload = json.loads(reader.source.read_bytes(merge_rel).decode("utf-8"))
                if isinstance(merge_payload, Mapping):
                    merge_obj = {str(k): merge_payload[k] for k in merge_payload.keys()}
                    cfg = str(merge_obj.get("scan_config_sha256_chosen", "")).strip()
                    if cfg and cfg != "unknown":
                        row["config_sha"] = cfg
                    ps = str(merge_obj.get("plan_source_sha256_chosen", "")).strip()
                    if ps and ps != "unknown":
                        row["plan_source_sha"] = ps
            except Exception:
                pass

        cert_rel = _detect_certificate_relpath(relpaths)
        row["certificate_relpath"] = cert_rel
        if cert_rel is None:
            row["missing_certificate"] = True
            return row

        cert_payload = json.loads(reader.source.read_bytes(cert_rel).decode("utf-8"))
        if not isinstance(cert_payload, Mapping):
            raise ValueError("certificate payload is not a JSON object")
        cert = {str(k): cert_payload[k] for k in cert_payload.keys()}

        counts = _as_mapping(cert.get("counts"))
        status_counts = _status_counts_from_certificate(cert)
        status_ok, status_error, status_skipped, status_unknown = _classify_status_counts(status_counts)
        n_records = counts.get("n_total_records")
        n_records_i = int(n_records) if isinstance(n_records, int) else None

        row["n_records"] = n_records_i
        row["status_ok"] = int(status_ok)
        row["status_error"] = int(status_error)
        row["status_skipped"] = int(status_skipped)
        row["status_unknown"] = int(status_unknown)

        coverage = cert.get("coverage")
        if isinstance(coverage, Mapping):
            cov = {str(k): coverage[k] for k in coverage.keys()}
            row["plan_points_total"] = int(cov.get("n_plan_points", 0))
            row["plan_points_seen_any"] = int(cov.get("n_seen_plan_point_ids", 0))
            row["plan_points_seen_eligible"] = (
                int(cov.get("n_seen_plan_point_ids_eligible", 0))
                if "n_seen_plan_point_ids_eligible" in cov
                else None
            )
            frac = _finite_float(cov.get("fraction"))
            if frac is None and row["plan_points_total"] and row["plan_points_seen_any"] is not None:
                frac = float(row["plan_points_seen_any"]) / float(row["plan_points_total"])
            row["coverage_any"] = frac
            row["coverage_eligible"] = _finite_float(cov.get("coverage_eligible"))

        best_overall = _best_from_certificate(cert, eligible_status=eligible_status)
        row["best_chi2_total"] = _finite_float(best_overall.get("chi2_total")) if best_overall else None
        if best_overall:
            plan_id = str(best_overall.get("plan_point_id", "")).strip()
            params_hash = str(best_overall.get("params_hash", "")).strip()
            row["best_plan_point_id"] = plan_id or None
            row["best_params_hash"] = params_hash or None

        best_pl = _best_plausible_from_certificate(cert)
        row["best_plausible_chi2_total"] = _finite_float(best_pl.get("chi2_total")) if best_pl else None

        n_plausible = _finite_float(counts.get("n_plausible"))
        n_eligible = _finite_float(counts.get("n_eligible"))
        if n_plausible is not None:
            denom = n_eligible
            if denom is None or denom <= 0:
                denom = _finite_float(counts.get("n_total_records"))
            if denom is not None and denom > 0:
                row["fraction_plausible"] = float(n_plausible) / float(denom)

        plan_source_from_cert = _extract_plan_source_from_certificate(cert)
        if plan_source_from_cert:
            row["plan_source_sha"] = str(plan_source_from_cert)

        git_sha = _extract_git_sha(manifest_obj, cert)
        if git_sha:
            row["git_sha"] = str(git_sha)

        return row
    except Exception as exc:
        row["parse_error"] = str(exc)
        return row
    finally:
        if reader is not None:
            reader.close()


def _sort_bundle_rows(rows: Sequence[Mapping[str, Any]], *, sort_by: str) -> List[Dict[str, Any]]:
    def key_best(row: Mapping[str, Any]) -> Tuple[float, str]:
        chi2 = _finite_float(row.get("best_chi2_total"))
        return (float("inf") if chi2 is None else float(chi2), str(row.get("path", "")))

    def key_cov_eligible(row: Mapping[str, Any]) -> Tuple[float, str]:
        cov = _finite_float(row.get("coverage_eligible"))
        return (-(float(cov) if cov is not None else -1.0), str(row.get("path", "")))

    def key_cov_any(row: Mapping[str, Any]) -> Tuple[float, str]:
        cov = _finite_float(row.get("coverage_any"))
        return (-(float(cov) if cov is not None else -1.0), str(row.get("path", "")))

    def key_records(row: Mapping[str, Any]) -> Tuple[int, str]:
        count = row.get("n_records")
        n = int(count) if isinstance(count, int) else -1
        return (-n, str(row.get("path", "")))

    def key_path(row: Mapping[str, Any]) -> Tuple[str]:
        return (str(row.get("path", "")),)

    mapping = {
        "best_chi2_total": key_best,
        "coverage_eligible": key_cov_eligible,
        "coverage_any": key_cov_any,
        "n_records": key_records,
        "path": key_path,
    }
    key_fn = mapping.get(sort_by, key_best)
    sorted_rows = sorted(rows, key=key_fn)
    return [{str(k): row[k] for k in sorted(row.keys())} for row in sorted_rows]


def _compatibility_values(rows: Sequence[Mapping[str, Any]], field: str) -> List[str]:
    values: set[str] = set()
    for row in rows:
        raw = str(row.get(field, "")).strip()
        values.add(raw if raw and raw != "unknown" else "unknown")
    return sorted(values)


def _status_totals(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    totals = {
        "total_records": 0,
        "total_ok": 0,
        "total_error": 0,
        "total_skipped": 0,
        "total_unknown": 0,
    }
    for row in rows:
        n_records = row.get("n_records")
        if isinstance(n_records, int):
            totals["total_records"] += int(n_records)
        for key, field in (
            ("total_ok", "status_ok"),
            ("total_error", "status_error"),
            ("total_skipped", "status_skipped"),
            ("total_unknown", "status_unknown"),
        ):
            val = row.get(field)
            if isinstance(val, int):
                totals[key] += int(val)
    return totals


def _pick_best_overall(rows: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    best: Optional[Tuple[float, str, Mapping[str, Any]]] = None
    for row in rows:
        chi2 = _finite_float(row.get("best_chi2_total"))
        if chi2 is None:
            continue
        key = (float(chi2), str(row.get("best_params_hash") or ""), row)
        if best is None or key[:2] < best[:2]:
            best = key
    if best is None:
        return None
    row = best[2]
    return {
        "bundle_sha256": str(row.get("bundle_sha256", "unknown")),
        "bundle_path": str(row.get("path", "")),
        "chi2_total": float(best[0]),
        "plan_point_id": row.get("best_plan_point_id"),
        "params_hash": row.get("best_params_hash"),
    }


def _evaluate_exit_code(
    *,
    rows: Sequence[Mapping[str, Any]],
    require_coverage: str,
    require_same: str,
    compatibility: Mapping[str, Any],
    parsed_count: int,
) -> Tuple[int, List[str]]:
    violations: List[str] = []

    if parsed_count <= 0:
        return 1, ["no bundles parsed successfully"]

    if require_coverage in {"any", "complete"}:
        for row in rows:
            cov = _finite_float(row.get("coverage_any"))
            if cov is None:
                violations.append(
                    f"coverage unknown for bundle: {row.get('path', '')}"
                )
                continue
            if require_coverage == "any" and cov <= 0.0:
                violations.append(
                    f"coverage_any==0 for bundle: {row.get('path', '')}"
                )
            if require_coverage == "complete" and cov < 1.0 - 1e-12:
                violations.append(
                    f"coverage_any<1 for bundle: {row.get('path', '')} ({cov:.6g})"
                )

    if require_same == "config_sha":
        values = list(compatibility.get("unique_config_sha") or [])
        if len(values) > 1:
            violations.append("require-same config_sha violated: " + ",".join(str(v) for v in values))
    elif require_same == "plan_source_sha":
        values = list(compatibility.get("unique_plan_source_sha") or [])
        if len(values) > 1:
            violations.append("require-same plan_source_sha violated: " + ",".join(str(v) for v in values))

    if violations:
        return 2, violations
    return 0, []


def _fmt_float(value: Any) -> str:
    parsed = _finite_float(value)
    if parsed is None:
        return "unknown"
    return f"{parsed:.6g}"


def _render_text(payload: Mapping[str, Any], *, mode: str, exit_code: int) -> str:
    lines: List[str] = []

    inputs = _as_mapping(payload.get("inputs"))
    lines.append("# Inputs")
    for key in (
        "n_bundles_input",
        "n_bundles_found",
        "n_bundles_parsed",
        "n_bundles_missing_manifest",
        "n_bundles_missing_certificate",
        "n_bundles_parse_error",
    ):
        lines.append(f"{key}={int(inputs.get(key, 0))}")
    lines.append("")

    compat = _as_mapping(payload.get("compatibility"))
    lines.append("# Compatibility")
    lines.append("unique_config_sha=" + json.dumps(list(compat.get("unique_config_sha") or []), ensure_ascii=True))
    lines.append("unique_plan_source_sha=" + json.dumps(list(compat.get("unique_plan_source_sha") or []), ensure_ascii=True))
    lines.append("unique_git_sha=" + json.dumps(list(compat.get("unique_git_sha") or []), ensure_ascii=True))
    lines.append("")

    lines.append("# Bundles")
    bundles = list(payload.get("bundles") or [])
    if not bundles:
        lines.append("none")
    elif mode == "by_bundle":
        for idx, row_any in enumerate(bundles, start=1):
            row = _as_mapping(row_any)
            lines.append(f"bundle_idx={idx}")
            lines.append(f"path={row.get('path','')}")
            lines.append(f"bundle_sha256={row.get('bundle_sha256','unknown')}")
            lines.append(f"size_bytes={int(row.get('size_bytes', 0))}")
            lines.append(f"verify_ok={1 if bool(row.get('verify_ok', False)) else 0}")
            lines.append(f"manifest_relpath={_safe_rel_for_display(row.get('manifest_relpath'))}")
            lines.append(f"certificate_relpath={_safe_rel_for_display(row.get('certificate_relpath'))}")
            lines.append(f"config_sha={str(row.get('config_sha', 'unknown'))}")
            lines.append(f"plan_source_sha={str(row.get('plan_source_sha', 'unknown'))}")
            lines.append(
                "coverage_any={cov_any} coverage_eligible={cov_elig} plan_points_total={ppt}".format(
                    cov_any=_fmt_float(row.get("coverage_any")),
                    cov_elig=_fmt_float(row.get("coverage_eligible")),
                    ppt=(
                        int(row.get("plan_points_total"))
                        if isinstance(row.get("plan_points_total"), int)
                        else "unknown"
                    ),
                )
            )
            lines.append(
                "n_records={n} status_ok={ok} status_error={err} status_skipped={skip} status_unknown={unk}".format(
                    n=(int(row.get("n_records")) if isinstance(row.get("n_records"), int) else "unknown"),
                    ok=int(row.get("status_ok", 0)),
                    err=int(row.get("status_error", 0)),
                    skip=int(row.get("status_skipped", 0)),
                    unk=int(row.get("status_unknown", 0)),
                )
            )
            lines.append(
                "best_chi2_total={chi2} best_plan_point_id={ppid} best_params_hash={ph}".format(
                    chi2=_fmt_float(row.get("best_chi2_total")),
                    ppid=str(row.get("best_plan_point_id") or "unknown"),
                    ph=str(row.get("best_params_hash") or "unknown"),
                )
            )
            lines.append(
                "fraction_plausible={fp} best_plausible_chi2_total={bp}".format(
                    fp=_fmt_float(row.get("fraction_plausible")),
                    bp=_fmt_float(row.get("best_plausible_chi2_total")),
                )
            )
            if row.get("parse_error"):
                lines.append(f"parse_error={row.get('parse_error')}")
            lines.append("")
    else:
        for idx, row_any in enumerate(bundles, start=1):
            row = _as_mapping(row_any)
            lines.append(
                "idx={idx} path={path} bundle_sha256={sha} size_bytes={size} verify_ok={ok} "+
                "config_sha={cfg} plan_source_sha={plan} coverage_any={cov} n_records={n} best_chi2_total={chi2}".format(
                    idx=idx,
                    path=str(row.get("path", "")),
                    sha=str(row.get("bundle_sha256", "unknown")),
                    size=int(row.get("size_bytes", 0)),
                    ok=1 if bool(row.get("verify_ok", False)) else 0,
                    cfg=str(row.get("config_sha", "unknown")),
                    plan=str(row.get("plan_source_sha", "unknown")),
                    cov=_fmt_float(row.get("coverage_any")),
                    n=(int(row.get("n_records")) if isinstance(row.get("n_records"), int) else "unknown"),
                    chi2=_fmt_float(row.get("best_chi2_total")),
                )
            )
    lines.append("")

    lines.append("# Best overall (eligible)")
    best = payload.get("best_overall")
    if isinstance(best, Mapping):
        lines.append(f"best_overall_bundle_sha256={best.get('bundle_sha256', 'unknown')}")
        lines.append(f"best_overall_chi2_total={_fmt_float(best.get('chi2_total'))}")
        lines.append(f"best_overall_plan_point_id={best.get('plan_point_id') or 'unknown'}")
        lines.append(f"best_overall_params_hash={best.get('params_hash') or 'unknown'}")
    else:
        lines.append("best_overall=unknown")
    lines.append("")

    totals = _as_mapping(payload.get("totals"))
    lines.append("# Totals")
    for key in (
        "total_records",
        "total_ok",
        "total_error",
        "total_skipped",
        "total_unknown",
        "bundles_with_complete_coverage",
        "bundles_with_any_errors",
    ):
        lines.append(f"{key}={int(totals.get(key, 0))}")
    lines.append("")

    lines.append("# Exit code policy")
    policy = _as_mapping(payload.get("exit_code_policy"))
    lines.append(f"computed_exit_code={int(exit_code)}")
    lines.append(
        "require_coverage={rc} require_same={rs} violations={n}".format(
            rc=str(policy.get("require_coverage", "none")),
            rs=str(policy.get("require_same", "none")),
            n=len(list(policy.get("violations") or [])),
        )
    )
    for item in list(policy.get("violations") or []):
        lines.append(f"violation={str(item)}")

    return "\n".join(lines).rstrip() + "\n"


def build_catalog(
    *,
    bundles: Sequence[Path],
    sort_by: str,
    eligible_status: str,
    require_coverage: str,
    require_same: str,
) -> Tuple[Dict[str, Any], int]:
    parsed_rows: List[Dict[str, Any]] = []
    missing_manifest = 0
    missing_certificate = 0
    parse_error_count = 0

    for path in bundles:
        row = _parse_bundle(path, eligible_status=eligible_status)
        parsed_rows.append(row)
        if bool(row.get("missing_manifest", False)):
            missing_manifest += 1
        if bool(row.get("missing_certificate", False)):
            missing_certificate += 1
        if row.get("parse_error"):
            parse_error_count += 1

    sorted_rows = _sort_bundle_rows(parsed_rows, sort_by=sort_by)

    compatibility = {
        "unique_config_sha": _compatibility_values(sorted_rows, "config_sha"),
        "unique_plan_source_sha": _compatibility_values(sorted_rows, "plan_source_sha"),
        "unique_git_sha": _compatibility_values(sorted_rows, "git_sha"),
    }

    totals = _status_totals(sorted_rows)
    totals["bundles_with_complete_coverage"] = int(
        sum(1 for row in sorted_rows if _finite_float(row.get("coverage_any")) is not None and _finite_float(row.get("coverage_any")) >= 1.0 - 1e-12)
    )
    totals["bundles_with_any_errors"] = int(
        sum(1 for row in sorted_rows if int(row.get("status_error", 0)) > 0)
    )

    best_overall = _pick_best_overall(sorted_rows)

    inputs_payload = {
        "n_bundles_input": int(len(bundles)),
        "n_bundles_found": int(len(bundles)),
        "n_bundles_parsed": int(sum(1 for row in sorted_rows if not row.get("parse_error"))),
        "n_bundles_missing_manifest": int(missing_manifest),
        "n_bundles_missing_certificate": int(missing_certificate),
        "n_bundles_parse_error": int(parse_error_count),
    }

    exit_code, violations = _evaluate_exit_code(
        rows=sorted_rows,
        require_coverage=require_coverage,
        require_same=require_same,
        compatibility=compatibility,
        parsed_count=int(inputs_payload["n_bundles_parsed"]),
    )

    payload: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "inputs": inputs_payload,
        "compatibility": compatibility,
        "bundles": sorted_rows,
        "best_overall": best_overall,
        "totals": totals,
        "exit_code_policy": {
            "require_coverage": str(require_coverage),
            "require_same": str(require_same),
            "violations": [str(v) for v in violations],
        },
    }
    return payload, int(exit_code)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Catalog/dashboard for multiple Phase-2 E2 bundles (stdlib-only, deterministic)."
    )
    parser.add_argument(
        "--bundle",
        action="append",
        default=[],
        metavar="PATH",
        help="Bundle input path (repeatable): archive file, directory of bundles, or extracted bundle root.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON output file path")
    parser.add_argument("--mode", choices=["summary", "by_bundle"], default="summary")
    parser.add_argument(
        "--sort-by",
        choices=["best_chi2_total", "coverage_eligible", "coverage_any", "n_records", "path"],
        default="best_chi2_total",
    )
    parser.add_argument("--eligible-status", choices=["ok_only", "any_eligible"], default="ok_only")
    parser.add_argument("--require-coverage", choices=["none", "any", "complete"], default="none")
    parser.add_argument("--require-same", choices=["none", "config_sha", "plan_source_sha"], default="none")

    args = parser.parse_args(argv)

    if not args.bundle:
        raise SystemExit("At least one --bundle PATH is required")

    bundle_paths, _ = _collect_bundles([str(x) for x in list(args.bundle)])
    payload, exit_code = build_catalog(
        bundles=bundle_paths,
        sort_by=str(args.sort_by),
        eligible_status=str(args.eligible_status),
        require_coverage=str(args.require_coverage),
        require_same=str(args.require_same),
    )

    if args.json_out is not None:
        _write_json(Path(args.json_out).expanduser().resolve(), payload)

    if str(args.format) == "json":
        print(_to_json_text(payload))
    else:
        print(_render_text(payload, mode=str(args.mode), exit_code=int(exit_code)), end="")

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
