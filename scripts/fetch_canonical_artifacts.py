#!/usr/bin/env python3
"""Opt-in fetch helper for canonical artifacts (schema v2 SoT)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
from urllib.parse import urlparse

import verify_all_canonical_artifacts as verify_all


V101_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = V101_DIR / "canonical_artifacts.json"
_KEYS = ("late_time", "submission", "referee_pack", "toe_bundle")
_RETRY_HTTP_CODES = {408, 429, 500, 502, 503, 504}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def construct_download_url(release_url: str, tag: str, asset: str) -> str:
    parsed = urlparse(release_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"invalid release_url: {release_url!r}")
    # release_url expected: https://github.com/<org>/<repo>/releases/tag/<tag>
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 4 or parts[2] != "releases" or parts[3] != "tag":
        raise ValueError(f"release_url must point to /releases/tag/...: {release_url!r}")
    owner_repo = "/".join(parts[:2])
    return f"{parsed.scheme}://{parsed.netloc}/{owner_repo}/releases/download/{tag}/{asset}"


def _load_entries(catalog_path: Path) -> Dict[str, Dict[str, str]]:
    catalog = verify_all.load_catalog(catalog_path)
    artifacts = catalog.get("artifacts")
    if not isinstance(artifacts, dict):
        raise verify_all.CatalogError("catalog.artifacts must be an object")
    out: Dict[str, Dict[str, str]] = {}
    for k in _KEYS:
        v = artifacts.get(k)
        if not isinstance(v, dict):
            raise verify_all.CatalogError(f"missing artifacts.{k}")
        out[k] = {kk: str(v[kk]) for kk in ("tag", "asset", "sha256", "release_url")}
    return out


def _select_keys(only: str | None) -> List[str]:
    if not only:
        return list(_KEYS)
    toks = [t.strip() for t in only.split(",") if t.strip()]
    if not toks:
        raise ValueError("--only produced an empty selection")
    bad = [t for t in toks if t not in _KEYS]
    if bad:
        raise ValueError(f"unknown --only keys: {', '.join(sorted(set(bad)))}")
    return toks


def _download_to_temp(url: str, artifacts_dir: Path, timeout_sec: float, auth_token: str | None = None) -> Path:
    tmp = tempfile.NamedTemporaryFile(prefix="gsc_fetch_", suffix=".tmp", dir=artifacts_dir, delete=False)
    tmp_path = Path(tmp.name)
    headers = {"User-Agent": "GSC-fetch-canonical-artifacts/1.0"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with tmp, urllib.request.urlopen(request, timeout=timeout_sec) as r:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    return tmp_path


def _download_direct_with_retries(
    *,
    key: str,
    url: str,
    artifacts_dir: Path,
    timeout_sec: float,
    retries: int,
    retry_backoff_sec: float,
    auth_token: str | None,
) -> Path:
    attempts = max(1, retries + 1)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _download_to_temp(url, artifacts_dir, timeout_sec, auth_token=auth_token)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            code = int(getattr(exc, "code", 0))
            retryable = code in _RETRY_HTTP_CODES
            if attempt >= attempts or not retryable:
                break
            wait_s = retry_backoff_sec * attempt
            print(f"WARN: direct download failed for {key} with HTTP {code}; retrying in {wait_s:.1f}s ({attempt}/{attempts - 1})")
            time.sleep(wait_s)
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            wait_s = retry_backoff_sec * attempt
            print(f"WARN: direct download network error for {key}; retrying in {wait_s:.1f}s ({attempt}/{attempts - 1})")
            time.sleep(wait_s)
        except Exception as exc:
            last_exc = exc
            break
    assert last_exc is not None
    raise last_exc


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _report_missing(entries: Iterable[Tuple[str, Dict[str, str], Path]]) -> int:
    missing_list = list(entries)
    if not missing_list:
        return 0
    print("Missing canonical artifacts (no network performed):")
    for key, rec, resolved in missing_list:
        print(f"- {key}: {rec['asset']}")
        print(f"  expected_sha256: {rec['sha256']}")
        print(f"  tag: {rec['tag']}")
        print(f"  release: {rec['release_url']}")
        print(f"  looked_at: {resolved}")
        try:
            url = construct_download_url(rec["release_url"], rec["tag"], rec["asset"])
            print(f"  download_url: {url}")
        except Exception:
            pass
    print("To fetch missing assets:")
    print("  bash v11.0.0/scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing")
    return 2


def _owner_repo_from_release_url(release_url: str) -> str | None:
    parsed = urlparse(release_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return None


def _print_manual_download_help(*, key: str, rec: Dict[str, str], resolved: Path, url: str) -> None:
    owner_repo = _owner_repo_from_release_url(rec["release_url"]) or "OWNER/REPO"
    print(f"Manual fallback for {key}:")
    print(f"  release_url: {rec['release_url']}")
    print(f"  asset_filename: {rec['asset']}")
    print(f"  direct_download_url: {url}")
    print(f"  expected_sha256: {rec['sha256']}")
    print(f"  destination: {resolved}")
    print(f"  curl_download_cmd: curl -fL --retry 3 --retry-delay 2 -o {resolved} {url}")
    print(
        "  gh_download_cmd: gh release download "
        f"{rec['tag']} --repo {owner_repo} --pattern {rec['asset']} --dir {resolved.parent}"
    )
    print(f"  verify_cmd: shasum -a 256 {resolved}")


def _resolve_auth_token() -> str | None:
    env_token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if env_token:
        return env_token
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    token = (r.stdout or "").strip()
    return token or None


def _download_via_gh_release(*, key: str, rec: Dict[str, str], resolved: Path) -> Tuple[bool, str]:
    owner_repo = _owner_repo_from_release_url(rec["release_url"])
    if not owner_repo:
        return False, "unable to parse owner/repo from release URL"
    cmd = [
        "gh",
        "release",
        "download",
        rec["tag"],
        "--repo",
        owner_repo,
        "--pattern",
        rec["asset"],
        "--dir",
        str(resolved.parent),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        return False, "gh CLI not found in PATH"
    if r.returncode != 0:
        detail = ((r.stderr or "") + "\n" + (r.stdout or "")).strip()
        if "not logged" in detail.lower() or "authenticate" in detail.lower():
            return False, "gh CLI is not authenticated (run `gh auth login`)"
        return False, (detail.splitlines()[0] if detail else f"gh release download returned rc={r.returncode}")
    if not resolved.is_file():
        return False, "gh reported success but asset file was not downloaded"
    return True, ""


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="fetch_canonical_artifacts",
        description="Fetch missing canonical artifacts from GitHub releases (opt-in; SHA-verified).",
    )
    ap.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    ap.add_argument("--artifacts-dir", type=Path, default=Path.cwd())
    ap.add_argument("--only", default="", help="CSV subset of late_time,submission,referee_pack,toe_bundle")
    ap.add_argument("--fetch-missing", action="store_true", help="Actually download missing assets from release URLs")
    ap.add_argument("--dry-run", action="store_true", help="Report actions only; never perform network or writes")
    ap.add_argument("--timeout-sec", type=float, default=60.0)
    ap.add_argument("--retries", type=int, default=2, help="Retry count for direct download attempts")
    ap.add_argument("--retry-backoff-sec", type=float, default=1.0, help="Base backoff (seconds) between direct retries")
    args = ap.parse_args(argv)

    try:
        entries = _load_entries(args.catalog.expanduser().resolve())
        keys = _select_keys(args.only)
    except (verify_all.CatalogError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    artifacts_dir = args.artifacts_dir.expanduser().resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    auth_token: str | None = None

    missing: List[Tuple[str, Dict[str, str], Path]] = []
    for key in keys:
        rec = entries[key]
        resolved = verify_all._resolve_asset_path(artifacts_dir, rec["asset"])
        if resolved.is_file():
            got = sha256_file(resolved)
            if got.lower() != rec["sha256"].lower():
                print("ERROR: existing file sha256 mismatch")
                print(f"  id: {key}")
                print(f"  file: {resolved}")
                print(f"  expected_sha256: {rec['sha256']}")
                print(f"  got_sha256: {got}")
                return 2
            print(f"[ok] present+verified: {key} -> {resolved.name}")
            continue
        missing.append((key, rec, resolved))

    if not missing:
        print("OK: all selected canonical artifacts already present")
        return 0

    if not args.fetch_missing:
        if args.dry_run:
            for key, rec, resolved in missing:
                print(f"[dry-run] missing: {key} -> {resolved}")
            print("[dry-run] no fetch performed")
            return 0
        return _report_missing(missing)

    if args.dry_run:
        for key, rec, resolved in missing:
            url = construct_download_url(rec["release_url"], rec["tag"], rec["asset"])
            print(f"[dry-run] would fetch: {key}")
            print(f"  from: {url}")
            print(f"  to:   {resolved}")
            print(f"  sha:  {rec['sha256']}")
        return 0

    auth_token = _resolve_auth_token()

    for key, rec, resolved in missing:
        url = construct_download_url(rec["release_url"], rec["tag"], rec["asset"])
        _ensure_parent(resolved)
        print(f"[fetch] {key}: {url}")
        try:
            tmp_path = _download_direct_with_retries(
                key=key,
                url=url,
                artifacts_dir=artifacts_dir,
                timeout_sec=args.timeout_sec,
                retries=args.retries,
                retry_backoff_sec=args.retry_backoff_sec,
                auth_token=auth_token,
            )
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            print(f"ERROR: direct download failed for {key}: {exc.__class__.__name__}: {exc}")
            ok_gh, gh_reason = _download_via_gh_release(key=key, rec=rec, resolved=resolved)
            if ok_gh:
                got = sha256_file(resolved)
                if got.lower() != rec["sha256"].lower():
                    print(f"ERROR: sha256 mismatch after gh fallback for {key}")
                    print(f"  expected: {rec['sha256']}")
                    print(f"  got:      {got}")
                    _print_manual_download_help(key=key, rec=rec, resolved=resolved, url=url)
                    return 2
                print(f"[ok] fetched+verified (gh fallback): {key} -> {resolved}")
                continue

            if gh_reason:
                print(f"INFO: gh fallback unavailable for {key}: {gh_reason}")
            if auth_token is None:
                print("INFO: no GitHub auth token detected; private release assets may return 404/403.")
                print("      Try `gh auth login` or set GITHUB_TOKEN, then retry.")
            _print_manual_download_help(key=key, rec=rec, resolved=resolved, url=url)
            return 2
        except Exception as exc:
            print(f"ERROR: download failed for {key}: {exc}")
            _print_manual_download_help(key=key, rec=rec, resolved=resolved, url=url)
            return 2

        got = sha256_file(tmp_path)
        if got.lower() != rec["sha256"].lower():
            tmp_path.unlink(missing_ok=True)
            print(f"ERROR: sha256 mismatch after fetch for {key}")
            print(f"  expected: {rec['sha256']}")
            print(f"  got:      {got}")
            _print_manual_download_help(key=key, rec=rec, resolved=resolved, url=url)
            return 2

        # Atomic move in same filesystem.
        os.replace(tmp_path, resolved)
        print(f"[ok] fetched+verified: {key} -> {resolved}")

    print("OK: fetched all missing selected canonical artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
