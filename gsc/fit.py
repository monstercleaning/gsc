"""Late-time fitting helpers (v11.0.0).

Scope:
- deterministic grid search (no MCMC)
- analytic profiling of nuisance parameters is delegated to dataset blocks
  (SN: delta_M, BAO: r_d), but this module provides utility scaffolding for
  reproducible best-fit runs and outputs.

This is intentionally lightweight and avoids pulling in heavy frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Sequence, Tuple

from .datasets.base import HzModel
from .datasets.drift import DriftDataset
from .measurement_model import H0_to_SI, MPC_SI, delta_v_cm_s


@dataclass(frozen=True)
class FitPoint:
    params: Dict[str, float]
    chi2: float
    ndof: int
    parts: Dict[str, Any]


def iter_param_grid(grid: Mapping[str, Sequence[float]]) -> Iterator[Dict[str, float]]:
    """Yield parameter dictionaries for a cartesian product grid.

    The iteration order is deterministic: keys are iterated in sorted order.
    """
    keys = sorted(grid.keys())
    if not keys:
        yield {}
        return

    def rec(i: int, acc: Dict[str, float]) -> Iterator[Dict[str, float]]:
        if i >= len(keys):
            yield dict(acc)
            return
        k = keys[i]
        vals = grid[k]
        for v in vals:
            acc[k] = float(v)
            yield from rec(i + 1, acc)
        acc.pop(k, None)

    yield from rec(0, {})


def grid_search(
    *,
    grid: Mapping[str, Sequence[float]],
    score: Callable[[Dict[str, float]], FitPoint],
    top_k: int = 1,
) -> Tuple[FitPoint, List[FitPoint]]:
    """Run a deterministic grid search and return (best, top_k_sorted)."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    best: FitPoint | None = None
    top: List[FitPoint] = []

    for params in iter_param_grid(grid):
        fp = score(params)

        if best is None or fp.chi2 < best.chi2:
            best = fp

        # Keep a small sorted top-K list (stable, O(K) per insert).
        inserted = False
        for i, existing in enumerate(top):
            if fp.chi2 < existing.chi2:
                top.insert(i, fp)
                inserted = True
                break
        if not inserted:
            top.append(fp)
        if len(top) > top_k:
            top = top[:top_k]

    if best is None:
        raise ValueError("Empty grid search (no points evaluated)")
    return best, top


def parse_grid_spec(spec: str) -> List[float]:
    """Parse a simple grid spec.

    Supported:
    - comma list: "0.3,0.31,0.32"
    - range: "start:stop:step" (inclusive of stop within float tolerance)
    """
    s = spec.strip()
    if not s:
        raise ValueError("empty grid spec")

    if ":" in s:
        parts = [p.strip() for p in s.split(":")]
        if len(parts) != 3:
            raise ValueError("range grid spec must be 'start:stop:step'")
        start, stop, step = (float(parts[0]), float(parts[1]), float(parts[2]))
        if step <= 0:
            raise ValueError("step must be positive")
        vals: List[float] = []
        v = start
        # Use a tolerance to include the endpoint.
        tol = 1e-12 * max(1.0, abs(stop))
        while v <= stop + tol:
            vals.append(float(v))
            v += step
        if not vals:
            raise ValueError("empty range after parsing")
        return vals

    # Comma list.
    out: List[float] = []
    for tok in s.split(","):
        t = tok.strip()
        if not t:
            continue
        out.append(float(t))
    if not out:
        raise ValueError("empty comma grid spec")
    return out


def profile_H0_from_drift(
    *,
    drift: DriftDataset,
    model_ref: HzModel,
    H0_bounds_km_s_Mpc: Tuple[float, float] | None = None,
) -> Dict[str, Any]:
    """Profile H0 analytically from a drift dataset.

    Assumption (true for our v11.0.0 histories): H(z) is linear in H0, so
    Δv(z) is linear in H0 for fixed shape parameters.

    Returns a dict with:
    - H0_km_s_Mpc (best-fit within bounds if provided)
    - chi2 (evaluated at the returned H0)
    - ndof (N-1, since H0 is fitted)
    - clamped (bool)
    """
    if len(drift.z) == 0:
        raise ValueError("Empty drift dataset")
    if not (len(drift.z) == len(drift.dv_cm_s) == len(drift.sigma_dv_cm_s)):
        raise ValueError("z/dv/sigma length mismatch")

    H0_ref_si = float(model_ref.H(0.0))
    if not (H0_ref_si > 0 and math.isfinite(H0_ref_si)):
        raise ValueError("model_ref.H(0) must be positive and finite")

    num = 0.0
    den = 0.0
    rows: List[Tuple[float, float, float]] = []  # (dv_obs, w, f)

    for i, (z, dv_obs, sig) in enumerate(zip(drift.z, drift.dv_cm_s, drift.sigma_dv_cm_s)):
        if sig <= 0:
            raise ValueError("sigma_dv_cm_s must be positive")
        years = drift.baseline_years_by_row[i] if drift.baseline_years_by_row is not None else drift.baseline_years
        if years <= 0:
            raise ValueError("baseline_years must be positive")

        # Compute the linear "shape factor" f_i such that dv = H0 * f_i.
        dv_ref = delta_v_cm_s(z=float(z), years=float(years), H0=H0_ref_si, H_of_z=model_ref.H)
        f_i = float(dv_ref) / H0_ref_si  # units: cm
        w_i = 1.0 / (float(sig) ** 2)

        rows.append((float(dv_obs), float(w_i), float(f_i)))
        num += w_i * float(dv_obs) * f_i
        den += w_i * f_i * f_i

    if not (den > 0 and math.isfinite(den) and math.isfinite(num)):
        raise ValueError("Invalid drift profiling denominator")

    H0_hat_si = num / den
    if not math.isfinite(H0_hat_si):
        raise ValueError("Profiled H0 is non-finite")

    clamped = False
    if H0_bounds_km_s_Mpc is not None:
        lo_km_s_Mpc, hi_km_s_Mpc = (float(H0_bounds_km_s_Mpc[0]), float(H0_bounds_km_s_Mpc[1]))
        if not (lo_km_s_Mpc > 0 and hi_km_s_Mpc > 0 and lo_km_s_Mpc <= hi_km_s_Mpc):
            raise ValueError("Invalid H0_bounds_km_s_Mpc (require 0 < lo <= hi)")
        lo_si = H0_to_SI(lo_km_s_Mpc)
        hi_si = H0_to_SI(hi_km_s_Mpc)
        if H0_hat_si < lo_si:
            H0_hat_si = lo_si
            clamped = True
        if H0_hat_si > hi_si:
            H0_hat_si = hi_si
            clamped = True

    if not (H0_hat_si > 0 and math.isfinite(H0_hat_si)):
        raise ValueError("Profiled H0 must be positive")

    chi2 = 0.0
    for dv_obs, w_i, f_i in rows:
        r = dv_obs - H0_hat_si * f_i
        chi2 += w_i * r * r

    H0_hat_km_s_Mpc = float(H0_hat_si * float(MPC_SI) / 1000.0)
    ndof = max(0, int(len(drift.z) - 1))
    out: Dict[str, Any] = {
        "chi2": float(chi2),
        "ndof": int(ndof),
        "H0_km_s_Mpc": float(H0_hat_km_s_Mpc),
        "clamped": bool(clamped),
    }
    if H0_bounds_km_s_Mpc is not None:
        out["H0_bounds_km_s_Mpc"] = [float(H0_bounds_km_s_Mpc[0]), float(H0_bounds_km_s_Mpc[1])]
    return out
