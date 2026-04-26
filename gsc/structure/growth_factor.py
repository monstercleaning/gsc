"""Linear-growth bridge diagnostics (GR baseline, background-driven).

This module provides a deterministic approximation-first growth solver in
``x = ln(a)`` and helper observables. It is intended for diagnostic reporting
and not as a full perturbation/Boltzmann solver.
"""

from __future__ import annotations

from bisect import bisect_right
import math
from typing import Callable, Dict, Iterable, List, Sequence, Tuple


def _finite_positive(value: float, *, name: str) -> float:
    out = float(value)
    if not (math.isfinite(out) and out > 0.0):
        raise ValueError(f"{name} must be finite and > 0")
    return out


def _validate_z_targets(z_targets: Iterable[float]) -> List[float]:
    out = [float(z) for z in z_targets]
    if not out:
        raise ValueError("z_targets must contain at least one value")
    for z in out:
        if not (math.isfinite(z) and z >= 0.0):
            raise ValueError("z_targets must contain finite z >= 0")
    return out


def _dlnE_dx_numeric(
    x: float,
    *,
    E_of_z: Callable[[float], float],
    eps_dlnH: float,
) -> float:
    eps = float(eps_dlnH)
    if not (math.isfinite(eps) and eps > 0.0):
        raise ValueError("eps_dlnH must be finite and > 0")

    x_plus = float(x) + eps
    x_minus = float(x) - eps
    z_plus = math.exp(-x_plus) - 1.0
    z_minus = math.exp(-x_minus) - 1.0

    e_plus = _finite_positive(float(E_of_z(z_plus)), name="E(z+eps)")
    e_minus = _finite_positive(float(E_of_z(z_minus)), name="E(z-eps)")
    return float((math.log(e_plus) - math.log(e_minus)) / (2.0 * eps))


def _rk4_step_ln_a(
    x: float,
    D: float,
    V: float,
    *,
    h: float,
    E_of_z: Callable[[float], float],
    omega_m0: float,
    eps_dlnH: float,
) -> Tuple[float, float]:
    def rhs(xx: float, DD: float, VV: float) -> Tuple[float, float]:
        z = math.exp(-xx) - 1.0
        e_val = _finite_positive(float(E_of_z(z)), name="E(z)")
        dlnHdx = _dlnE_dx_numeric(xx, E_of_z=E_of_z, eps_dlnH=eps_dlnH)
        a = math.exp(xx)
        omega_m_a = float(omega_m0) * (a**-3.0) / (e_val * e_val)
        if not math.isfinite(omega_m_a):
            raise ValueError("non-finite Omega_m(a)")

        dD = VV
        dV = -((2.0 + dlnHdx) * VV) + 1.5 * omega_m_a * DD
        return float(dD), float(dV)

    k1_D, k1_V = rhs(x, D, V)
    k2_D, k2_V = rhs(x + 0.5 * h, D + 0.5 * h * k1_D, V + 0.5 * h * k1_V)
    k3_D, k3_V = rhs(x + 0.5 * h, D + 0.5 * h * k2_D, V + 0.5 * h * k2_V)
    k4_D, k4_V = rhs(x + h, D + h * k3_D, V + h * k3_V)

    D_next = D + (h / 6.0) * (k1_D + 2.0 * k2_D + 2.0 * k3_D + k4_D)
    V_next = V + (h / 6.0) * (k1_V + 2.0 * k2_V + 2.0 * k3_V + k4_V)
    return float(D_next), float(V_next)


def _interp_linear(x_grid: Sequence[float], y_grid: Sequence[float], xq: float) -> float:
    if xq <= x_grid[0]:
        return float(y_grid[0])
    if xq >= x_grid[-1]:
        return float(y_grid[-1])
    idx = bisect_right(x_grid, xq)
    i0 = int(idx - 1)
    i1 = int(idx)
    x0 = float(x_grid[i0])
    x1 = float(x_grid[i1])
    y0 = float(y_grid[i0])
    y1 = float(y_grid[i1])
    if x1 == x0:
        return y0
    t = (float(xq) - x0) / (x1 - x0)
    return float(y0 + t * (y1 - y0))


