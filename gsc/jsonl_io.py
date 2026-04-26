"""Shared stdlib helpers for transparent JSONL / JSONL.GZ I/O."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple


def is_gz(path: Path | str) -> bool:
    """Return True when the path uses gzip suffix-based semantics."""
    return str(path).lower().endswith(".gz")


def _normalize_text_mode(mode: str) -> str:
    text_mode = str(mode).strip()
    if not text_mode:
        raise ValueError("mode must be non-empty")
    if "b" not in text_mode and "t" not in text_mode:
        text_mode += "t"
    return text_mode


def open_text_auto(path: Path | str, mode: str, encoding: str = "utf-8", newline: str = ""):
    """Open plain or gzip-compressed text streams based on suffix."""
    p = Path(path)
    text_mode = _normalize_text_mode(mode)
    is_binary = "b" in text_mode
    if is_gz(p):
        if is_binary:
            return gzip.open(p, text_mode)
        return gzip.open(p, text_mode, encoding=encoding, newline=newline)
    if is_binary:
        return p.open(text_mode)
    return p.open(text_mode, encoding=encoding, newline=newline)


def open_text_read(path: Path | str, encoding: str = "utf-8"):
    """Open a text reader for plain or gzip-compressed files."""
    return open_text_auto(path, "r", encoding=encoding, newline="")


def open_text_write(path: Path | str, encoding: str = "utf-8"):
    """Open a text writer for plain or gzip-compressed files."""
    return open_text_auto(path, "w", encoding=encoding, newline="")


def open_text_append(path: Path | str, encoding: str = "utf-8"):
    """Open a text appender for plain or gzip-compressed files."""
    return open_text_auto(path, "a", encoding=encoding, newline="")


def iter_jsonl_lines(path: Path | str) -> Iterator[Tuple[int, str]]:
    """Yield non-empty JSONL lines as (1-based line number, raw line text)."""
    with open_text_read(path) as fh:
        for lineno, raw in enumerate(fh, start=1):
            text = str(raw).strip()
            if not text:
                continue
            yield int(lineno), str(text)


def try_parse_json(line_text: str) -> Tuple[bool, Optional[Mapping[str, Any]]]:
    """Best-effort JSON object parser for robust streaming loops."""
    try:
        parsed = json.loads(str(line_text))
    except Exception:
        return False, None
    if not isinstance(parsed, Mapping):
        return False, None
    return True, parsed


def iter_jsonl_records(
    path: Path | str,
    *,
    on_invalid: str = "count",
    max_invalid: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield JSON object records from a JSONL(.gz) stream.

    Invalid JSON lines and non-object JSON lines are ignored in ``on_invalid='count'``
    mode. ``on_invalid='raise'`` raises ``ValueError`` on the first invalid line.
    ``max_invalid`` can enforce an upper invalid-line bound in count mode.
    """
    if str(on_invalid) not in {"count", "raise"}:
        raise ValueError("on_invalid must be 'count' or 'raise'")
    invalid = 0
    for lineno, line in iter_jsonl_lines(path):
        ok, parsed = try_parse_json(line)
        if ok and isinstance(parsed, Mapping):
            yield {str(k): parsed[k] for k in parsed.keys()}
            continue
        if str(on_invalid) == "raise":
            raise ValueError(f"invalid JSON object at line {int(lineno)} in {path}")
        invalid += 1
        if max_invalid is not None and int(invalid) > int(max_invalid):
            raise ValueError(f"invalid JSON line limit exceeded for {path}: {invalid}>{max_invalid}")
