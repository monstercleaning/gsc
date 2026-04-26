"""Deterministic stdlib local optimization helpers."""

from __future__ import annotations

import math
from typing import Callable, List, Mapping, Optional, Sequence, Tuple


_INF = float("inf")


def project_to_bounds(
    x: Sequence[float],
    bounds: Optional[Sequence[Tuple[float, float]]] = None,
) -> List[float]:
    """Project a point onto box bounds with deterministic clamping."""
    vals = [float(v) for v in x]
    if bounds is None:
        return vals
    if len(bounds) != len(vals):
        raise ValueError("bounds length must match x length")
    out: List[float] = []
    for i, (vv, raw_b) in enumerate(zip(vals, bounds)):
        if not isinstance(raw_b, tuple) and not isinstance(raw_b, list):
            raise ValueError(f"bounds[{i}] must be (lo, hi)")
        if len(raw_b) != 2:
            raise ValueError(f"bounds[{i}] must have exactly two entries")
        lo = float(raw_b[0])
        hi = float(raw_b[1])
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError(f"bounds[{i}] must be finite")
        if hi < lo:
            raise ValueError(f"bounds[{i}] invalid range: hi < lo")
        if vv < lo:
            vv = lo
        elif vv > hi:
            vv = hi
        out.append(float(vv))
    return out


def _safe_eval(f: Callable[[List[float]], float], x: Sequence[float]) -> float:
    try:
        value = float(f([float(v) for v in x]))
    except Exception:
        return _INF
    if not math.isfinite(value):
        return _INF
    return float(value)


def _sort_key(item: Tuple[float, List[float]]) -> Tuple[float, Tuple[float, ...]]:
    f_val, x = item
    return float(f_val), tuple(float(v) for v in x)


def _max_f_delta(simplex: Sequence[Tuple[float, List[float]]]) -> float:
    if not simplex:
        return _INF
    best = float(simplex[0][0])
    if not math.isfinite(best):
        return _INF
    out = 0.0
    for f_val, _ in simplex:
        ff = float(f_val)
        if not math.isfinite(ff):
            return _INF
        out = max(out, abs(ff - best))
    return float(out)


def _max_x_delta(simplex: Sequence[Tuple[float, List[float]]]) -> float:
    if not simplex:
        return _INF
    best = simplex[0][1]
    out = 0.0
    for _, point in simplex:
        if len(point) != len(best):
            return _INF
        out = max(
            out,
            max(abs(float(a) - float(b)) for a, b in zip(point, best)),
        )
    return float(out)


def _default_step(
    x0: Sequence[float],
    bounds: Optional[Sequence[Tuple[float, float]]],
) -> List[float]:
    if bounds is not None:
        out: List[float] = []
        for lo, hi in bounds:
            span = float(hi) - float(lo)
            if span > 0.0:
                out.append(0.05 * span)
            else:
                out.append(0.0)
        return out
    out = []
    for value in x0:
        vv = abs(float(value))
        out.append(0.05 * vv if vv > 0.0 else 1e-3)
    return out


