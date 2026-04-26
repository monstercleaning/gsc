#!/usr/bin/env python3
"""Deterministic SigmaTensor-v1 no-go gap diagnostic (Phase-4 M146 / Task 4A.-0)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import H0_to_SI  # noqa: E402
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


TOOL = "phase4_sigmatensor_optimal_control_gap_diagnostic"
TOOL_VERSION = "m146-v1"
SCHEMA = "phase4_sigmatensor_optimal_control_gap_diagnostic_report_v1"
FAIL_MARKER = "PHASE4_SIGMATENSOR_GAP_DIAGNOSTIC_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
REQUIRED_EVAL_Z: Tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
REQUIRED_DISTANCE_Z: Tuple[float, ...] = (0.5, 1.0, 2.0)


class UsageError(Exception):
    """Invalid CLI usage."""


class DiagnosticError(Exception):
    """Diagnostic/precondition failure."""


@dataclass(frozen=True)
class GapContext:
    z_grid: Tuple[float, ...]
    H_baseline: Tuple[float, ...]
    H0_si: float
    Omega_m0: float
    Omega_r0: float
    eval_z: Tuple[float, ...]
    distance_z: Tuple[float, ...]
    baseline_distance_by_z: Mapping[float, float]
    knot_z: Tuple[float, ...]
    reg_l2: float
    reg_curvature: float
    infeasible_penalty: float


@dataclass(frozen=True)
class CandidateResult:
    theta: Tuple[float, ...]
    objective: float
    distance_mismatch_rms: float
    reg_l2_term: float
    reg_curvature_term: float
    feasible: bool
    min_drift_norm_eval: float
    drift_eval_rows: Tuple[Mapping[str, Any], ...]
    distance_rows: Tuple[Mapping[str, Any], ...]
    implied_w_min: Optional[float]
    implied_w_max: Optional[float]
    implied_w_ge_minus_one: bool
    rho_de_positive_all: bool
    physically_allowed_canonical: bool


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _fmt_e(value: float) -> str:
    return f"{float(value):.12e}"


def _stable_key(value: float) -> str:
    return _fmt_e(float(value))


def _to_iso_utc(epoch_seconds: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    except Exception as exc:
        raise UsageError("--created-utc must be a valid integer epoch-seconds value") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_csv_floats(text: str, *, name: str) -> List[float]:
    out: List[float] = []
    for raw in str(text).split(","):
        token = raw.strip()
        if not token:
            continue
        try:
            value = float(token)
        except Exception as exc:
            raise UsageError(f"{name} must be a comma-separated float list") from exc
        if not math.isfinite(value):
            raise UsageError(f"{name} contains non-finite value")
        out.append(float(value))
    if not out:
        raise UsageError(f"{name} produced empty list")
    return out


def _dedupe_sorted(values: Iterable[float]) -> List[float]:
    return [float(v) for v in sorted({float(x) for x in values})]


def _build_linear_grid(vmin: float, vmax: float, n: int) -> List[float]:
    if int(n) < 1:
        raise UsageError("grid size must be >= 1")
    if not (math.isfinite(vmin) and math.isfinite(vmax)):
        raise UsageError("grid bounds must be finite")
    if float(vmax) < float(vmin):
        raise UsageError("grid max must be >= min")
    if int(n) == 1:
        return [float(vmin)]
    step = (float(vmax) - float(vmin)) / float(int(n) - 1)
    return [float(vmin + i * step) for i in range(int(n))]


def _interp_linear(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise DiagnosticError("interpolation arrays must have same length >= 2")
    xx = float(x)
    if xx < float(xs[0]) or xx > float(xs[-1]):
        raise DiagnosticError(f"x={xx} outside interpolation range [{xs[0]}, {xs[-1]}]")
    if xx == float(xs[0]):
        return float(ys[0])
    if xx == float(xs[-1]):
        return float(ys[-1])
    lo = 0
    hi = len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if float(xs[mid]) <= xx:
            lo = mid
        else:
            hi = mid
    xl = float(xs[lo])
    xr = float(xs[hi])
    yl = float(ys[lo])
    yr = float(ys[hi])
    if xr <= xl:
        return float(yl)
    t = (xx - xl) / (xr - xl)
    return float(yl + (yr - yl) * t)


def _cumulative_trapz(xs: Sequence[float], ys: Sequence[float]) -> List[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise DiagnosticError("trapz arrays must have same length >= 2")
    out: List[float] = [0.0]
    total = 0.0
    for i in range(1, len(xs)):
        dx = float(xs[i]) - float(xs[i - 1])
        total += 0.5 * (float(ys[i]) + float(ys[i - 1])) * dx
        out.append(float(total))
    return out


def _integral_to(x: float, xs: Sequence[float], cumulative: Sequence[float]) -> float:
    if len(xs) != len(cumulative):
        raise DiagnosticError("integral table length mismatch")
    return _interp_linear(float(x), xs, cumulative)


def _knot_positions(z_min: float, z_max: float, n_knots: int) -> List[float]:
    return _build_linear_grid(float(z_min), float(z_max), int(n_knots))


def _theta_to_amplitude(z: float, knot_z: Sequence[float], theta: Sequence[float]) -> float:
    log_a = _interp_linear(float(z), knot_z, theta)
    # Keep positive multiplicative deformation by exponentiating the control profile.
    return float(math.exp(float(log_a)))


def _theta_to_amplitude_grid(z_grid: Sequence[float], knot_z: Sequence[float], theta: Sequence[float]) -> List[float]:
    return [_theta_to_amplitude(float(z), knot_z, theta) for z in z_grid]


def _second_diff_mean_sq(values: Sequence[float]) -> float:
    n = len(values)
    if n < 3:
        return 0.0
    acc = 0.0
    count = 0
    for i in range(1, n - 1):
        d2 = float(values[i + 1]) - 2.0 * float(values[i]) + float(values[i - 1])
        acc += d2 * d2
        count += 1
    if count == 0:
        return 0.0
    return float(acc / float(count))


def _theta_key(theta: Sequence[float]) -> Tuple[float, ...]:
    return tuple(float(f"{float(v):.16e}") for v in theta)


def _seed_thetas(n_knots: int, *, toy_mode: bool) -> List[Tuple[float, ...]]:
    if n_knots < 3:
        raise UsageError("n-knots must be >= 3")

    levels = (0.12, 0.24, 0.36) if toy_mode else (0.10, 0.20, 0.30, 0.45, 0.60)
    seeds: List[Tuple[float, ...]] = [tuple(0.0 for _ in range(n_knots))]

    for level in levels:
        flat = tuple(-float(level) for _ in range(n_knots))
        ramp = tuple(-float(level) * (float(i) / float(n_knots - 1)) for i in range(n_knots))
        highz = tuple(
            -float(level)
            * max(0.0, (float(i) / float(n_knots - 1)) - 0.4)
            / 0.6
            for i in range(n_knots)
        )
        mid = tuple(
            -float(level)
            * (0.4 + 0.6 * max(0.0, 1.0 - abs((2.0 * i / float(n_knots - 1)) - 1.0)))
            for i in range(n_knots)
        )
        seeds.extend([flat, ramp, highz, mid])

    unique: Dict[Tuple[float, ...], Tuple[float, ...]] = {}
    for seed in seeds:
        unique[_theta_key(seed)] = tuple(float(v) for v in seed)
    return [unique[k] for k in sorted(unique.keys())]


def _clip_theta(theta: Sequence[float], theta_max_abs: float) -> Tuple[float, ...]:
    out: List[float] = []
    lim = float(abs(theta_max_abs))
    for value in theta:
        v = float(value)
        if v > lim:
            v = lim
        if v < -lim:
            v = -lim
        out.append(float(v))
    return tuple(out)


def _implied_w_profile(
    *,
    z_grid: Sequence[float],
    H_grid_si: Sequence[float],
    H0_si: float,
    Omega_m0: float,
    Omega_r0: float,
) -> Dict[str, Any]:
    n = len(z_grid)
    if n < 2:
        raise DiagnosticError("z_grid must have at least two points for implied w check")

    rho_de: List[float] = []
    for z, h in zip(z_grid, H_grid_si):
        zp1 = 1.0 + float(z)
        e2 = (float(h) / float(H0_si)) ** 2
        val = e2 - float(Omega_m0) * (zp1 ** 3) - float(Omega_r0) * (zp1 ** 4)
        rho_de.append(float(val))

    rho_pos = all((v > 0.0 and math.isfinite(v)) for v in rho_de)
    if not rho_pos:
        return {
            "rho_de_positive_all": False,
            "w_ge_minus_one": False,
            "w_min": None,
            "w_max": None,
            "n_w_violations": int(sum(1 for v in rho_de if not (v > 0.0 and math.isfinite(v)))),
        }

    x_grid = [math.log1p(float(z)) for z in z_grid]
    ln_rho = [math.log(float(v)) for v in rho_de]
    w_values: List[float] = []
    for i in range(n):
        if i == 0:
            num = ln_rho[1] - ln_rho[0]
            den = x_grid[1] - x_grid[0]
        elif i == n - 1:
            num = ln_rho[-1] - ln_rho[-2]
            den = x_grid[-1] - x_grid[-2]
        else:
            num = ln_rho[i + 1] - ln_rho[i - 1]
            den = x_grid[i + 1] - x_grid[i - 1]
        if not (den > 0.0 and math.isfinite(den)):
            raise DiagnosticError("non-positive x-grid spacing encountered")
        dlnrho_dln1pz = num / den
        w_val = -1.0 + (1.0 / 3.0) * dlnrho_dln1pz
        w_values.append(float(w_val))

    w_min = min(w_values)
    w_max = max(w_values)
    tol = 1.0e-10
    ge_minus_one = all(float(w) >= (-1.0 - tol) for w in w_values)
    n_viol = int(sum(1 for w in w_values if float(w) < (-1.0 - tol)))
    return {
        "rho_de_positive_all": True,
        "w_ge_minus_one": bool(ge_minus_one),
        "w_min": float(w_min),
        "w_max": float(w_max),
        "n_w_violations": n_viol,
    }


def _evaluate_theta(theta: Sequence[float], ctx: GapContext) -> CandidateResult:
    theta_vec = tuple(float(v) for v in theta)

    amp_grid = _theta_to_amplitude_grid(ctx.z_grid, ctx.knot_z, theta_vec)
    H_def = [float(a * h) for a, h in zip(amp_grid, ctx.H_baseline)]

    drift_eval_rows: List[Dict[str, Any]] = []
    min_drift_norm = float("inf")
    feasible = True
    for z_eval in ctx.eval_z:
        h_eval = _interp_linear(float(z_eval), ctx.z_grid, H_def)
        dzdt = float(ctx.H0_si) * (1.0 + float(z_eval)) - float(h_eval)
        dnorm = dzdt / float(ctx.H0_si)
        min_drift_norm = min(min_drift_norm, dnorm)
        sign = 1 if dzdt > 0.0 else (-1 if dzdt < 0.0 else 0)
        if dnorm <= 0.0:
            feasible = False
        drift_eval_rows.append(
            {
                "z": float(z_eval),
                "H_deformed_si": float(h_eval),
                "dz_dt0_si": float(dzdt),
                "drift_sign": int(sign),
            }
        )

    inv_h = [1.0 / float(h) for h in H_def]
    cumulative = _cumulative_trapz(ctx.z_grid, inv_h)

    distance_rows: List[Dict[str, Any]] = []
    sq_sum = 0.0
    for z_t in ctx.distance_z:
        d_def = _integral_to(float(z_t), ctx.z_grid, cumulative)
        d_baseline = float(ctx.baseline_distance_by_z[float(z_t)])
        rel = (float(d_def) - float(d_baseline)) / max(abs(float(d_baseline)), 1.0e-30)
        sq_sum += rel * rel
        distance_rows.append(
            {
                "z": float(z_t),
                "distance_baseline": float(d_baseline),
                "distance_deformed": float(d_def),
                "relative_mismatch": float(rel),
            }
        )
    distance_mismatch = math.sqrt(sq_sum / float(len(ctx.distance_z)))

    l2_term = float(sum(float(t) * float(t) for t in theta_vec) / float(len(theta_vec)))
    curv_term = _second_diff_mean_sq(theta_vec)

    objective = (
        float(distance_mismatch)
        + float(ctx.reg_l2) * float(l2_term)
        + float(ctx.reg_curvature) * float(curv_term)
    )
    if not feasible:
        # Penalty on normalized drift deficits; deterministic and smooth around boundary.
        penalty = float(ctx.infeasible_penalty) * (abs(float(min_drift_norm)) + 1.0e-6)
        objective += penalty

    w_info = _implied_w_profile(
        z_grid=ctx.z_grid,
        H_grid_si=H_def,
        H0_si=float(ctx.H0_si),
        Omega_m0=float(ctx.Omega_m0),
        Omega_r0=float(ctx.Omega_r0),
    )

    implied_w_min = w_info.get("w_min")
    implied_w_max = w_info.get("w_max")
    w_ge_minus_one = bool(w_info.get("w_ge_minus_one"))
    rho_positive_all = bool(w_info.get("rho_de_positive_all"))
    physically_allowed = bool(feasible and rho_positive_all and w_ge_minus_one)

    return CandidateResult(
        theta=theta_vec,
        objective=float(objective),
        distance_mismatch_rms=float(distance_mismatch),
        reg_l2_term=float(l2_term),
        reg_curvature_term=float(curv_term),
        feasible=bool(feasible),
        min_drift_norm_eval=float(min_drift_norm),
        drift_eval_rows=tuple(drift_eval_rows),
        distance_rows=tuple(distance_rows),
        implied_w_min=float(implied_w_min) if implied_w_min is not None else None,
        implied_w_max=float(implied_w_max) if implied_w_max is not None else None,
        implied_w_ge_minus_one=bool(w_ge_minus_one),
        rho_de_positive_all=bool(rho_positive_all),
        physically_allowed_canonical=bool(physically_allowed),
    )


def _is_better_search_candidate(
    cand: CandidateResult,
    best: CandidateResult,
    *,
    cand_theta: Sequence[float],
    best_theta: Sequence[float],
) -> bool:
    eps = 1.0e-16
    if float(cand.objective) < float(best.objective) - eps:
        return True
    if float(cand.objective) > float(best.objective) + eps:
        return False
    if bool(cand.feasible) and (not bool(best.feasible)):
        return True
    if (not bool(cand.feasible)) and bool(best.feasible):
        return False
    if float(cand.distance_mismatch_rms) < float(best.distance_mismatch_rms) - eps:
        return True
    if float(cand.distance_mismatch_rms) > float(best.distance_mismatch_rms) + eps:
        return False
    return _theta_key(cand_theta) < _theta_key(best_theta)


def _optimize_for_context(
    *,
    ctx: GapContext,
    theta_max_abs: float,
    step_values: Sequence[float],
    toy_mode: bool,
) -> Tuple[Optional[CandidateResult], CandidateResult]:
    seeds = _seed_thetas(len(ctx.knot_z), toy_mode=bool(toy_mode))
    all_final: List[CandidateResult] = []

    for seed in seeds:
        theta = _clip_theta(seed, theta_max_abs=float(theta_max_abs))
        best_local = _evaluate_theta(theta, ctx)

        for step in step_values:
            s = float(step)
            if not (s > 0.0 and math.isfinite(s)):
                continue
            improved = True
            while improved:
                improved = False
                for i in range(len(theta)):
                    for direction in (-1.0, +1.0):
                        trial_list = list(theta)
                        trial_list[i] = float(trial_list[i]) + float(direction) * s
                        trial_theta = _clip_theta(trial_list, theta_max_abs=float(theta_max_abs))
                        if _theta_key(trial_theta) == _theta_key(theta):
                            continue
                        trial_eval = _evaluate_theta(trial_theta, ctx)
                        if _is_better_search_candidate(
                            trial_eval,
                            best_local,
                            cand_theta=trial_theta,
                            best_theta=theta,
                        ):
                            theta = trial_theta
                            best_local = trial_eval
                            improved = True

        all_final.append(best_local)

    if not all_final:
        raise DiagnosticError("internal optimization produced no candidates")

    best_any = min(
        all_final,
        key=lambda item: (
            float(item.objective),
            float(item.distance_mismatch_rms),
            _theta_key(item.theta),
        ),
    )

    feasible_rows = [row for row in all_final if bool(row.feasible)]
    best_feasible: Optional[CandidateResult]
    if feasible_rows:
        best_feasible = min(
            feasible_rows,
            key=lambda item: (
                float(item.distance_mismatch_rms),
                float(item.objective),
                _theta_key(item.theta),
            ),
        )
    else:
        best_feasible = None

    return best_feasible, best_any


def _candidate_to_payload(
    *,
    result: CandidateResult,
    lambda_value: float,
    ctx: GapContext,
) -> Dict[str, Any]:
    control_knots = [
        {
            "z": float(z),
            "log_amplitude": float(t),
            "amplitude": float(math.exp(float(t))),
        }
        for z, t in zip(ctx.knot_z, result.theta)
    ]

    return {
        "lambda": float(lambda_value),
        "feasible_drift_positive_all_eval": bool(result.feasible),
        "physically_allowed_canonical": bool(result.physically_allowed_canonical),
        "distance_mismatch_rms": float(result.distance_mismatch_rms),
        "objective": float(result.objective),
        "regularization_l2": float(result.reg_l2_term),
        "regularization_curvature": float(result.reg_curvature_term),
        "min_drift_norm_eval": float(result.min_drift_norm_eval),
        "implied_w_min": float(result.implied_w_min) if result.implied_w_min is not None else None,
        "implied_w_max": float(result.implied_w_max) if result.implied_w_max is not None else None,
        "implied_w_ge_minus_one": bool(result.implied_w_ge_minus_one),
        "rho_de_positive_all": bool(result.rho_de_positive_all),
        "drift_eval": [dict(row) for row in result.drift_eval_rows],
        "distance_targets": [dict(row) for row in result.distance_rows],
        "control_knots": control_knots,
        "note": (
            "mathematically found but physically forbidden for canonical quintessence"
            if (bool(result.feasible) and not bool(result.physically_allowed_canonical))
            else ("infeasible under drift-positive constraints" if not bool(result.feasible) else "feasible")
        ),
    }


def _baseline_eval_payload(*, eval_z: Sequence[float], history: SigmaTensorV1History, H0_si: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for z in eval_z:
        h = float(history.H(float(z)))
        drift = float(H0_si) * (1.0 + float(z)) - h
        rows.append(
            {
                "z": float(z),
                "H_baseline_si": float(h),
                "dz_dt0_si": float(drift),
                "drift_sign": 1 if drift > 0.0 else (-1 if drift < 0.0 else 0),
            }
        )
    return rows


def _drift_at_z(baseline_eval_rows: Sequence[Mapping[str, Any]], z: float) -> Optional[float]:
    for row in baseline_eval_rows:
        if abs(float(row.get("z", float("nan"))) - float(z)) <= 1.0e-12:
            val = row.get("dz_dt0_si")
            if isinstance(val, (int, float)):
                return float(val)
    return None


def _render_text(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    rows = payload.get("gap_by_lambda") if isinstance(payload.get("gap_by_lambda"), list) else []

    lines.append("SigmaTensor optimal-control gap diagnostic")
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"status={payload.get('status')}")
    lines.append(
        "summary="
        f"feasible_count={int(summary.get('feasible_count', 0))} "
        f"infeasible_count={int(summary.get('infeasible_count', 0))} "
        f"any_physically_allowed_feasible={bool(summary.get('any_physically_allowed_feasible'))}"
    )
    lines.append(
        f"best_gap_metric_distance_mismatch={summary.get('best_gap_metric_distance_mismatch')}"
    )
    lines.append("lambda,feasible,physical_ok,distance_mismatch_rms,min_drift_norm_eval,implied_w_min")

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            ",".join(
                [
                    f"{float(row.get('lambda')):.6g}",
                    "1" if bool(row.get("feasible_drift_positive_all_eval")) else "0",
                    "1" if bool(row.get("physically_allowed_canonical")) else "0",
                    f"{float(row.get('distance_mismatch_rms')):.12e}" if row.get("distance_mismatch_rms") is not None else "nan",
                    f"{float(row.get('min_drift_norm_eval')):.12e}" if row.get("min_drift_norm_eval") is not None else "nan",
                    f"{float(row.get('implied_w_min')):.12e}" if row.get("implied_w_min") is not None else "nan",
                ]
            )
        )

    return "\n".join(lines) + "\n"


def _render_markdown(payload: Mapping[str, Any]) -> str:
    params = payload.get("params") if isinstance(payload.get("params"), Mapping) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    rows = payload.get("gap_by_lambda") if isinstance(payload.get("gap_by_lambda"), list) else []

    lines: List[str] = []
    lines.append("# SigmaTensor Optimal-Control Gap Diagnostic (Task 4A.-0 repurposed)")
    lines.append("")
    lines.append("This diagnostic quantifies how much `H(z)` must be deformed to force positive drift")
    lines.append("over `z in [2,5]`, while minimizing distance-integral mismatch to the SigmaTensor baseline.")
    lines.append("")
    lines.append("## Parameters")
    lines.append(f"- H0_km_s_Mpc: `{float(params.get('H0_km_s_Mpc')):.12g}`")
    lines.append(f"- Omega_m0: `{float(params.get('Omega_m0')):.12g}`")
    lines.append(f"- w_phi0: `{float(params.get('w_phi0')):.12g}`")
    lines.append(
        f"- lambda grid: `[{float(params.get('lambda_min')):.12g}, {float(params.get('lambda_max')):.12g}]` with `n_lambda={int(params.get('n_lambda'))}`"
    )
    lines.append(
        f"- deformation DOF: `n_knots={int(params.get('n_knots'))}`"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- feasible_count: `{int(summary.get('feasible_count', 0))}`")
    lines.append(f"- infeasible_count: `{int(summary.get('infeasible_count', 0))}`")
    lines.append(
        f"- best_gap_metric_distance_mismatch: `{summary.get('best_gap_metric_distance_mismatch')}`"
    )
    lines.append(
        f"- any_physically_allowed_feasible: `{bool(summary.get('any_physically_allowed_feasible'))}`"
    )
    lines.append("")
    lines.append("## Gap table")
    lines.append("")
    lines.append("| lambda | drift-positive at all eval points? | physically allowed (`w>=-1`)? | distance mismatch RMS | min drift norm over eval points |")
    lines.append("|---:|---:|---:|---:|---:|")
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + f"{float(row.get('lambda')):.6g} | "
            + ("yes" if bool(row.get("feasible_drift_positive_all_eval")) else "no")
            + " | "
            + ("yes" if bool(row.get("physically_allowed_canonical")) else "no")
            + " | "
            + (f"{float(row.get('distance_mismatch_rms')):.12e}" if row.get("distance_mismatch_rms") is not None else "n/a")
            + " | "
            + (f"{float(row.get('min_drift_norm_eval')):.12e}" if row.get("min_drift_norm_eval") is not None else "n/a")
            + " |"
        )
    lines.append("")
    lines.append("## Reproduce")
    lines.append("```bash")
    lines.append(
        "python3 v11.0.0/scripts/phase4_sigmatensor_optimal_control_gap_diagnostic.py "
        "--outdir <outdir> --format text"
    )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _plot_if_requested(
    *,
    emit_plot: bool,
    outdir: Path,
    rows: Sequence[Mapping[str, Any]],
) -> Tuple[Optional[str], str]:
    if not emit_plot:
        return None, "disabled"

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None, "unavailable_matplotlib"

    if not rows:
        return None, "unavailable_no_rows"

    indices = sorted({0, len(rows) // 2, len(rows) - 1})
    selected = [rows[i] for i in indices]

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=120)
    z_ref = [2.0, 3.0, 4.0, 5.0]

    for row in selected:
        if not isinstance(row, Mapping):
            continue
        baseline = row.get("baseline_drift_eval") if isinstance(row.get("baseline_drift_eval"), list) else []
        solution = row.get("drift_eval") if isinstance(row.get("drift_eval"), list) else []

        base_map: Dict[str, float] = {
            _stable_key(float(r.get("z"))): float(r.get("dz_dt0_si"))
            for r in baseline
            if isinstance(r, Mapping)
        }
        sol_map: Dict[str, float] = {
            _stable_key(float(r.get("z"))): float(r.get("dz_dt0_si"))
            for r in solution
            if isinstance(r, Mapping)
        }
        y_base = [base_map.get(_stable_key(z), float("nan")) for z in z_ref]
        y_sol = [sol_map.get(_stable_key(z), float("nan")) for z in z_ref]

        lam = float(row.get("lambda", float("nan")))
        ax.plot(z_ref, y_base, linewidth=1.0, linestyle="--", alpha=0.55, label=f"baseline lambda={lam:.3g}")
        ax.plot(z_ref, y_sol, linewidth=1.8, alpha=0.95, label=f"deformed lambda={lam:.3g}")

    ax.axhline(0.0, color="black", linewidth=1.0)
    ax.set_xlabel("z")
    ax.set_ylabel("dz/dt0 [1/s]")
    ax.set_title("Optimal-control gap diagnostic (eval points)")
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.legend(frameon=False, fontsize=8, ncol=1)
    fig.tight_layout()

    plot_path = outdir / "GAP_DIAGNOSTIC.svg"
    fig.savefig(plot_path, format="svg", metadata={"Date": None})
    plt.close(fig)
    return plot_path.name, "ok"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Deterministic SigmaTensor no-go gap diagnostic: minimal distance mismatch needed "
            "to force positive drift over z in [2,5]."
        )
    )
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--format", choices=("json", "text"), default="text")
    ap.add_argument("--emit-plot", type=int, choices=(0, 1), default=0)
    ap.add_argument("--toy", type=int, choices=(0, 1), default=0)
    ap.add_argument(
        "--created-utc",
        type=int,
        default=DEFAULT_CREATED_UTC_EPOCH,
        help="UTC epoch-seconds marker for deterministic outputs (default: 946684800).",
    )

    # Baseline SigmaTensor parameters.
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--w0", type=float, default=-1.0)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)

    # Lambda grid.
    ap.add_argument("--lambda-min", dest="lambda_min", type=float, default=0.0)
    ap.add_argument("--lambda-max", dest="lambda_max", type=float, default=1.0)
    ap.add_argument("--n-lambda", dest="n_lambda", type=int, default=5)

    # z-grid and diagnostics points.
    ap.add_argument("--z-min", dest="z_min", type=float, default=0.0)
    ap.add_argument("--z-max", dest="z_max", type=float, default=5.0)
    ap.add_argument("--n-z", dest="n_z", type=int, default=301)
    ap.add_argument("--eval-z-csv", dest="eval_z_csv", default="2,3,4,5")
    ap.add_argument("--distance-z-csv", dest="distance_z_csv", default="0.5,1.0,2.0")

    # Control profile and optimization.
    ap.add_argument("--n-knots", dest="n_knots", type=int, default=5)
    ap.add_argument("--theta-max-abs", dest="theta_max_abs", type=float, default=0.8)
    ap.add_argument("--step-csv", dest="step_csv", default="0.25,0.15,0.08,0.04,0.02")
    ap.add_argument("--reg-l2", dest="reg_l2", type=float, default=1.0e-3)
    ap.add_argument("--reg-curvature", dest="reg_curvature", type=float, default=1.0e-2)
    ap.add_argument("--infeasible-penalty", dest="infeasible_penalty", type=float, default=1000.0)

    # Background solve resolution.
    ap.add_argument("--n-steps-bg", dest="n_steps_bg", type=int, default=1024)

    return ap.parse_args(argv)


def _apply_toy_overrides(args: argparse.Namespace) -> None:
    if int(args.toy) != 1:
        return
    args.n_lambda = min(int(args.n_lambda), 3)
    args.n_z = min(int(args.n_z), 121)
    args.n_steps_bg = min(int(args.n_steps_bg), 256)
    args.step_csv = "0.30,0.12,0.05"


def _validate_args(args: argparse.Namespace) -> Tuple[List[float], List[float], List[float], List[float], List[float]]:
    if not (math.isfinite(float(args.H0_km_s_Mpc)) and float(args.H0_km_s_Mpc) > 0.0):
        raise UsageError("--H0-km-s-Mpc must be finite and > 0")
    if not (math.isfinite(float(args.Omega_m)) and float(args.Omega_m) >= 0.0):
        raise UsageError("--Omega-m must be finite and >= 0")
    if not (math.isfinite(float(args.w0)) and -1.0 <= float(args.w0) < 1.0):
        raise UsageError("--w0 must be finite and in [-1,1)")

    if int(args.n_lambda) < 1:
        raise UsageError("--n-lambda must be >= 1")
    if float(args.lambda_max) < float(args.lambda_min):
        raise UsageError("--lambda-max must be >= --lambda-min")

    if int(args.n_z) < 5:
        raise UsageError("--n-z must be >= 5")
    if float(args.z_min) != 0.0:
        raise UsageError("--z-min must be 0.0 for distance integrals in this diagnostic")
    if float(args.z_max) < 5.0:
        raise UsageError("--z-max must be >= 5.0 to include required drift evaluation points")

    if int(args.n_knots) < 3 or int(args.n_knots) > 5:
        raise UsageError("--n-knots must be in [3,5]")
    if not (math.isfinite(float(args.theta_max_abs)) and float(args.theta_max_abs) > 0.0):
        raise UsageError("--theta-max-abs must be finite and > 0")
    if not (math.isfinite(float(args.reg_l2)) and float(args.reg_l2) >= 0.0):
        raise UsageError("--reg-l2 must be finite and >= 0")
    if not (math.isfinite(float(args.reg_curvature)) and float(args.reg_curvature) >= 0.0):
        raise UsageError("--reg-curvature must be finite and >= 0")
    if not (math.isfinite(float(args.infeasible_penalty)) and float(args.infeasible_penalty) > 0.0):
        raise UsageError("--infeasible-penalty must be finite and > 0")
    if int(args.n_steps_bg) < 16:
        raise UsageError("--n-steps-bg must be >= 16")

    lambda_values = _build_linear_grid(float(args.lambda_min), float(args.lambda_max), int(args.n_lambda))

    eval_z = _dedupe_sorted(list(REQUIRED_EVAL_Z) + _parse_csv_floats(args.eval_z_csv, name="--eval-z-csv"))
    distance_z = _dedupe_sorted(list(REQUIRED_DISTANCE_Z) + _parse_csv_floats(args.distance_z_csv, name="--distance-z-csv"))

    for z in eval_z:
        if not (float(args.z_min) <= float(z) <= float(args.z_max)):
            raise UsageError(f"evaluation z={z} lies outside [z-min, z-max]")
    for z in distance_z:
        if not (float(args.z_min) <= float(z) <= float(args.z_max)):
            raise UsageError(f"distance target z={z} lies outside [z-min, z-max]")

    z_grid = _dedupe_sorted(
        _build_linear_grid(float(args.z_min), float(args.z_max), int(args.n_z))
        + eval_z
        + distance_z
        + [0.0]
    )

    step_values = _parse_csv_floats(args.step_csv, name="--step-csv")
    step_values = [float(v) for v in step_values if float(v) > 0.0]
    if not step_values:
        raise UsageError("--step-csv must contain at least one positive value")

    return lambda_values, eval_z, distance_z, z_grid, step_values


def _gap_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    lines: List[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            ",".join(
                [
                    _fmt_e(float(row.get("lambda"))),
                    _fmt_e(float(row.get("distance_mismatch_rms"))) if row.get("distance_mismatch_rms") is not None else "nan",
                    _fmt_e(float(row.get("min_drift_norm_eval"))) if row.get("min_drift_norm_eval") is not None else "nan",
                    "1" if bool(row.get("feasible_drift_positive_all_eval")) else "0",
                    "1" if bool(row.get("physically_allowed_canonical")) else "0",
                ]
            )
        )
    blob = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        _apply_toy_overrides(args)
        created_utc = _to_iso_utc(int(args.created_utc))
        lambda_values, eval_z, distance_z, z_grid, step_values = _validate_args(args)

        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)

        H0_si = float(H0_to_SI(float(args.H0_km_s_Mpc)))
        knot_z = _knot_positions(float(args.z_min), float(args.z_max), int(args.n_knots))

        gap_rows: List[Dict[str, Any]] = []
        feasible_count = 0
        physical_ok_count = 0

        for lambda_value in lambda_values:
            st_params = SigmaTensorV1Params(
                H0_si=float(H0_si),
                Omega_m0=float(args.Omega_m),
                w_phi0=float(args.w0),
                lambda_=float(lambda_value),
                Tcmb_K=float(args.Tcmb_K),
                N_eff=float(args.N_eff),
                Omega_r0_override=(None if args.Omega_r0_override is None else float(args.Omega_r0_override)),
                sign_u0=int(args.sign_u0),
            )
            bg = solve_sigmatensor_v1_background(
                st_params,
                z_max=float(args.z_max),
                n_steps=int(args.n_steps_bg),
            )
            hist = SigmaTensorV1History(bg)

            H_baseline = [float(hist.H(float(z))) for z in z_grid]
            cumulative_baseline = _cumulative_trapz(z_grid, [1.0 / float(h) for h in H_baseline])
            baseline_distance_by_z = {
                float(z): float(_integral_to(float(z), z_grid, cumulative_baseline)) for z in distance_z
            }

            ctx = GapContext(
                z_grid=tuple(float(z) for z in z_grid),
                H_baseline=tuple(float(h) for h in H_baseline),
                H0_si=float(H0_si),
                Omega_m0=float(args.Omega_m),
                Omega_r0=float(bg.meta.get("Omega_r0")),
                eval_z=tuple(float(z) for z in eval_z),
                distance_z=tuple(float(z) for z in distance_z),
                baseline_distance_by_z=baseline_distance_by_z,
                knot_z=tuple(float(z) for z in knot_z),
                reg_l2=float(args.reg_l2),
                reg_curvature=float(args.reg_curvature),
                infeasible_penalty=float(args.infeasible_penalty),
            )

            best_feasible, best_any = _optimize_for_context(
                ctx=ctx,
                theta_max_abs=float(args.theta_max_abs),
                step_values=step_values,
                toy_mode=bool(int(args.toy)),
            )
            chosen = best_feasible if best_feasible is not None else best_any

            row = _candidate_to_payload(result=chosen, lambda_value=float(lambda_value), ctx=ctx)
            row["baseline_drift_eval"] = _baseline_eval_payload(eval_z=eval_z, history=hist, H0_si=float(H0_si))
            baseline_z3 = _drift_at_z(row["baseline_drift_eval"], 3.0)
            row["baseline_drift_at_z3_si"] = float(baseline_z3) if baseline_z3 is not None else None
            row["gap_metric_distance_mismatch"] = (
                float(chosen.distance_mismatch_rms) if bool(chosen.feasible) else None
            )
            row["optimization_status"] = "feasible" if bool(chosen.feasible) else "infeasible"

            if bool(chosen.feasible):
                feasible_count += 1
            if bool(chosen.physically_allowed_canonical):
                physical_ok_count += 1

            gap_rows.append(row)

        best_gap_rows = [
            row for row in gap_rows if isinstance(row.get("gap_metric_distance_mismatch"), (int, float))
        ]
        if best_gap_rows:
            best_row = min(
                best_gap_rows,
                key=lambda row: (
                    float(row.get("gap_metric_distance_mismatch")),
                    float(row.get("objective")),
                    float(row.get("lambda")),
                ),
            )
            best_gap_metric = float(best_row.get("gap_metric_distance_mismatch"))
            best_gap_lambda = float(best_row.get("lambda"))
        else:
            best_gap_metric = None
            best_gap_lambda = None

        summary = {
            "feasible_count": int(feasible_count),
            "infeasible_count": int(len(gap_rows) - feasible_count),
            "any_feasible": bool(feasible_count > 0),
            "any_physically_allowed_feasible": bool(
                any(bool(row.get("feasible_drift_positive_all_eval")) and bool(row.get("physically_allowed_canonical")) for row in gap_rows)
            ),
            "best_gap_metric_distance_mismatch": best_gap_metric,
            "best_gap_lambda": best_gap_lambda,
            "drift_positive_anywhere_in_2_5": bool(
                any(bool(row.get("feasible_drift_positive_all_eval")) for row in gap_rows)
            ),
            "drift_positive_all_eval_points_for_all_lambda": bool(
                len(gap_rows) > 0 and all(bool(row.get("feasible_drift_positive_all_eval")) for row in gap_rows)
            ),
        }

        plot_relpath, plot_status = _plot_if_requested(
            emit_plot=bool(int(args.emit_plot)),
            outdir=outdir,
            rows=gap_rows,
        )

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "created_utc": created_utc,
            "created_utc_epoch": int(args.created_utc),
            "python_version": sys.version.split(" ")[0],
            "platform": platform.platform(),
            "repo_version_dir": "v11.0.0",
            "paths_redacted": True,
            "status": "ok",
            "params": {
                "H0_km_s_Mpc": float(args.H0_km_s_Mpc),
                "H0_si": float(H0_si),
                "Omega_m0": float(args.Omega_m),
                "w_phi0": float(args.w0),
                "Tcmb_K": float(args.Tcmb_K),
                "N_eff": float(args.N_eff),
                "Omega_r0_override": (None if args.Omega_r0_override is None else float(args.Omega_r0_override)),
                "sign_u0": int(args.sign_u0),
                "lambda_min": float(args.lambda_min),
                "lambda_max": float(args.lambda_max),
                "n_lambda": int(args.n_lambda),
                "z_min": float(args.z_min),
                "z_max": float(args.z_max),
                "n_z": int(args.n_z),
                "eval_z_values": [float(v) for v in eval_z],
                "distance_z_values": [float(v) for v in distance_z],
                "n_knots": int(args.n_knots),
                "theta_max_abs": float(args.theta_max_abs),
                "reg_l2": float(args.reg_l2),
                "reg_curvature": float(args.reg_curvature),
                "infeasible_penalty": float(args.infeasible_penalty),
                "step_values": [float(v) for v in step_values],
                "toy_mode": bool(int(args.toy)),
                "n_steps_bg": int(args.n_steps_bg),
            },
            "grids": {
                "lambda_values": [float(v) for v in lambda_values],
                "z_values": [float(v) for v in z_grid],
                "eval_z_values": [float(v) for v in eval_z],
                "distance_z_values": [float(v) for v in distance_z],
                "knot_z_values": [float(v) for v in knot_z],
            },
            "summary": summary,
            "gap_by_lambda": gap_rows,
            "artifacts": {
                "json": "GAP_DIAGNOSTIC.json",
                "text": "GAP_DIAGNOSTIC.txt",
                "plot": plot_relpath,
                "plot_status": plot_status,
            },
            "digests": {
                "gap_table_sha256": _gap_digest(gap_rows),
            },
        }

        json_path = outdir / "GAP_DIAGNOSTIC.json"
        txt_path = outdir / "GAP_DIAGNOSTIC.txt"

        json_path.write_text(_json_pretty(payload), encoding="utf-8")
        txt_path.write_text(_render_markdown(payload), encoding="utf-8")

        if str(args.format) == "json":
            print(_json_pretty(payload), end="")
        else:
            print(_render_text(payload), end="")

        return 0
    except UsageError as exc:
        print(f"ERROR: {exc}")
        return 1
    except DiagnosticError as exc:
        print(f"{FAIL_MARKER}: {exc}")
        return 2
    except Exception as exc:
        print(f"{FAIL_MARKER}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
