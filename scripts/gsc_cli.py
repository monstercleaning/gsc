#!/usr/bin/env python3
"""Convenience wrapper for the unified GSC CLI."""

from __future__ import annotations

from pathlib import Path
import sys


V101_DIR = Path(__file__).resolve().parents[1]
if str(V101_DIR) not in sys.path:
    sys.path.insert(0, str(V101_DIR))

from gsc.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
