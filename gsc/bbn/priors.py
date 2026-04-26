"""Optional BBN-inspired priors for early-time diagnostics.

This module provides conservative, dataset-style Gaussian priors used as an
optional additive chi2 term in Phase-2 scan diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional, Tuple


BBN_PRIOR_MODES: Tuple[str, ...] = ("none", "weak", "standard")


@dataclass(frozen=True)
class _BBNPriorSpec:
    mode: str
    omega_b_h2_mu: float
    omega_b_h2_sigma: float
    reference: str


_BBN_SPECS: Dict[str, _BBNPriorSpec] = {
    "weak": _BBNPriorSpec(
        mode="weak",
        omega_b_h2_mu=0.0224,
        omega_b_h2_sigma=0.0010,
        reference="bbn_baryon_weak_anchor",
    ),
    "standard": _BBNPriorSpec(
        mode="standard",
        omega_b_h2_mu=0.0224,
        omega_b_h2_sigma=0.00035,
        reference="bbn_baryon_standard_anchor",
    ),
}


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def canonical_bbn_prior_mode(value: str) -> str:
    mode = str(value).strip().lower()
    if mode not in BBN_PRIOR_MODES:
        raise ValueError(f"Unsupported BBN prior mode: {value!r}")
    return mode


@dataclass(frozen=True)
class BBNPriorResult:
    mode: str
    enabled: bool
    chi2: float
    terms: Mapping[str, Mapping[str, float]]
    reference: Optional[str]

    def to_json(self) -> Dict[str, Any]:
        return {
            "mode": str(self.mode),
            "enabled": bool(self.enabled),
            "chi2": float(self.chi2),
            "terms": {
                str(k): {
                    "value": float(v["value"]),
                    "mu": float(v["mu"]),
                    "sigma": float(v["sigma"]),
                    "pull": float(v["pull"]),
                    "chi2": float(v["chi2"]),
                }
                for k, v in sorted(self.terms.items(), key=lambda kv: str(kv[0]))
            },
            "reference": None if self.reference is None else str(self.reference),
        }


def evaluate_bbn_prior_chi2(
    *,
    mode: str,
    omega_b_h2: Any,
) -> BBNPriorResult:
    """Evaluate optional BBN prior chi2.

    Parameters
    ----------
    mode:
        One of ``none``, ``weak``, ``standard``.
    omega_b_h2:
        Baryon density parameter (dimensionless physical density).
    """

    mode_canonical = canonical_bbn_prior_mode(mode)
    if mode_canonical == "none":
        return BBNPriorResult(
            mode="none",
            enabled=False,
            chi2=0.0,
            terms={},
            reference=None,
        )

    spec = _BBN_SPECS[mode_canonical]
    value = _finite_float(omega_b_h2)
    if value is None:
        raise ValueError("omega_b_h2 must be finite for BBN prior evaluation")
    pull = (float(value) - float(spec.omega_b_h2_mu)) / float(spec.omega_b_h2_sigma)
    contrib = float(pull * pull)
    terms = {
        "omega_b_h2": {
            "value": float(value),
            "mu": float(spec.omega_b_h2_mu),
            "sigma": float(spec.omega_b_h2_sigma),
            "pull": float(pull),
            "chi2": float(contrib),
        }
    }
    return BBNPriorResult(
        mode=str(mode_canonical),
        enabled=True,
        chi2=float(contrib),
        terms=terms,
        reference=str(spec.reference),
    )

