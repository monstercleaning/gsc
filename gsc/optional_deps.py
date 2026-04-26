"""Helpers for optional third-party dependencies.

Use these helpers in tests and optional diagnostic paths so environments without
the scientific stack fail gracefully (SKIP) instead of import-time errors.
"""

from __future__ import annotations

import importlib.util
import unittest
from typing import Any

_INSTALL_HINT = "Install optional scientific deps via: bash v11.0.0/scripts/bootstrap_venv.sh"


def missing_dependency_message(name: str) -> str:
    dep = str(name).strip() or "dependency"
    return f"{dep} is required for this operation. {_INSTALL_HINT}"


def has_module(name: str) -> bool:
    return importlib.util.find_spec(str(name)) is not None


def has_numpy() -> bool:
    return has_module("numpy")


def has_matplotlib() -> bool:
    return has_module("matplotlib")


def skip_module_unless_numpy(reason: str = "numpy not installed") -> None:
    if not has_numpy():
        raise unittest.SkipTest(reason)


def skip_testcase_unless_numpy(tc: unittest.TestCase, reason: str = "numpy not installed") -> None:
    if not has_numpy():
        tc.skipTest(reason)


def skip_testcase_unless_matplotlib(tc: unittest.TestCase, reason: str = "matplotlib not installed") -> None:
    if not has_matplotlib():
        tc.skipTest(reason)


def require_numpy() -> Any:
    try:
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive path
        raise RuntimeError(missing_dependency_message("numpy")) from exc
    return np
