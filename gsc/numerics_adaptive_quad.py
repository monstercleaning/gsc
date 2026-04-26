"""Deterministic stdlib adaptive quadrature helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable


def _require_finite(name: str, value: float) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _simpson(fa: float, fm: float, fb: float, a: float, b: float) -> float:
    return (b - a) * (fa + 4.0 * fm + fb) / 6.0


@dataclass(frozen=True)
class AdaptiveQuadResult:
    value: float
    abs_err_est: float
    n_eval: int
    method: str
    rtol: float
    atol: float


def adaptive_simpson_with_meta(
    f: Callable[[float], float],
    a: float,
    b: float,
    *,
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    max_depth: int = 20,
    method: str = "adaptive_simpson",
) -> AdaptiveQuadResult:
    """Integrate `f` over [a,b] with adaptive Simpson recursion and metadata."""
    a_f = _require_finite("a", a)
    b_f = _require_finite("b", b)
    eps_abs_f = _require_finite("eps_abs", eps_abs)
    eps_rel_f = _require_finite("eps_rel", eps_rel)
    if eps_abs_f <= 0.0 or eps_rel_f <= 0.0:
        raise ValueError("eps_abs and eps_rel must be > 0")
    depth = int(max_depth)
    if depth < 0:
        raise ValueError("max_depth must be >= 0")
    if a_f == b_f:
        return AdaptiveQuadResult(
            value=0.0,
            abs_err_est=0.0,
            n_eval=0,
            method=str(method),
            rtol=float(eps_rel_f),
            atol=float(eps_abs_f),
        )

    eval_count = 0
    err_accum = 0.0

    def eval_f(x: float) -> float:
        nonlocal eval_count
        y = float(f(float(x)))
        if not math.isfinite(y):
            raise ValueError(f"integrand returned non-finite value at x={x!r}")
        eval_count += 1
        return y

    fa = eval_f(a_f)
    fb = eval_f(b_f)
    m = 0.5 * (a_f + b_f)
    fm = eval_f(m)
    whole = _simpson(fa, fm, fb, a_f, b_f)

    def recurse(left: float, right: float, fl: float, fm_: float, fr: float, s_whole: float, d: int) -> float:
        nonlocal err_accum
        mid = 0.5 * (left + right)
        lmid = 0.5 * (left + mid)
        rmid = 0.5 * (mid + right)

        flm = eval_f(lmid)
        frm = eval_f(rmid)

        s_left = _simpson(fl, flm, fm_, left, mid)
        s_right = _simpson(fm_, frm, fr, mid, right)
        s_split = s_left + s_right

        tol = max(eps_abs_f, eps_rel_f * abs(s_split))
        err = abs(s_split - s_whole) / 15.0
        if err <= tol:
            err_accum += float(err)
            return s_split + (s_split - s_whole) / 15.0
        if d <= 0:
            raise RuntimeError("adaptive_simpson exceeded max_depth before reaching tolerance")
        return recurse(left, mid, fl, flm, fm_, s_left, d - 1) + recurse(mid, right, fm_, frm, fr, s_right, d - 1)

    value = float(recurse(a_f, b_f, fa, fm, fb, whole, depth))
    return AdaptiveQuadResult(
        value=float(value),
        abs_err_est=float(abs(err_accum)),
        n_eval=int(eval_count),
        method=str(method),
        rtol=float(eps_rel_f),
        atol=float(eps_abs_f),
    )


def adaptive_simpson(
    f: Callable[[float], float],
    a: float,
    b: float,
    *,
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    max_depth: int = 20,
) -> float:
    """Integrate `f` over [a,b] with adaptive Simpson recursion."""
    return float(
        adaptive_simpson_with_meta(
            f,
            a,
            b,
            eps_abs=float(eps_abs),
            eps_rel=float(eps_rel),
            max_depth=int(max_depth),
            method="adaptive_simpson",
        ).value
    )


def adaptive_simpson_log1p_z_with_meta(
    fz: Callable[[float], float],
    z0: float,
    z1: float,
    *,
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    max_depth: int = 20,
) -> AdaptiveQuadResult:
    """Integrate `fz(z) dz` using `u=ln(1+z)` with adaptive Simpson + metadata."""
    z0_f = _require_finite("z0", z0)
    z1_f = _require_finite("z1", z1)
    if z0_f <= -1.0 or z1_f <= -1.0:
        raise ValueError("z0 and z1 must be > -1")
    if z1_f < z0_f:
        raise ValueError("z1 must be >= z0")
    if z0_f == z1_f:
        return AdaptiveQuadResult(
            value=0.0,
            abs_err_est=0.0,
            n_eval=0,
            method="adaptive_simpson_log1p_z",
            rtol=float(eps_rel),
            atol=float(eps_abs),
        )

    u0 = math.log1p(z0_f)
    u1 = math.log1p(z1_f)

    def fu(u: float) -> float:
        one_plus_z = math.exp(float(u))
        z = one_plus_z - 1.0
        return float(fz(float(z))) * one_plus_z

    return adaptive_simpson_with_meta(
        fu,
        u0,
        u1,
        eps_abs=float(eps_abs),
        eps_rel=float(eps_rel),
        max_depth=int(max_depth),
        method="adaptive_simpson_log1p_z",
    )


def adaptive_simpson_log1p_z(
    fz: Callable[[float], float],
    z0: float,
    z1: float,
    *,
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    max_depth: int = 20,
) -> float:
    """Integrate `fz(z) dz` using `u=ln(1+z)` with adaptive Simpson."""
    return float(
        adaptive_simpson_log1p_z_with_meta(
            fz,
            z0,
            z1,
            eps_abs=float(eps_abs),
            eps_rel=float(eps_rel),
            max_depth=int(max_depth),
        ).value
    )


__all__ = [
    "AdaptiveQuadResult",
    "adaptive_simpson",
    "adaptive_simpson_with_meta",
    "adaptive_simpson_log1p_z",
    "adaptive_simpson_log1p_z_with_meta",
]
