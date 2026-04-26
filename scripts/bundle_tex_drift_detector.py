#!/usr/bin/env python3
"""Warn-only detector for drift between canonical submission TeX and repo TeX."""

from __future__ import annotations

import hashlib
import shlex
import zipfile
from pathlib import Path
from typing import Any, Dict


CANONICAL_TEX_NAME = "GSC_Framework_v10_1_FINAL.tex"


def _sha256_bytes(payload: bytes) -> str:
    h = hashlib.sha256()
    h.update(payload)
    return h.hexdigest()


def _hint_cmds(bundle_zip: Path, repo_tex: Path) -> list[str]:
    z = shlex.quote(str(bundle_zip))
    r = shlex.quote(str(repo_tex))
    return [
        f"unzip -p {z} {CANONICAL_TEX_NAME} | shasum -a 256",
        f"shasum -a 256 {r}",
        f"diff -u <(unzip -p {z} {CANONICAL_TEX_NAME}) {r} | head -n 80",
    ]


def compare_bundle_tex_vs_repo(bundle_zip: Path, repo_tex: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "match": False,
        "bundle_zip": str(bundle_zip),
        "bundle_tex_entry": CANONICAL_TEX_NAME,
        "repo_tex_path": str(repo_tex),
        "sha_bundle": None,
        "sha_repo": None,
        "warning": None,
        "hint_cmds": _hint_cmds(bundle_zip, repo_tex),
    }

    if not bundle_zip.is_file():
        result["warning"] = f"submission bundle not found: {bundle_zip}"
        return result
    if not repo_tex.is_file():
        result["warning"] = f"repo TeX not found: {repo_tex}"
        return result

    try:
        with zipfile.ZipFile(bundle_zip, "r") as zf:
            try:
                bundle_tex = zf.read(CANONICAL_TEX_NAME)
            except KeyError:
                result["warning"] = f"bundle missing TeX entry: {CANONICAL_TEX_NAME}"
                return result
    except Exception as exc:  # pragma: no cover
        result["warning"] = f"failed to read submission bundle: {exc}"
        return result

    try:
        repo_bytes = repo_tex.read_bytes()
    except Exception as exc:  # pragma: no cover
        result["warning"] = f"failed to read repo TeX: {exc}"
        return result

    sha_bundle = _sha256_bytes(bundle_tex)
    sha_repo = _sha256_bytes(repo_bytes)
    result["sha_bundle"] = sha_bundle
    result["sha_repo"] = sha_repo
    result["match"] = sha_bundle == sha_repo
    if not result["match"]:
        result["warning"] = (
            "submission bundle TeX differs from repo TeX "
            "(expected in frozen-canonical workflows; verify before upload decisions)"
        )
    return result

