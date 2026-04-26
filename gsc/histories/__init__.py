"""History classes for diagnostic-only experiments (v11.0.0).

This package is intentionally **not** used by the canonical late-time pipeline.
It exists to support opt-in E2 diagnostics (full-range / no-stitch closure).
"""

from .full_range import FlatLCDMRadHistory, GSCTransitionFullHistory, HBoostWrapper

__all__ = [
    "FlatLCDMRadHistory",
    "GSCTransitionFullHistory",
    "HBoostWrapper",
]
