"""Minimal dataset interfaces for late-time checks (v11.0.0).

Design goals:
- dependency-free (stdlib only)
- explicit nuisance handling (fit analytically when possible)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol


class HzModel(Protocol):
    """A late-time history model providing H(z) in 1/s."""

    def H(self, z: float) -> float:  # pragma: no cover - Protocol signature only
        ...


@dataclass(frozen=True)
class Chi2Result:
    chi2: float
    ndof: int
    params: Dict[str, float]
    meta: Dict[str, Any] = field(default_factory=dict)


DatasetChi2 = Callable[[HzModel], Chi2Result]
