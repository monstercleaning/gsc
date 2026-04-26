"""GW standard-sirens diagnostic helpers (pipeline-unused).

This module provides a minimal, *diagnostic-only* translation layer for a common
modified GW propagation parameterization.

It supports two (diagnostic) modes:

1) Phenomenological (Xi0, n) parameterization:

  Xi(z) = Xi0 + (1 - Xi0) / (1+z)^n
  d_L^GW(z) = Xi(z) * d_L^EM(z)

2) Modified-propagation interface (friction / Planck-mass running):

  d_L^GW(z) / d_L^EM(z) = exp( ∫_0^z [delta(z')/(1+z')] dz' )

The sign convention varies in the literature depending on how ``delta(z)`` is
defined. In this codebase, we adopt the **plus-sign** convention above so that
constant ``delta`` yields an analytic check:

  delta(z)=delta0 (const)  =>  d_L^GW/d_L^EM = (1+z)^delta0

We also include a toy mapping in terms of a constant Planck-mass running
parameter ``alpha_M`` (often used in EFT formulations):

  d_L^GW/d_L^EM = exp( 1/2 ∫_0^z [alpha_M(z')/(1+z')] dz' )

These helpers are not used by the v11.0.0 late-time fit/paper pipeline.
"""

from __future__ import annotations

import math
from typing import Callable


def _integrate_trapezoid(f: Callable[[float], float], a: float, b: float, *, n: int = 10_000) -> float:
    if n <= 0:
        raise ValueError("n must be > 0")
    if b < a:
        raise ValueError("Require b >= a")
    if a == b:
        return 0.0
    h = (b - a) / n
    s = 0.5 * (float(f(a)) + float(f(b)))
    for i in range(1, n):
        s += float(f(a + i * h))
    return s * h


def Xi_of_z(z: float, *, Xi0: float, n: float) -> float:
    """Return the phenomenological GW/EM distance ratio Xi(z).

    Definition (widely used in standard-siren MG parameterizations):

      Xi(z) = Xi0 + (1 - Xi0) / (1+z)^n
      d_L^GW(z) = Xi(z) * d_L^EM(z)

    Properties:
    - Xi(0) = 1 exactly
    - For n>0, Xi(z) approaches Xi0 monotonically as z increases.
    """
    if not (z >= 0.0 and math.isfinite(z)):
        raise ValueError("z must be finite and >= 0")
    if not (Xi0 > 0.0 and math.isfinite(Xi0)):
        raise ValueError("Xi0 must be finite and > 0")
    if not (n >= 0.0 and math.isfinite(n)):
        raise ValueError("n must be finite and >= 0")
    one_p_z = 1.0 + float(z)
    Xi = float(Xi0) + (1.0 - float(Xi0)) / (one_p_z**float(n))
    if not (Xi > 0.0 and math.isfinite(Xi)):
        raise ValueError("Non-finite or non-positive Xi(z)")
    return float(Xi)


def gw_distance_ratio_xi0_n(z: float, *, Xi0: float, n: float) -> float:
    """Convenience wrapper: return d_L^GW/d_L^EM for the (Xi0, n) parameterization."""
    return Xi_of_z(float(z), Xi0=float(Xi0), n=float(n))


def gw_distance_ratio(
    z: float,
    *,
    delta_of_z: Callable[[float], float] | None = None,
    alphaM_of_z: Callable[[float], float] | None = None,
    n: int = 10_000,
) -> float:
    """Return the modified-propagation ratio d_L^GW(z) / d_L^EM(z).

    Parameters
    ----------
    z : float
        Redshift (must be >= 0).
    delta_of_z : callable, optional
        Friction modification function delta(z) (dimensionless).
    alphaM_of_z : callable, optional
        Effective Planck-mass running alpha_M(z) (dimensionless). If provided,
        uses the common mapping ``ratio = exp(1/2 ∫ alpha_M/(1+z) dz)``.
    n : int
        Integration resolution for the z-integral.
    """
    if not (z >= 0.0 and math.isfinite(z)):
        raise ValueError("z must be finite and >= 0")
    if delta_of_z is not None and alphaM_of_z is not None:
        raise ValueError("Provide at most one of delta_of_z or alphaM_of_z")
    if delta_of_z is None and alphaM_of_z is None:
        return 1.0

    def integrand(zz: float) -> float:
        if delta_of_z is not None:
            return float(delta_of_z(float(zz))) / (1.0 + float(zz))
        assert alphaM_of_z is not None
        return 0.5 * float(alphaM_of_z(float(zz))) / (1.0 + float(zz))

    I = _integrate_trapezoid(integrand, 0.0, float(z), n=int(n))
    r = math.exp(float(I))
    if not math.isfinite(r):
        raise ValueError("Non-finite GW/EM ratio")
    return float(r)


def gw_ratio_from_Mstar(z: float, Mstar_of_z: Callable[[float], float]) -> float:
    """Return the common mapping d_L^GW/d_L^EM = M_*(0)/M_*(z).

    This helper is intended for conceptual diagnostics only (when the mapping applies).
    """
    if not (z >= 0.0 and math.isfinite(z)):
        raise ValueError("z must be finite and >= 0")
    M0 = float(Mstar_of_z(0.0))
    Mz = float(Mstar_of_z(float(z)))
    if not (M0 > 0.0 and Mz > 0.0 and math.isfinite(M0) and math.isfinite(Mz)):
        raise ValueError("Mstar must be finite and > 0")
    return float(M0 / Mz)
