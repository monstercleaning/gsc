"""Toy epsilon sensitivity helpers for Phase-4 Task 4B.2.

This module computes deterministic sensitivity scaffolding for how toy
measurement-model epsilon channels can bias inferred H0/sigma8 proxies.
It is intentionally a software-contract layer, not a likelihood analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from .translator import one_plus_z_from_sigma_ratio


EPS_KEYS: Tuple[str, str, str] = ("epsilon_em", "epsilon_qcd", "epsilon_gr")


@dataclass(frozen=True)
class ProbeSensitivityV1:
    """Probe-level toy sensitivity configuration."""

    name: str
    pivot_z: float
    # Weights map epsilon channels to an effective probe epsilon.
    weights: Mapping[str, float]


@dataclass(frozen=True)
class InferredBiases:
    """Log-bias outputs for toy inferred parameters."""

    ln_h0_inferred_ratio: float
    ln_sigma8_inferred_ratio: float


def _require_finite(value: float, *, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _validate_eps(epsilon: Mapping[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in EPS_KEYS:
        if key not in epsilon:
            raise ValueError(f"missing epsilon key: {key}")
        out[key] = _require_finite(float(epsilon[key]), name=key)
    return out


def _validate_probe(probe: ProbeSensitivityV1) -> ProbeSensitivityV1:
    z = _require_finite(float(probe.pivot_z), name=f"{probe.name}.pivot_z")
    if z <= -1.0:
        raise ValueError(f"{probe.name}.pivot_z must be > -1")
    weights = {k: _require_finite(float(probe.weights.get(k, 0.0)), name=f"{probe.name}.weights[{k}]") for k in EPS_KEYS}
    return ProbeSensitivityV1(name=str(probe.name), pivot_z=z, weights=weights)


def default_probe_configs(
    *,
    z_sn_pivot: float,
    z_bao_pivot: float,
    z_cmb_pivot: float,
    z_lensing_pivot: float,
) -> List[ProbeSensitivityV1]:
    """Return deterministic default probe configurations."""

    return [
        ProbeSensitivityV1(
            name="SN",
            pivot_z=float(z_sn_pivot),
            weights={"epsilon_em": 1.0, "epsilon_qcd": 0.0, "epsilon_gr": 0.0},
        ),
        ProbeSensitivityV1(
            name="BAO",
            pivot_z=float(z_bao_pivot),
            weights={"epsilon_em": 0.0, "epsilon_qcd": 1.0, "epsilon_gr": 0.0},
        ),
        ProbeSensitivityV1(
            name="CMB",
            pivot_z=float(z_cmb_pivot),
            weights={"epsilon_em": 0.0, "epsilon_qcd": 0.5, "epsilon_gr": 0.5},
        ),
        ProbeSensitivityV1(
            name="GW",
            pivot_z=float(z_lensing_pivot),
            weights={"epsilon_em": 0.0, "epsilon_qcd": 0.0, "epsilon_gr": 1.0},
        ),
        ProbeSensitivityV1(
            name="Lensing",
            pivot_z=float(z_lensing_pivot),
            weights={"epsilon_em": 0.0, "epsilon_qcd": 0.0, "epsilon_gr": 1.0},
        ),
    ]


def effective_probe_epsilon(probe: ProbeSensitivityV1, epsilon: Mapping[str, float]) -> float:
    """Return the effective epsilon for a probe from channel weights."""

    valid_probe = _validate_probe(probe)
    eps = _validate_eps(epsilon)
    return float(sum(float(valid_probe.weights[key]) * float(eps[key]) for key in EPS_KEYS))


def inferred_biases_for_probe(
    *,
    probe: ProbeSensitivityV1,
    epsilon: Mapping[str, float],
    h_exponent_p: float,
    growth_exponent_gamma: float,
) -> InferredBiases:
    """Compute toy inferred log-ratios for H0 and sigma8 from one probe.

    The toy model uses:
      H(z) ~ H0 * (1+z)^p
      sigma8(z) ~ sigma8_0 / (1+z)^gamma

    and the translator remapping:
      (1+z_probe) = (1+z_true)^(1+epsilon_eff)
    """

    valid_probe = _validate_probe(probe)
    p = _require_finite(float(h_exponent_p), name="h_exponent_p")
    gamma = _require_finite(float(growth_exponent_gamma), name="growth_exponent_gamma")
    eps_eff = effective_probe_epsilon(valid_probe, epsilon)

    one_plus_z_true = 1.0 + float(valid_probe.pivot_z)
    if one_plus_z_true <= 0.0:
        raise ValueError(f"{valid_probe.name}.pivot_z must keep (1+z)>0")

    one_plus_z_probe = one_plus_z_from_sigma_ratio(one_plus_z_true, eps_eff)

    ln_h0 = p * (math.log(one_plus_z_true) - math.log(one_plus_z_probe))
    ln_sigma8 = gamma * (math.log(one_plus_z_probe) - math.log(one_plus_z_true))
    return InferredBiases(
        ln_h0_inferred_ratio=float(ln_h0),
        ln_sigma8_inferred_ratio=float(ln_sigma8),
    )


def analytic_sensitivity_for_probe(
    *,
    probe: ProbeSensitivityV1,
    h_exponent_p: float,
    growth_exponent_gamma: float,
) -> Dict[str, Dict[str, float]]:
    """Return analytic sensitivities for one probe and all epsilon channels."""

    valid_probe = _validate_probe(probe)
    p = _require_finite(float(h_exponent_p), name="h_exponent_p")
    gamma = _require_finite(float(growth_exponent_gamma), name="growth_exponent_gamma")

    ln1pz = math.log(1.0 + float(valid_probe.pivot_z))
    dlnh: Dict[str, float] = {}
    dlns: Dict[str, float] = {}

    for key in EPS_KEYS:
        w = float(valid_probe.weights.get(key, 0.0))
        dlnh[key] = float(-p * ln1pz * w)
        dlns[key] = float(gamma * ln1pz * w)

    return {
        "d_ln_H0_inferred": dlnh,
        "d_ln_sigma8_inferred": dlns,
    }


def finite_difference_sensitivity_for_probe(
    *,
    probe: ProbeSensitivityV1,
    epsilon: Mapping[str, float],
    h_exponent_p: float,
    growth_exponent_gamma: float,
    delta_eps: float,
) -> Dict[str, Dict[str, float]]:
    """Return finite-difference sensitivities for one probe and all channels."""

    valid_probe = _validate_probe(probe)
    eps = _validate_eps(epsilon)
    delta = _require_finite(float(delta_eps), name="delta_eps")
    if delta <= 0.0:
        raise ValueError("delta_eps must be > 0")

    dlnh: Dict[str, float] = {}
    dlns: Dict[str, float] = {}

    for key in EPS_KEYS:
        eps_plus: Dict[str, float] = dict(eps)
        eps_minus: Dict[str, float] = dict(eps)
        eps_plus[key] += delta
        eps_minus[key] -= delta

        out_plus = inferred_biases_for_probe(
            probe=valid_probe,
            epsilon=eps_plus,
            h_exponent_p=h_exponent_p,
            growth_exponent_gamma=growth_exponent_gamma,
        )
        out_minus = inferred_biases_for_probe(
            probe=valid_probe,
            epsilon=eps_minus,
            h_exponent_p=h_exponent_p,
            growth_exponent_gamma=growth_exponent_gamma,
        )

        inv_step = 1.0 / (2.0 * delta)
        dlnh[key] = float((out_plus.ln_h0_inferred_ratio - out_minus.ln_h0_inferred_ratio) * inv_step)
        dlns[key] = float((out_plus.ln_sigma8_inferred_ratio - out_minus.ln_sigma8_inferred_ratio) * inv_step)

    return {
        "d_ln_H0_inferred": dlnh,
        "d_ln_sigma8_inferred": dlns,
    }


def sensitivity_matrix(
    *,
    probes: Sequence[ProbeSensitivityV1],
    epsilon: Mapping[str, float],
    h_exponent_p: float,
    growth_exponent_gamma: float,
    delta_eps: float,
) -> Dict[str, object]:
    """Compute deterministic analytic/FD sensitivity matrices with self-check."""

    eps = _validate_eps(epsilon)
    probe_list = [_validate_probe(p) for p in probes]
    if not probe_list:
        raise ValueError("probes must not be empty")

    analytic_h0: Dict[str, Dict[str, float]] = {}
    analytic_s8: Dict[str, Dict[str, float]] = {}
    fd_h0: Dict[str, Dict[str, float]] = {}
    fd_s8: Dict[str, Dict[str, float]] = {}

    max_diff_h0 = 0.0
    max_diff_s8 = 0.0

    for probe in probe_list:
        a = analytic_sensitivity_for_probe(
            probe=probe,
            h_exponent_p=h_exponent_p,
            growth_exponent_gamma=growth_exponent_gamma,
        )
        n = finite_difference_sensitivity_for_probe(
            probe=probe,
            epsilon=eps,
            h_exponent_p=h_exponent_p,
            growth_exponent_gamma=growth_exponent_gamma,
            delta_eps=delta_eps,
        )

        name = str(probe.name)
        analytic_h0[name] = {key: float(a["d_ln_H0_inferred"][key]) for key in EPS_KEYS}
        analytic_s8[name] = {key: float(a["d_ln_sigma8_inferred"][key]) for key in EPS_KEYS}
        fd_h0[name] = {key: float(n["d_ln_H0_inferred"][key]) for key in EPS_KEYS}
        fd_s8[name] = {key: float(n["d_ln_sigma8_inferred"][key]) for key in EPS_KEYS}

        for key in EPS_KEYS:
            diff_h0 = abs(analytic_h0[name][key] - fd_h0[name][key])
            diff_s8 = abs(analytic_s8[name][key] - fd_s8[name][key])
            if diff_h0 > max_diff_h0:
                max_diff_h0 = float(diff_h0)
            if diff_s8 > max_diff_s8:
                max_diff_s8 = float(diff_s8)

    return {
        "analytic": {
            "d_ln_H0_inferred_d_epsilon": analytic_h0,
            "d_ln_sigma8_inferred_d_epsilon": analytic_s8,
        },
        "finite_difference": {
            "d_ln_H0_inferred_d_epsilon": fd_h0,
            "d_ln_sigma8_inferred_d_epsilon": fd_s8,
        },
        "self_check": {
            "max_abs_diff_d_ln_H0": float(max_diff_h0),
            "max_abs_diff_d_ln_sigma8": float(max_diff_s8),
            "max_abs_diff_overall": float(max(max_diff_h0, max_diff_s8)),
        },
    }


def probe_table(probes: Sequence[ProbeSensitivityV1]) -> Dict[str, Dict[str, object]]:
    """Return deterministic probe metadata table for reports."""

    out: Dict[str, Dict[str, object]] = {}
    for probe in probes:
        p = _validate_probe(probe)
        out[p.name] = {
            "pivot_z": float(p.pivot_z),
            "weights": {key: float(p.weights.get(key, 0.0)) for key in EPS_KEYS},
        }
    return out