def solve_growth_ln_a(
    E_of_z: Callable[[float], float],
    omega_m0: float,
    *,
    z_start: float,
    z_targets: Iterable[float],
    n_steps: int = 4000,
    eps_dlnH: float = 1.0e-5,
) -> Dict[str, object]:
    """Solve GR linear growth in ln(a) for diagnostic use.

    Equation:
      D'' + (2 + dlnH/dx) D' - (3/2) Omega_m(a) D = 0
      x = ln(a), a = exp(x), z = 1/a - 1

    Initial conditions at high-z matter-dominated start:
      D(x_start) = a_start
      D'(x_start) = D(x_start)

    Returned grids are normalized so that D(z=0)=1.
    """
    om0 = float(omega_m0)
    if not (0.0 < om0 <= 1.5):
        raise ValueError("omega_m0 must satisfy 0 < omega_m0 <= 1.5")

    z0 = float(z_start)
    if not (math.isfinite(z0) and z0 > 0.0):
        raise ValueError("z_start must be finite and > 0")

    z_targets_list = _validate_z_targets(z_targets)
    if max(z_targets_list) >= z0:
        raise ValueError("z_start must be strictly greater than all z_targets")

    n_steps_i = int(n_steps)
    if n_steps_i < 16:
        raise ValueError("n_steps must be >= 16")

    eps = float(eps_dlnH)
    if not (math.isfinite(eps) and eps > 0.0):
        raise ValueError("eps_dlnH must be finite and > 0")

    # Force early validation at z=0.
    _finite_positive(float(E_of_z(0.0)), name="E(0)")

    x_start = -math.log1p(z0)
    x_end = 0.0
    h = (x_end - x_start) / float(n_steps_i)
    if not (h > 0.0 and math.isfinite(h)):
        raise ValueError("invalid integration step")

    a_start = math.exp(x_start)
    D = float(a_start)
    V = float(D)

    x_grid: List[float] = [float(x_start)]
    D_grid: List[float] = [float(D)]
    V_grid: List[float] = [float(V)]

    x = float(x_start)
    for _ in range(n_steps_i):
        D, V = _rk4_step_ln_a(
            x,
            D,
            V,
            h=h,
            E_of_z=E_of_z,
            omega_m0=om0,
            eps_dlnH=eps,
        )
        x = float(x + h)
        x_grid.append(float(x))
        D_grid.append(float(D))
        V_grid.append(float(V))

    D0 = float(D_grid[-1])
    if not (math.isfinite(D0) and D0 > 0.0):
        raise ValueError("non-finite or non-positive D(z=0)")

    D_norm = [float(v / D0) for v in D_grid]
    V_norm = [float(v / D0) for v in V_grid]

    for idx, val in enumerate(D_norm):
        if not (math.isfinite(val) and val > 0.0):
            raise ValueError(f"non-finite/non-positive D at index {idx}")
    for i in range(len(D_norm) - 1):
        if D_norm[i + 1] + 1.0e-9 < D_norm[i]:
            raise ValueError("growth solution failed monotonicity sanity check")

    return {
        "method": "rk4_ln_a_v2",
        "omega_m0": float(om0),
        "z_start": float(z0),
        "n_steps": int(n_steps_i),
        "eps_dlnH": float(eps),
        "x_grid": x_grid,
        "D_grid": D_norm,
        "D_prime_grid": V_norm,
    }


def growth_observables_from_solution(sol: Dict[str, object], z_targets: Iterable[float]) -> Dict[str, List[float]]:
    """Return D(z), f(z) and g(z)=fD from a growth solution.

    This helper is deterministic and preserves the input order of ``z_targets``.
    """
    x_grid = [float(v) for v in sol.get("x_grid", [])]
    D_grid = [float(v) for v in sol.get("D_grid", [])]
    V_grid = [float(v) for v in sol.get("D_prime_grid", [])]
    if not x_grid or len(x_grid) != len(D_grid) or len(D_grid) != len(V_grid):
        raise ValueError("invalid growth solution grid payload")

    z_in = _validate_z_targets(z_targets)
    out_D: List[float] = []
    out_f: List[float] = []
    out_g: List[float] = []
    for z in z_in:
        xq = -math.log1p(float(z))
        d_val = _interp_linear(x_grid, D_grid, xq)
        v_val = _interp_linear(x_grid, V_grid, xq)
        if not (math.isfinite(d_val) and d_val > 0.0 and math.isfinite(v_val)):
            raise ValueError("non-finite growth observable")
        f_val = float(v_val / d_val)
        g_val = float(f_val * d_val)
        out_D.append(float(d_val))
        out_f.append(float(f_val))
        out_g.append(float(g_val))

    return {"z": [float(z) for z in z_in], "D": out_D, "f": out_f, "g": out_g}


def solve_growth_D_f(
    z_eval: Iterable[float],
    *,
    H_of_z: Callable[[float], float],
    Omega_m0: float,
    z_init: float = 100.0,
    n_steps: int = 4000,
) -> Dict[str, object]:
    """Backward-compatible growth wrapper returning deterministic D(z), f(z)."""
    z_targets = _validate_z_targets(z_eval)
    H0 = _finite_positive(float(H_of_z(0.0)), name="H0")

    def E_of_z(z: float) -> float:
        Hz = _finite_positive(float(H_of_z(float(z))), name="H(z)")
        return float(Hz / H0)

    sol = solve_growth_ln_a(
        E_of_z,
        float(Omega_m0),
        z_start=float(z_init),
        z_targets=z_targets,
        n_steps=int(n_steps),
        eps_dlnH=1.0e-5,
    )
    obs = growth_observables_from_solution(sol, z_targets)
    return {
        "method": "rk4_ln_a_v1",
        "Omega_m0": float(Omega_m0),
        "H0": float(H0),
        "z_init": float(z_init),
        "n_steps": int(n_steps),
        "z": [float(z) for z in obs["z"]],
        "D": [float(v) for v in obs["D"]],
        "f": [float(v) for v in obs["f"]],
    }


def fsigma8_from_D_f(
    z_eval: Iterable[float],
    D_eval: Iterable[float],
    f_eval: Iterable[float],
    sigma8_0: float,
) -> List[float]:
    """Return fσ8(z) = f(z) * D(z) * sigma8_0 for aligned iterables."""
    s8 = float(sigma8_0)
    if not (math.isfinite(s8) and s8 > 0.0):
        raise ValueError("sigma8_0 must be finite and > 0")

    z_list = [float(z) for z in z_eval]
    d_list = [float(d) for d in D_eval]
    f_list = [float(f) for f in f_eval]
    if not (len(z_list) == len(d_list) == len(f_list)):
        raise ValueError("z_eval, D_eval and f_eval must have the same length")

    out: List[float] = []
    for z, dval, fval in zip(z_list, d_list, f_list):
        if not (math.isfinite(z) and z >= 0.0):
            raise ValueError("z values must be finite and >= 0")
        if not (math.isfinite(dval) and math.isfinite(fval)):
            raise ValueError("D and f values must be finite")
        out.append(float(fval * dval * s8))
    return out
