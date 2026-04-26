"""BBKS transfer-function approximation for structure diagnostics.

This module is intentionally approximation-first and stdlib-only. It is a
compact bridge utility for Phase-2 diagnostics and is not a Boltzmann solver.
"""

from __future__ import annotations

import math
from typing import Iterable, List


def shape_parameter_sugiyama(Omega_m0: float, Omega_b0: float, h: float) -> float:
    """Return the Sugiyama baryon-corrected shape parameter Γ_eff.

    Γ_eff = Ω_m h * exp[-Ω_b * (1 + sqrt(2h)/Ω_m)]

    Inputs use fractional density parameters (Ω values, not ω=Ωh²).
    """
    om = float(Omega_m0)
    ob = float(Omega_b0)
    hh = float(h)

    if not (om > 0.0):
        raise ValueError("Omega_m0 must be > 0")
    if not (0.0 <= ob <= om):
        raise ValueError("Omega_b0 must satisfy 0 <= Omega_b0 <= Omega_m0")
    if not (0.0 < hh <= 2.0):
        raise ValueError("h must satisfy 0 < h <= 2")

    exponent = -ob * (1.0 + math.sqrt(2.0 * hh) / om)
    gamma_eff = om * hh * math.exp(exponent)
    if not (math.isfinite(gamma_eff) and gamma_eff > 0.0):
        raise ValueError("non-finite/invalid Sugiyama shape parameter")
    return float(gamma_eff)


def transfer_bbks(
    k_Mpc: float,
    *,
    Omega_m0: float,
    Omega_b0: float,
    h: float,
    Tcmb_K: float = 2.7255,
) -> float:
    """Return scalar BBKS transfer T(k) for k in 1/Mpc.

    Conventions:
    - input k_Mpc is in 1/Mpc (not h/Mpc)
    - q = (k_Mpc / (Gamma_eff * h)) * (Tcmb_K / 2.7)^2

    T(k) is an approximation for rough structure-formation diagnostics and is
    not a replacement for full Boltzmann transfer calculations.
    """
    k = float(k_Mpc)
    if k < 0.0:
        raise ValueError("k_Mpc must be >= 0")
    if not (Tcmb_K > 0.0):
        raise ValueError("Tcmb_K must be > 0")

    gamma_eff = shape_parameter_sugiyama(Omega_m0=Omega_m0, Omega_b0=Omega_b0, h=h)

    if k == 0.0:
        return 1.0

    theta = float(Tcmb_K) / 2.7
    denom = float(gamma_eff) * float(h)
    if not (denom > 0.0 and math.isfinite(denom)):
        raise ValueError("invalid denominator in BBKS q definition")

    q = (k / denom) * (theta * theta)
    if q <= 1.0e-14:
        return 1.0

    a = 2.34 * q
    log_term = math.log(1.0 + a) / a
    poly = 1.0 + 3.89 * q + (16.1 * q) ** 2 + (5.46 * q) ** 3 + (6.71 * q) ** 4
    T = log_term * (poly ** (-0.25))

    if not (math.isfinite(T) and T > 0.0):
        raise ValueError("non-finite BBKS transfer value")
    return float(T)


def transfer_bbks_many(
    k_values_Mpc: Iterable[float],
    *,
    Omega_m0: float,
    Omega_b0: float,
    h: float,
    Tcmb_K: float = 2.7255,
) -> List[float]:
    """Vector helper for BBKS transfer values."""
    return [
        transfer_bbks(
            float(k),
            Omega_m0=Omega_m0,
            Omega_b0=Omega_b0,
            h=h,
            Tcmb_K=Tcmb_K,
        )
        for k in k_values_Mpc
    ]


def sample_k_grid(*, kmin: float, kmax: float, n: int) -> List[float]:
    """Return deterministic log-spaced k-grid in 1/Mpc."""
    k_lo = float(kmin)
    k_hi = float(kmax)
    nn = int(n)

    if not (k_lo > 0.0 and k_hi > 0.0):
        raise ValueError("kmin and kmax must be positive")
    if not (k_hi >= k_lo):
        raise ValueError("kmax must be >= kmin")
    if nn < 2:
        raise ValueError("n must be >= 2")

    if k_hi == k_lo:
        return [float(k_lo) for _ in range(nn)]

    log_lo = math.log(k_lo)
    log_hi = math.log(k_hi)
    step = (log_hi - log_lo) / float(nn - 1)
    return [float(math.exp(log_lo + float(i) * step)) for i in range(nn)]
