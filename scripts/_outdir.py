"""Shared output-directory helpers for v11.0.0 scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def resolve_outdir(
    cli_outdir: Optional[Path],
    *,
    v101_dir: Path,
    env_var: str = "GSC_OUTDIR",
    default_rel: str = "artifacts/release",
) -> Path:
    """Resolve output root with precedence: CLI > env > default.

    Relative paths are resolved against repo root (parent of v11.0.0).
    """
    repo_root = v101_dir.parent
    if cli_outdir is not None:
        p = Path(cli_outdir).expanduser()
    else:
        env = (os.environ.get(env_var) or "").strip()
        if env:
            p = Path(env).expanduser()
        else:
            p = v101_dir / default_rel
    if not p.is_absolute():
        p = repo_root / p
    return p.resolve()


def resolve_path_under_outdir(path: Optional[Path], *, out_root: Path) -> Optional[Path]:
    """Resolve a user path under out_root when relative; preserve absolute paths."""
    if path is None:
        return None
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (out_root / p).resolve()
