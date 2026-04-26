"""Epsilon-framework translator MVP utilities.

This module intentionally implements a minimal toy translator ansatz for Phase-4
Task 4B.1. It is a software-contract scaffold, not a validated physical
derivation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class EpsilonVectorV1:
    """Minimal epsilon vector for translator MVP wiring.

    `epsilon_gr` is optional in the MVP because not all toy probes in this
    stage consume a gravity-channel epsilon directly.
    """

    epsilon_em: float
    epsilon_qcd: float
    epsilon_gr: Optional[float] = None


def _require_finite(value: float, *, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _validate_sigma_ratio(sigma_ratio: float) -> float:
    out = _require_finite(float(sigma_ratio), name="sigma_ratio")
    if out <= 0.0:
        raise ValueError("sigma_ratio must be > 0")
    return out


def _validate_sigma_ratio_grid(sigma_ratio_grid: Iterable[float]) -> List[float]:
    values = [_validate_sigma_ratio(float(v)) for v in sigma_ratio_grid]
    if not values:
        raise ValueError("sigma_ratio_grid must not be empty")
    return values


def one_plus_z_from_sigma_ratio(sigma_ratio: float, epsilon: float) -> float:
    """Return translated ``1+z`` using the M148 toy ansatz.

    Toy ansatz (explicitly non-final):
        (1 + z_sector) = (sigma_ratio)^(1 + epsilon_sector)

    Contract requirement:
    - when ``epsilon == 0``, the return value is exactly ``sigma_ratio``.
    """

    sr = _validate_sigma_ratio(float(sigma_ratio))
    eps = _require_finite(float(epsilon), name="epsilon")

    if eps == 0.0:
        return sr

    exponent = 1.0 + eps
    translated = sr ** exponent
    if not math.isfinite(translated):
        raise ValueError("translated one_plus_z is non-finite")
    if translated <= 0.0:
        raise ValueError("translated one_plus_z must be > 0")
    return float(translated)


def mismatch_metrics(
    sigma_ratio_grid: Iterable[float],
    eps_em: float,
    eps_qcd: float,
) -> Dict[str, Any]:
    """Return deterministic mismatch summaries between EM and QCD channels.

    The output is intentionally compact and scalar-only, suitable for report
    summaries.
    """

    grid = _validate_sigma_ratio_grid(sigma_ratio_grid)
    eps_em_f = _require_finite(float(eps_em), name="eps_em")
    eps_qcd_f = _require_finite(float(eps_qcd), name="eps_qcd")

    delta_ln_values: List[float] = []
    delta_z_values: List[float] = []
    delta_one_plus_z_values: List[float] = []

    for sr in grid:
        onepz_em = one_plus_z_from_sigma_ratio(sr, eps_em_f)
        onepz_qcd = one_plus_z_from_sigma_ratio(sr, eps_qcd_f)
        delta_ln = math.log(onepz_em) - math.log(onepz_qcd)
        delta_onepz = onepz_em - onepz_qcd
        delta_z = (onepz_em - 1.0) - (onepz_qcd - 1.0)

        delta_ln_values.append(float(delta_ln))
        delta_one_plus_z_values.append(float(delta_onepz))
        delta_z_values.append(float(delta_z))

    n = len(grid)

    def _mean(values: Sequence[float]) -> float:
        return float(sum(values) / float(len(values)))

    def _rms(values: Sequence[float]) -> float:
        return float(math.sqrt(sum(v * v for v in values) / float(len(values))))

    def _max_abs(values: Sequence[float]) -> float:
        return float(max(abs(v) for v in values))

    return {
        "n_points": int(n),
        "sigma_ratio_min": float(min(grid)),
        "sigma_ratio_max": float(max(grid)),
        "eps_em": float(eps_em_f),
        "eps_qcd": float(eps_qcd_f),
        "mean_delta_ln_1pz_em_minus_qcd": _mean(delta_ln_values),
        "rms_delta_ln_1pz_em_minus_qcd": _rms(delta_ln_values),
        "max_abs_delta_ln_1pz_em_minus_qcd": _max_abs(delta_ln_values),
        "mean_delta_one_plus_z_em_minus_qcd": _mean(delta_one_plus_z_values),
        "rms_delta_one_plus_z_em_minus_qcd": _rms(delta_one_plus_z_values),
        "max_abs_delta_one_plus_z_em_minus_qcd": _max_abs(delta_one_plus_z_values),
        "mean_delta_z_em_minus_qcd": _mean(delta_z_values),
        "rms_delta_z_em_minus_qcd": _rms(delta_z_values),
        "max_abs_delta_z_em_minus_qcd": _max_abs(delta_z_values),
    }
