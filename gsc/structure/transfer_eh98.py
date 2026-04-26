"""EH98 no-wiggle transfer-function approximation (stdlib-only).

This module implements an approximation-first Eisenstein & Hu (1998)
no-wiggle transfer function for diagnostic structure-formation calculations.
It is not a Boltzmann hierarchy solver.
"""

from __future__ import annotations

import math

from ..early_time.rd import compute_rd_Mpc, omega_r_h2


_C_KM_S = 299_792.458


def _finite(value: float, *, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def transfer_eh98_nowiggle(
    k_Mpc_inv: float,
    *,
    omega_b_h2: float,
    omega_c_h2: float,
    h: float,
    Tcmb_K: float = 2.7255,
    N_eff: float = 3.046,
) -> float:
    """Return EH98 no-wiggle transfer ``T(k)`` for ``k`` in 1/Mpc.

    The implementation follows the smooth no-wiggle form with baryon
    suppression through an effective ``Gamma`` factor. This is a deterministic
    diagnostic approximation and not a precision Boltzmann transfer.
    """
    k = _finite(float(k_Mpc_inv), name="k_Mpc_inv")
    if k < 0.0:
        raise ValueError("k_Mpc_inv must be >= 0")
    if k == 0.0:
        return 1.0

    wb = _finite(float(omega_b_h2), name="omega_b_h2")
    wc = _finite(float(omega_c_h2), name="omega_c_h2")
    hh = _finite(float(h), name="h")
    tcmb = _finite(float(Tcmb_K), name="Tcmb_K")
    neff = _finite(float(N_eff), name="N_eff")

    if wb < 0.0:
        raise ValueError("omega_b_h2 must be >= 0")
    if wc < 0.0:
        raise ValueError("omega_c_h2 must be >= 0")
    if not (hh > 0.0):
        raise ValueError("h must be > 0")
    if not (tcmb > 0.0):
        raise ValueError("Tcmb_K must be > 0")
    if neff < 0.0:
        raise ValueError("N_eff must be >= 0")

    omega_m_h2 = wb + wc
    if not (omega_m_h2 > 0.0):
        raise ValueError("omega_m_h2 must be > 0")

    fb = wb / omega_m_h2
    omega_r = omega_r_h2(Tcmb_K=tcmb, N_eff=neff)
    if not (omega_r > 0.0 and math.isfinite(omega_r)):
        raise ValueError("computed omega_r_h2 must be finite and > 0")

    # Matter-radiation equality scale in 1/Mpc.
    k_eq = (100.0 / _C_KM_S) * math.sqrt(2.0) * omega_m_h2 / math.sqrt(omega_r)
    if not (k_eq > 0.0 and math.isfinite(k_eq)):
        raise ValueError("computed k_eq is non-physical")

    q_base = k / (13.41 * k_eq)
    if q_base <= 1.0e-16:
        return 1.0

    # EH98 drag horizon scale (Mpc) from the same early-time helper as r_d.
    s_mpc = compute_rd_Mpc(
        omega_b_h2=wb,
        omega_c_h2=wc,
        N_eff=neff,
        Tcmb_K=tcmb,
    )
    if not (s_mpc > 0.0 and math.isfinite(s_mpc)):
        raise ValueError("computed drag horizon is non-physical")

    ln_arg_1 = 431.0 * omega_m_h2
    ln_arg_2 = 22.3 * omega_m_h2
    if not (ln_arg_1 > 0.0 and ln_arg_2 > 0.0):
        raise ValueError("invalid logarithm argument in alpha_Gamma")

    alpha_gamma = (
        1.0
        - 0.328 * math.log(ln_arg_1) * fb
        + 0.38 * math.log(ln_arg_2) * (fb**2.0)
    )
    if not math.isfinite(alpha_gamma):
        raise ValueError("non-finite alpha_Gamma")

    # Smooth baryon suppression transition.
    f_gamma = alpha_gamma + (1.0 - alpha_gamma) / (1.0 + (0.43 * k * s_mpc) ** 4.0)
    if not (math.isfinite(f_gamma) and f_gamma > 0.0):
        raise ValueError("non-finite/invalid f_Gamma")

    q = q_base / f_gamma
    if q <= 1.0e-16:
        return 1.0

    l0 = math.log(math.e + 1.8 * q)
    c0 = 14.2 + 731.0 / (1.0 + 62.5 * q)
    denom = l0 + c0 * (q**2.0)
    if not (math.isfinite(denom) and denom > 0.0):
        raise ValueError("invalid denominator in EH98 transfer")

    t_k = l0 / denom
    if not (math.isfinite(t_k) and t_k > 0.0):
        raise ValueError("non-finite EH98 no-wiggle transfer value")
    return float(t_k)