def nelder_mead_minimize(
    f: Callable[[List[float]], float],
    x0: Sequence[float],
    *,
    bounds: Optional[Sequence[Tuple[float, float]]] = None,
    step: Optional[Sequence[float]] = None,
    max_eval: int = 200,
    tol_f: float = 1e-9,
    tol_x: float = 1e-9,
    alpha: float = 1.0,
    gamma: float = 2.0,
    rho: float = 0.5,
    sigma: float = 0.5,
) -> Mapping[str, object]:
    """Deterministic Nelder-Mead minimizer (stdlib only).

    Non-finite objective values and evaluation errors are treated as +inf.
    """
    x0_list = [float(v) for v in x0]
    if not x0_list and len(x0) == 0:
        x0_projected: List[float] = []
    else:
        x0_projected = project_to_bounds(x0_list, bounds=bounds)
    n_dim = len(x0_projected)

    if max_eval <= 0:
        raise ValueError("max_eval must be > 0")
    if tol_f < 0.0 or tol_x < 0.0:
        raise ValueError("tol_f and tol_x must be >= 0")

    step_vals = [float(v) for v in (_default_step(x0_projected, bounds) if step is None else step)]
    if len(step_vals) != n_dim:
        raise ValueError("step length must match x0 length")
    for value in step_vals:
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("step entries must be finite and >= 0")

    if n_dim == 0:
        f0 = _safe_eval(f, [])
        return {
            "x_best": [],
            "f_best": float(f0),
            "n_eval": 1,
            "converged": True,
            "stop_reason": "tol_x",
        }

    simplex: List[List[float]] = [list(x0_projected)]
    for i in range(n_dim):
        pt = list(x0_projected)
        delta = float(step_vals[i])
        if delta != 0.0:
            pt[i] = float(pt[i] + delta)
        pt = project_to_bounds(pt, bounds=bounds)
        if pt == x0_projected and delta != 0.0:
            alt = list(x0_projected)
            alt[i] = float(alt[i] - delta)
            alt = project_to_bounds(alt, bounds=bounds)
            if alt != x0_projected:
                pt = alt
        simplex.append(pt)

    simplex_fx: List[Tuple[float, List[float]]] = []
    n_eval = 0
    for point in simplex:
        if n_eval >= int(max_eval):
            break
        simplex_fx.append((_safe_eval(f, point), list(point)))
        n_eval += 1

    converged = False
    stop_reason = "max_eval"
    while simplex_fx:
        simplex_fx.sort(key=_sort_key)
        if _max_f_delta(simplex_fx) < float(tol_f):
            converged = True
            stop_reason = "tol_f"
            break
        if _max_x_delta(simplex_fx) < float(tol_x):
            converged = True
            stop_reason = "tol_x"
            break
        if n_eval >= int(max_eval):
            converged = False
            stop_reason = "max_eval"
            break

        best = simplex_fx[0]
        worst = simplex_fx[-1]
        second_worst = simplex_fx[-2] if len(simplex_fx) >= 2 else simplex_fx[-1]

        centroid = [0.0 for _ in range(n_dim)]
        for _, point in simplex_fx[:-1]:
            for i, value in enumerate(point):
                centroid[i] += float(value)
        denom = float(max(len(simplex_fx) - 1, 1))
        centroid = [v / denom for v in centroid]

        # Reflection
        x_reflect = [centroid[i] + float(alpha) * (centroid[i] - float(worst[1][i])) for i in range(n_dim)]
        x_reflect = project_to_bounds(x_reflect, bounds=bounds)
        if n_eval >= int(max_eval):
            break
        f_reflect = _safe_eval(f, x_reflect)
        n_eval += 1

        if f_reflect < float(best[0]):
            # Expansion
            x_expand = [centroid[i] + float(gamma) * (float(x_reflect[i]) - centroid[i]) for i in range(n_dim)]
            x_expand = project_to_bounds(x_expand, bounds=bounds)
            if n_eval >= int(max_eval):
                simplex_fx[-1] = (float(f_reflect), list(x_reflect))
                continue
            f_expand = _safe_eval(f, x_expand)
            n_eval += 1
            if f_expand < f_reflect:
                simplex_fx[-1] = (float(f_expand), list(x_expand))
            else:
                simplex_fx[-1] = (float(f_reflect), list(x_reflect))
            continue

        if f_reflect < float(second_worst[0]):
            simplex_fx[-1] = (float(f_reflect), list(x_reflect))
            continue

        # Contraction
        if f_reflect < float(worst[0]):
            # Outside contraction.
            x_contract = [centroid[i] + float(rho) * (float(x_reflect[i]) - centroid[i]) for i in range(n_dim)]
            target_cmp = float(f_reflect)
        else:
            # Inside contraction.
            x_contract = [centroid[i] + float(rho) * (float(worst[1][i]) - centroid[i]) for i in range(n_dim)]
            target_cmp = float(worst[0])
        x_contract = project_to_bounds(x_contract, bounds=bounds)
        if n_eval >= int(max_eval):
            break
        f_contract = _safe_eval(f, x_contract)
        n_eval += 1
        if f_contract <= target_cmp:
            simplex_fx[-1] = (float(f_contract), list(x_contract))
            continue

        # Shrink
        x_best = list(best[1])
        shrunk: List[Tuple[float, List[float]]] = [best]
        exhausted = False
        for _, point in simplex_fx[1:]:
            x_new = [float(x_best[i]) + float(sigma) * (float(point[i]) - float(x_best[i])) for i in range(n_dim)]
            x_new = project_to_bounds(x_new, bounds=bounds)
            if n_eval >= int(max_eval):
                exhausted = True
                break
            f_new = _safe_eval(f, x_new)
            n_eval += 1
            shrunk.append((float(f_new), list(x_new)))
        simplex_fx = shrunk
        if exhausted:
            break

    simplex_fx.sort(key=_sort_key)
    if not simplex_fx:
        return {
            "x_best": list(x0_projected),
            "f_best": float(_INF),
            "n_eval": int(n_eval),
            "converged": False,
            "stop_reason": "max_eval",
        }
    return {
        "x_best": [float(v) for v in simplex_fx[0][1]],
        "f_best": float(simplex_fx[0][0]),
        "n_eval": int(n_eval),
        "converged": bool(converged),
        "stop_reason": str(stop_reason),
    }


__all__ = ["nelder_mead_minimize", "project_to_bounds"]
