"""Diagnostic-only recombination helpers (E2.*).

This module intentionally provides a *minimal* Peebles-style 3-level atom
recombination approximation to support "definition audit" diagnostics.

Guardrails:
- Not used by the canonical late-time pipeline.
- Not a substitute for Recfast/HyRec; do not treat outputs as precision results.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from ..measurement_model import C_SI, MPC_SI


def _H_lcdm_rad_si(*, z: float, H0_si: float, Omega_m: float, Omega_r: float, Omega_Lambda: float) -> float:
    one_p = 1.0 + float(z)
    Ez2 = float(Omega_r) * one_p**4 + float(Omega_m) * one_p**3 + float(Omega_Lambda)
    if not (Ez2 > 0.0 and math.isfinite(Ez2)):
        raise ValueError("Non-physical E(z)^2")
    return float(H0_si) * math.sqrt(Ez2)


def _alpha_B_hui_gnedin_m3_s(T_K: float) -> float:
    """Case-B recombination coefficient alpha_B(T) in m^3/s (Hui & Gnedin 1997 fit)."""
    if not (T_K > 0.0 and math.isfinite(T_K)):
        raise ValueError("T_K must be finite and > 0")
    T4 = float(T_K) / 1.0e4
    # Original fit often quoted in cm^3/s; convert to m^3/s.
    alpha_cm3_s = 4.309e-13 * (T4 ** -0.6166) / (1.0 + 0.6703 * (T4**0.5300))
    alpha_m3_s = float(alpha_cm3_s) * 1.0e-6
    if not (alpha_m3_s > 0.0 and math.isfinite(alpha_m3_s)):
        raise ValueError("alpha_B is non-physical")
    return float(alpha_m3_s)


def _beta_B_from_alpha(*, alpha_m3_s: float, T_K: float) -> float:
    """Photoionization rate beta_B(T) from detailed balance (approx; hydrogen-only)."""
    # Constants (SI).
    k_B = 1.380649e-23
    h_P = 6.62607015e-34
    m_e = 9.1093837015e-31
    eV = 1.602176634e-19
    chi_2 = 3.4 * eV  # ionization energy from n=2

    T = float(T_K)
    if not (T > 0.0 and math.isfinite(T)):
        raise ValueError("T_K must be finite and > 0")
    if not (alpha_m3_s > 0.0 and math.isfinite(alpha_m3_s)):
        raise ValueError("alpha_m3_s must be finite and > 0")

    pref = (2.0 * math.pi * m_e * k_B * T) / (h_P * h_P)
    saha = (pref ** 1.5) * math.exp(-chi_2 / (k_B * T))
    beta = float(alpha_m3_s) * float(saha)
    if not (beta >= 0.0 and math.isfinite(beta)):
        raise ValueError("beta_B is non-physical")
    return float(beta)


def _n_H_m3(
    *,
    z: float,
    H0_si: float,
    omega_b_h2: float,
    Yp: float,
) -> float:
    """Hydrogen number density n_H(z) in 1/m^3 (hydrogen-only; helium treated via Yp)."""
    if not (z >= 0.0 and math.isfinite(z)):
        raise ValueError("z must be finite and >= 0")
    if not (omega_b_h2 > 0.0 and math.isfinite(omega_b_h2)):
        raise ValueError("omega_b_h2 must be finite and > 0")
    if not (0.0 <= float(Yp) < 1.0 and math.isfinite(Yp)):
        raise ValueError("Yp must be finite and in [0,1)")

    # Critical density today.
    G = 6.67430e-11
    rho_crit0 = 3.0 * float(H0_si) * float(H0_si) / (8.0 * math.pi * G)

    # Omega_b from omega_b_h2 and little-h inferred from H0.
    H0_km_s_Mpc = float(H0_si) * float(MPC_SI) / 1000.0
    h = float(H0_km_s_Mpc) / 100.0
    Omega_b = float(omega_b_h2) / (h * h)

    m_p = 1.67262192369e-27
    n_b0 = float(Omega_b) * float(rho_crit0) / float(m_p)
    n_H0 = (1.0 - float(Yp)) * float(n_b0)
    return float(n_H0) * (1.0 + float(z)) ** 3


def z_star_peebles_approx(
    *,
    H0_si: float,
    Omega_m: float,
    Omega_r: float,
    Omega_Lambda: float,
    omega_b_h2: float,
    Tcmb_K: float,
    Yp: float,
    z_max: float = 3000.0,
    z_min_ode: float = 200.0,
    n_grid: int = 8192,
    method: str = "fixed_rk4_u",
    rtol: float = 1e-6,
    atol: float = 1e-10,
) -> Tuple[float, Dict[str, float]]:
    """Return (z_star, info) from a minimal Peebles-style recombination + visibility peak.

    Notes:
    - Hydrogen-only (helium only via Yp in n_H).
    - Uses T(z)=Tcmb*(1+z) and assumes T_matter ~ T_radiation in recombination epoch.
    - This is *not* a substitute for Recfast/HyRec; it is a diagnostic sensitivity check.
    """
    import numpy as np

    if not (z_max > z_min_ode > 0):
        raise ValueError("Require z_max > z_min_ode > 0")
    if n_grid < 1024:
        raise ValueError("grid too small")

    if str(method) not in ("fixed_rk4_u", "fixed_rk4"):
        raise ValueError("Only method='fixed_rk4_u' is supported in this diagnostic implementation")

    # z-grid for tau/visibility (increasing).
    zz = np.linspace(0.0, float(z_max), int(n_grid), dtype=float)

    # Deterministic fixed-step RK4 integration in u=ln(1+z), from z=z_max down to z=z_min_ode.
    u0 = math.log1p(float(z_max))
    u1 = math.log1p(float(z_min_ode))
    n_ode = int(min(16384, max(2048, int(n_grid))))
    uu = np.linspace(float(u0), float(u1), int(n_ode), dtype=float)
    du = float(uu[1] - uu[0])
    if not (du < 0.0):
        raise ValueError("internal error: expected decreasing u grid")

    # Constants (SI).
    sigma_T = 6.6524587321e-29
    lam_alpha = 1.21567e-7
    Lambda_2s1s = 8.22458

    def dx_du(u: float, x: float) -> float:
        # u = ln(1+z)
        one_p = float(math.exp(float(u)))
        z = float(one_p) - 1.0
        x = min(1.0 - 1e-12, max(1e-12, float(x)))

        T = float(Tcmb_K) * float(one_p)
        alpha = _alpha_B_hui_gnedin_m3_s(float(T))
        beta = _beta_B_from_alpha(alpha_m3_s=float(alpha), T_K=float(T))

        nH = _n_H_m3(z=float(z), H0_si=float(H0_si), omega_b_h2=float(omega_b_h2), Yp=float(Yp))
        Hz = _H_lcdm_rad_si(z=float(z), H0_si=float(H0_si), Omega_m=float(Omega_m), Omega_r=float(Omega_r), Omega_Lambda=float(Omega_Lambda))
        K = (lam_alpha**3) / (8.0 * math.pi * float(Hz))
        C = (1.0 + K * Lambda_2s1s * nH * (1.0 - x)) / (1.0 + K * (Lambda_2s1s + beta) * nH * (1.0 - x))

        # Suppress photoionization by the Boltzmann factor for the n=2 population
        # (Peebles 3-level atom approximation; diagnostic-only).
        k_B = 1.380649e-23
        eV = 1.602176634e-19
        hnu_alpha = 10.2 * eV
        boltz = math.exp(-float(hnu_alpha) / (float(k_B) * float(T)))

        # Since dz/du = (1+z), we have dx/du = (1+z) * dx/dz = (C/H) * (...)
        ion = float(beta) * (1.0 - float(x)) * float(boltz)
        rec = float(nH) * float(alpha) * float(x) * float(x)
        return float(C / float(Hz)) * (float(rec) - float(ion))

    x_eval = np.empty_like(uu, dtype=float)
    x = 1.0 - 1e-8
    x_eval[0] = float(x)
    for i in range(1, int(uu.size)):
        u_prev = float(uu[i - 1])
        k1 = dx_du(float(u_prev), float(x))
        k2 = dx_du(float(u_prev + 0.5 * du), float(x + 0.5 * du * k1))
        k3 = dx_du(float(u_prev + 0.5 * du), float(x + 0.5 * du * k2))
        k4 = dx_du(float(u_prev + du), float(x + du * k3))
        x = float(x + (du / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4))
        if not math.isfinite(x):
            x = 1e-8
        x = min(1.0 - 1e-8, max(1e-8, float(x)))
        x_eval[i] = float(x)
    # Build x_e over the full zz grid.
    x_e = np.empty_like(zz, dtype=float)
    # Constant below z_min_ode; the toy model is not designed for late-time ionization history.
    x_low = float(max(1e-8, min(1.0, float(x_eval[-1]))))
    x_e[:] = float(x_low)

    # Interpolate the solution onto the analysis grid for z >= z_min_ode.
    z_eval = np.asarray(np.exp(uu) - 1.0, dtype=float)  # decreasing
    z_inc = np.asarray(z_eval[::-1], dtype=float)
    x_inc = np.asarray(x_eval[::-1], dtype=float)
    mask_hi = zz >= float(z_min_ode)
    x_e[mask_hi] = np.interp(zz[mask_hi], z_inc, x_inc)
    x_e = np.clip(x_e, 1e-8, 1.0)

    # Optical depth tau(z) and visibility g(z).
    Hz = np.asarray(
        [_H_lcdm_rad_si(z=float(z), H0_si=float(H0_si), Omega_m=float(Omega_m), Omega_r=float(Omega_r), Omega_Lambda=float(Omega_Lambda)) for z in zz],
        dtype=float,
    )
    nH = np.asarray(
        [_n_H_m3(z=float(z), H0_si=float(H0_si), omega_b_h2=float(omega_b_h2), Yp=float(Yp)) for z in zz],
        dtype=float,
    )
    ne = x_e * nH
    dtaudz = float(C_SI) * float(sigma_T) * ne / ((1.0 + zz) * Hz)
    if not (np.isfinite(dtaudz).all() and float(np.min(dtaudz)) >= 0.0):
        raise ValueError("Non-physical dtaudz")

    dz = float(zz[1] - zz[0])
    tau = np.concatenate(([0.0], np.cumsum(0.5 * (dtaudz[1:] + dtaudz[:-1]) * dz)))
    g = np.exp(-tau) * dtaudz
    i_max = int(np.argmax(g))
    z_star = float(zz[i_max])
    if not (z_star > 0.0 and math.isfinite(z_star)):
        raise ValueError("Computed z_star is non-physical")

    info = {
        "x_e_at_z_star": float(x_e[i_max]),
        "tau_at_z_star": float(tau[i_max]),
        "g_max": float(g[i_max]),
    }
    return (float(z_star), info)
