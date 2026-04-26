#!/usr/bin/env python3
"""Convert DESI DR1 Gaussian BAO summary mean/cov files to internal VECTOR_over_rd format."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


SCHEMA = "phase4_desi_bao_convert_report_v1"
FETCH_SCHEMA = "phase4_desi_bao_fetch_manifest_v1"
FAIL_MARKER = "PHASE4_DESI_BAO_CONVERT_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z


class UsageError(Exception):
    """CLI usage/configuration error."""


class ConvertError(Exception):
    """Conversion failure."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _to_iso_utc(epoch_seconds: int) -> str:
    dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _split_tokens(line: str) -> List[str]:
    out: List[str] = []
    cur: List[str] = []
    for ch in line:
        if ch in (" ", "\t", ",", ";"):
            if cur:
                out.append("".join(cur))
                cur = []
            continue
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def _load_manifest(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    if not path.is_file():
        raise UsageError(f"manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise UsageError("manifest must be a JSON object")
    schema = payload.get("schema")
    if not isinstance(schema, str) or schema != FETCH_SCHEMA:
        raise UsageError(f"manifest schema must be {FETCH_SCHEMA!r}")
    return payload


def _resolve_from_manifest_filename(repo_root: Path, manifest_path: Path, name: Optional[str]) -> Optional[Path]:
    if name is None:
        return None
    filename = str(name).strip()
    if not filename:
        return None
    p = Path(filename)
    if p.is_absolute():
        return p if p.is_file() else None

    direct_repo = (repo_root / p).resolve()
    if direct_repo.is_file():
        return direct_repo

    direct_manifest = (manifest_path.parent / p).resolve()
    if direct_manifest.is_file():
        return direct_manifest

    fallback_manifest = (manifest_path.parent / Path(filename).name).resolve()
    if fallback_manifest.is_file():
        return fallback_manifest
    return None


def _load_mean_rows(path: Path) -> Tuple[List[str], List[float], List[float]]:
    if not path.is_file():
        raise UsageError(f"mean file not found: {path}")
    kinds: List[str] = []
    zs: List[float] = []
    ys: List[float] = []
    kind_map = {"DV_over_rs": "DV", "DM_over_rs": "DM", "DH_over_rs": "DH"}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            toks = _split_tokens(line)
            if len(toks) < 3:
                continue
            try:
                z = float(toks[0])
                y = float(toks[1])
            except ValueError as exc:
                raise ConvertError(f"invalid numeric row in mean file: {line!r}") from exc
            kind_raw = toks[2]
            if kind_raw not in kind_map:
                raise ConvertError(f"unsupported mean kind {kind_raw!r}; expected DV_over_rs/DM_over_rs/DH_over_rs")
            kinds.append(kind_map[kind_raw])
            zs.append(float(z))
            ys.append(float(y))
    if not ys:
        raise ConvertError("no rows parsed from mean file")
    return kinds, zs, ys


def _load_cov(path: Path) -> List[List[float]]:
    if not path.is_file():
        raise UsageError(f"cov file not found: {path}")
    rows: List[List[float]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            toks = _split_tokens(line)
            if not toks:
                continue
            try:
                row = [float(tok) for tok in toks]
            except ValueError as exc:
                raise ConvertError(f"non-numeric cov row: {line!r}") from exc
            rows.append(row)
    if not rows:
        raise ConvertError("empty covariance matrix")
    n = len(rows)
    if any(len(r) != n for r in rows):
        raise ConvertError("covariance matrix must be square")
    for i in range(n):
        if rows[i][i] <= 0.0 or not math.isfinite(rows[i][i]):
            raise ConvertError("covariance diagonal must be positive and finite")
    for i in range(n):
        for j in range(n):
            if abs(rows[i][j] - rows[j][i]) > 1e-12 * max(1.0, abs(rows[i][j]), abs(rows[j][i])):
                raise ConvertError("covariance matrix must be symmetric")
    return rows


def _relative_or_name(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return path.name


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Convert DESI Gaussian mean/cov to internal VECTOR_over_rd dataset.")
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--mean-txt", default=None)
    ap.add_argument("--cov-txt", default=None)
    ap.add_argument("--fetch-manifest", default=None)
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--created-utc", type=int, default=None)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        repo_root = Path(str(args.repo_root)).expanduser().resolve()
        if not repo_root.is_dir():
            raise UsageError(f"repo-root directory not found: {repo_root}")

        deterministic_mode = bool(int(args.deterministic))
        if args.created_utc is not None:
            created_epoch = int(args.created_utc)
        elif deterministic_mode:
            created_epoch = DEFAULT_CREATED_UTC_EPOCH
        else:
            created_epoch = int(time.time())
        created_utc = _to_iso_utc(created_epoch)

        manifest_path = None
        if args.fetch_manifest is not None:
            candidate = Path(str(args.fetch_manifest)).expanduser()
            manifest_path = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
        manifest = _load_manifest(manifest_path)

        mean_arg = str(args.mean_txt).strip() if args.mean_txt is not None else ""
        cov_arg = str(args.cov_txt).strip() if args.cov_txt is not None else ""

        mean_path: Optional[Path] = None
        cov_path: Optional[Path] = None
        if mean_arg:
            p = Path(mean_arg).expanduser()
            mean_path = p.resolve() if p.is_absolute() else (repo_root / p).resolve()
        if cov_arg:
            p = Path(cov_arg).expanduser()
            cov_path = p.resolve() if p.is_absolute() else (repo_root / p).resolve()

        if manifest is not None:
            files = manifest.get("files")
            if isinstance(files, Mapping):
                if mean_path is None:
                    mean_path = _resolve_from_manifest_filename(
                        repo_root,
                        manifest_path if manifest_path is not None else repo_root,
                        "desi_2024_gaussian_bao_ALL_GCcomb_mean.txt",
                    )
                if cov_path is None:
                    cov_path = _resolve_from_manifest_filename(
                        repo_root,
                        manifest_path if manifest_path is not None else repo_root,
                        "desi_2024_gaussian_bao_ALL_GCcomb_cov.txt",
                    )

        if mean_path is None or cov_path is None:
            raise UsageError("mean/cov inputs are required (set --mean-txt/--cov-txt or provide --fetch-manifest)")

        kinds, zs, ys = _load_mean_rows(mean_path)
        cov = _load_cov(cov_path)
        if len(ys) != len(cov):
            raise ConvertError(f"mean/cov dimension mismatch: n_mean={len(ys)} n_cov={len(cov)}")

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        values_csv = outdir / "values.csv"
        cov_txt = outdir / "cov.txt"
        dataset_csv = outdir / "dataset.csv"
        report_json = outdir / "CONVERSION_REPORT.json"

        with values_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(("kind", "z", "y"))
            for kind, z, y in zip(kinds, zs, ys):
                writer.writerow((kind, f"{z:.12e}", f"{y:.12e}"))

        with cov_txt.open("w", encoding="utf-8", newline="") as fh:
            for row in cov:
                fh.write(" ".join(f"{float(v):.12e}" for v in row) + "\n")

        with dataset_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(("type", "label", "survey", "values_path", "cov_path"))
            writer.writerow(("VECTOR_over_rd", "DESI DR1 Gaussian BAO ALL_GCcomb", "DESI_DR1_GAUSSIAN", "values.csv", "cov.txt"))

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "paths_redacted": True,
            "inputs": {
                "mean_relpath": _relative_or_name(mean_path, repo_root),
                "cov_relpath": _relative_or_name(cov_path, repo_root),
                "mean_sha256": _sha256_file(mean_path),
                "cov_sha256": _sha256_file(cov_path),
                "manifest_relpath": _relative_or_name(manifest_path, repo_root) if manifest_path is not None else None,
                "manifest_schema": manifest.get("schema") if isinstance(manifest, Mapping) else None,
            },
            "outputs": {
                "values_csv": {"filename": values_csv.name, "sha256": _sha256_file(values_csv)},
                "cov_txt": {"filename": cov_txt.name, "sha256": _sha256_file(cov_txt)},
                "dataset_csv": {"filename": dataset_csv.name, "sha256": _sha256_file(dataset_csv)},
            },
            "n_values": int(len(ys)),
        }
        report_json.write_text(_json_pretty(payload), encoding="utf-8")

        if str(args.format) == "json":
            print(_json_pretty(payload), end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"n_values={len(ys)}")
            print(f"values_sha256={payload['outputs']['values_csv']['sha256']}")
            print(f"cov_sha256={payload['outputs']['cov_txt']['sha256']}")
            print(f"dataset_sha256={payload['outputs']['dataset_csv']['sha256']}")
            print(f"report={report_json.name}")
        return 0

    except (UsageError, ConvertError) as exc:
        print(f"{FAIL_MARKER}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
