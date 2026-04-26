"""Diagnostic recombination/drag method plumbing for early-time bridge paths.

This module provides lightweight method switches for z_* / z_drag evaluation.
It is intended for robustness diagnostics, not precision CMB microphysics claims.
"""

from __future__ import annotations

import bisect
import math
from typing import Any, Dict, Mapping, Tuple

from ..measurement_model import C_SI, MPC_SI
from ..numerics_adaptive_quad import adaptive_simpson_log1p_z_with_meta
from .rd import omega_gamma_h2_from_Tcmb, z_drag_eisenstein_hu


def _require_finite(name: str, value: float) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _z_star_hu_sugiyama_fit(*, omega_b_h2: float, omega_m_h2: float) -> float:
    if not (omega_b_h2 > 0.0 and math.isfinite(omega_b_h2)):
        raise ValueError("omega_b_h2 must be finite and > 0")
    if not (omega_m_h2 > 0.0 and math.isfinite(omega_m_h2)):
        raise ValueError("omega_m_h2 must be finite and > 0")
    g1 = (0.0783 * (omega_b_h2 ** -0.238)) / (1.0 + 39.5 * (omega_b_h2 ** 0.763))
    g2 = 0.560 / (1.0 + 21.1 * (omega_b_h2 ** 1.81))
    z_star = 1048.0 * (1.0 + 0.00124 * (omega_b_h2 ** -0.738)) * (1.0 + g1 * (omega_m_h2 ** g2))
    if not (z_star > 0.0 and math.isfinite(z_star)):
        raise ValueError("computed z_star is non-physical")
    return float(z_star)


def _h_lcdm_rad_si(*, z: float, H0_si: float, Omega_m: float, Omega_r: float, Omega_lambda: float) -> float:
    one_p = 1.0 + float(z)
    ez2 = float(Omega_r) * one_p**4 + float(Omega_m) * one_p**3 + float(Omega_lambda)
    if not (ez2 > 0.0 and math.isfinite(ez2)):
        raise ValueError("non-physical E(z)^2")
    return float(H0_si) * math.sqrt(ez2)


def _alpha_b_caseb_m3_s(t_k: float) -> float:
    if not (t_k > 0.0 and math.isfinite(t_k)):
        raise ValueError("T_K must be finite and > 0")
    t4 = float(t_k) / 1.0e4
    alpha_cm3_s = 4.309e-13 * (t4 ** -0.6166) / (1.0 + 0.6703 * (t4**0.53))
    alpha_m3_s = float(alpha_cm3_s) * 1.0e-6
    if not (alpha_m3_s > 0.0 and math.isfinite(alpha_m3_s)):
        raise ValueError("alpha_B is non-physical")
    return float(alpha_m3_s)


def _beta_b_from_alpha(*, alpha_m3_s: float, t_k: float) -> float:
    k_b = 1.380649e-23
    h_p = 6.62607015e-34
    m_e = 9.1093837015e-31
    e_v = 1.602176634e-19
    chi_2 = 3.4 * e_v

    t = float(t_k)
    if not (t > 0.0 and math.isfinite(t)):
        raise ValueError("T_K must be finite and > 0")
    if not (alpha_m3_s > 0.0 and math.isfinite(alpha_m3_s)):
        raise ValueError("alpha_m3_s must be finite and > 0")

    pref = (2.0 * math.pi * m_e * k_b * t) / (h_p * h_p)
    saha = (pref ** 1.5) * math.exp(-chi_2 / (k_b * t))
    beta = float(alpha_m3_s) * float(saha)
    if not (beta >= 0.0 and math.isfinite(beta)):
        raise ValueError("beta_B is non-physical")
    return float(beta)


def _n_h_m3(*, z: float, H0_si: float, omega_b_h2: float, y_p: float) -> float:
    if not (z >= 0.0 and math.isfinite(z)):
        raise ValueError("z must be finite and >= 0")
    if not (omega_b_h2 > 0.0 and math.isfinite(omega_b_h2)):
        raise ValueError("omega_b_h2 must be finite and > 0")
    if not (0.0 <= float(y_p) < 1.0 and math.isfinite(y_p)):
        raise ValueError("Y_p must be finite and in [0,1)")

    g_newton = 6.67430e-11
    rho_crit0 = 3.0 * float(H0_si) * float(H0_si) / (8.0 * math.pi * g_newton)

    h0_km_s_mpc = float(H0_si) * float(MPC_SI) / 1000.0
    h = float(h0_km_s_mpc) / 100.0
    omega_b = float(omega_b_h2) / (h * h)

    m_p = 1.67262192369e-27
    n_b0 = float(omega_b) * float(rho_crit0) / float(m_p)
    n_h0 = (1.0 - float(y_p)) * float(n_b0)
    return float(n_h0) * (1.0 + float(z)) ** 3


def _rk4_step(dx_du, u: float, x: float, h: float) -> float:
    k1 = dx_du(float(u), float(x))
    k2 = dx_du(float(u + 0.5 * h), float(x + 0.5 * h * k1))
    k3 = dx_du(float(u + 0.5 * h), float(x + 0.5 * h * k2))
    k4 = dx_du(float(u + h), float(x + h * k3))
    x_new = float(x + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4))
    if not math.isfinite(x_new):
        return float("nan")
    return x_new


def _z_star_peebles3(
    *,
    H0_si: float,
    Omega_m: float,
    Omega_r: float,
    Omega_lambda: float,
    omega_b_h2: float,
    Tcmb_K: float,
    Y_p: float,
    z_max: float,
    z_min_ode: float,
    max_steps: int,
    rtol: float,
    atol: float,
) -> Tuple[float, Dict[str, Any]]:
    if not (z_max > z_min_ode > 0.0):
        raise ValueError("require z_max > z_min_ode > 0")
    if int(max_steps) <= 0:
        raise ValueError("max_steps must be > 0")
    if not (float(rtol) > 0.0 and math.isfinite(float(rtol))):
        raise ValueError("rtol must be finite and > 0")
    if not (float(atol) > 0.0 and math.isfinite(float(atol))):
        raise ValueError("atol must be finite and > 0")

    sigma_t = 6.6524587321e-29
    lam_alpha = 1.21567e-7
    lambda_2s1s = 8.22458

    u_hi = math.log1p(float(z_max))
    u_lo = math.log1p(float(z_min_ode))

    def dx_du(u: float, x: float) -> float:
        one_p = math.exp(float(u))
        z = one_p - 1.0
        x_clamped = min(1.0 - 1e-12, max(1e-12, float(x)))

        t_k = float(Tcmb_K) * one_p
        alpha = _alpha_b_caseb_m3_s(float(t_k))
        beta = _beta_b_from_alpha(alpha_m3_s=float(alpha), t_k=float(t_k))

        n_h = _n_h_m3(z=float(z), H0_si=float(H0_si), omega_b_h2=float(omega_b_h2), y_p=float(Y_p))
        h_z = _h_lcdm_rad_si(
            z=float(z),
            H0_si=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_r=float(Omega_r),
            Omega_lambda=float(Omega_lambda),
        )
        k_fac = (lam_alpha**3) / (8.0 * math.pi * float(h_z))
        c_fac = (1.0 + k_fac * lambda_2s1s * n_h * (1.0 - x_clamped)) / (
            1.0 + k_fac * (lambda_2s1s + beta) * n_h * (1.0 - x_clamped)
        )

        k_b = 1.380649e-23
        e_v = 1.602176634e-19
        hnu_alpha = 10.2 * e_v
        boltz = math.exp(-float(hnu_alpha) / (float(k_b) * float(t_k)))

        ion = float(beta) * (1.0 - x_clamped) * float(boltz)
        rec = float(n_h) * float(alpha) * x_clamped * x_clamped
        return float(c_fac / float(h_z)) * (float(rec) - float(ion))

    accepted_u: list[float] = [float(u_hi)]
    accepted_x: list[float] = [1.0 - 1e-8]
    u = float(u_hi)
    x = 1.0 - 1e-8
    h = -abs((u_hi - u_lo) / max(64.0, min(float(max_steps), 1024.0)))
    steps_accepted = 0
    steps_attempted = 0
    converged = False

    while steps_attempted < int(max_steps):
        if u <= u_lo:
            converged = True
            break
        if u + h < u_lo:
            h = u_lo - u
        steps_attempted += 1

        x_full = _rk4_step(dx_du, u, x, h)
        x_half = _rk4_step(dx_du, u, x, 0.5 * h)
        if math.isfinite(x_half):
            x_half = _rk4_step(dx_du, u + 0.5 * h, x_half, 0.5 * h)

        if not (math.isfinite(x_full) and math.isfinite(x_half)):
            h *= 0.5
            if abs(h) < 1e-12:
                break
            continue

        err = abs(float(x_half) - float(x_full))
        tol = float(atol) + float(rtol) * max(abs(float(x)), abs(float(x_half)))
        if err <= tol or abs(h) <= 1e-12:
            u = float(u + h)
            x = min(1.0 - 1e-8, max(1e-8, float(x_half)))
            accepted_u.append(float(u))
            accepted_x.append(float(x))
            steps_accepted += 1
            if err <= 0.0:
                growth = 2.0
            else:
                growth = min(2.0, max(1.05, 0.9 * (tol / err) ** 0.2))
            h *= growth
        else:
            shrink = max(0.1, min(0.9, 0.9 * (tol / max(err, 1e-30)) ** 0.25))
            h *= shrink

    if not converged and u <= u_lo:
        converged = True

    # Visibility grid in z (increasing).
    n_vis = int(max(512, min(max_steps, 4096)))
    dz = float(z_max) / float(n_vis - 1)
    z_grid = [float(i) * dz for i in range(n_vis)]

    # Interpolate x_e(z) from accepted nodes for z >= z_min_ode.
    z_nodes_desc = [math.exp(float(val)) - 1.0 for val in accepted_u]
    z_nodes = list(reversed(z_nodes_desc))
    x_nodes = list(reversed(accepted_x))
    x_low = float(max(1e-8, min(1.0, x_nodes[0])))

    def x_of_z(z: float) -> float:
        zz = float(z)
        if zz <= float(z_min_ode):
            return float(x_low)
        if zz >= float(z_nodes[-1]):
            return float(x_nodes[-1])
        idx = bisect.bisect_left(z_nodes, zz)
        if idx <= 0:
            return float(x_nodes[0])
        if idx >= len(z_nodes):
            return float(x_nodes[-1])
        z0 = float(z_nodes[idx - 1])
        z1 = float(z_nodes[idx])
        x0 = float(x_nodes[idx - 1])
        x1 = float(x_nodes[idx])
        if z1 <= z0:
            return float(x0)
        t = (zz - z0) / (z1 - z0)
        return float(x0 + t * (x1 - x0))

    dtaudz: list[float] = []
    x_vis: list[float] = []

    for z in z_grid:
        x_e = float(x_of_z(float(z)))
        x_vis.append(float(x_e))
        n_h = _n_h_m3(z=float(z), H0_si=float(H0_si), omega_b_h2=float(omega_b_h2), y_p=float(Y_p))
        n_e = x_e * n_h
        h_z = _h_lcdm_rad_si(
            z=float(z),
            H0_si=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_r=float(Omega_r),
            Omega_lambda=float(Omega_lambda),
        )
        dtdz = float(C_SI) * float(sigma_t) * float(n_e) / ((1.0 + float(z)) * float(h_z))
        dtaudz.append(float(dtdz))

    # Visibility requires tau(z)=∫_z^zmax dτ/dz dz, i.e. reverse cumulative
    # integration on an increasing-z grid.
    tau: list[float] = [0.0] * int(n_vis)
    for i in range(int(n_vis) - 2, -1, -1):
        tau[i] = float(tau[i + 1] + 0.5 * (dtaudz[i + 1] + dtaudz[i]) * dz)

    g_vals: list[float] = [math.exp(-float(tau[i])) * float(dtaudz[i]) for i in range(int(n_vis))]
    max_idx = max(range(int(n_vis)), key=lambda i: float(g_vals[i]))
    max_g = float(g_vals[max_idx])
    z_star = float(z_grid[max_idx])
    x_at_star = float(x_vis[max_idx])

    if not (z_star > 0.0 and math.isfinite(z_star)):
        raise ValueError("failed to compute a physical z_star in peebles3 diagnostic mode")

    info: Dict[str, Any] = {
        "method": "peebles3",
        "converged": bool(converged),
        "steps": int(steps_accepted),
        "steps_attempted": int(steps_attempted),
        "last_h_u": float(h),
        "rtol": float(rtol),
        "atol": float(atol),
        "z_min_ode": float(z_min_ode),
        "z_max_ode": float(z_max),
        "max_steps": int(max_steps),
        "n_visibility": int(n_vis),
        "x_e_at_z_star": float(x_at_star),
        "g_max": float(max_g),
    }
    return float(z_star), info


def compute_z_star(
    *,
    method: str,
    omega_b_h2: float,
    omega_m_h2: float,
    H0_si: float,
    Omega_m: float,
    Omega_r: float,
    Omega_lambda: float,
    Tcmb_K: float,
    Y_p: float,
    rtol: float = 1e-6,
    atol: float = 1e-10,
    max_steps: int = 4096,
    z_max: float = 3000.0,
    z_min_ode: float = 200.0,
) -> Tuple[float, Dict[str, Any]]:
    """Return recombination redshift and diagnostics metadata.

    Supported methods:
    - `fit`: Hu-Sugiyama-style fitting formula.
    - `peebles3`: lightweight ODE visibility-peak estimate (diagnostic only).
    """
    mode = str(method).strip().lower()
    if mode == "fit":
        z_star = _z_star_hu_sugiyama_fit(
            omega_b_h2=float(omega_b_h2),
            omega_m_h2=float(omega_m_h2),
        )
        return float(z_star), {
            "method": "fit",
            "converged": True,
            "steps": 0,
            "steps_attempted": 0,
            "last_h_u": None,
            "rtol": None,
            "atol": None,
            "max_steps": int(max_steps),
        }
    if mode == "peebles3":
        z_star_diag, info = _z_star_peebles3(
            H0_si=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_r=float(Omega_r),
            Omega_lambda=float(Omega_lambda),
            omega_b_h2=float(omega_b_h2),
            Tcmb_K=float(Tcmb_K),
            Y_p=float(Y_p),
            z_max=float(z_max),
            z_min_ode=float(z_min_ode),
            max_steps=int(max_steps),
            rtol=float(rtol),
            atol=float(atol),
        )
        boundary_hit = bool(float(z_star_diag) <= float(z_min_ode) * 1.001) or bool(
            float(z_star_diag) >= float(z_max) * 0.999
        )
        if (not bool(info.get("converged", False))) or boundary_hit:
            z_fit = _z_star_hu_sugiyama_fit(
                omega_b_h2=float(omega_b_h2),
                omega_m_h2=float(omega_m_h2),
            )
            out = dict(info)
            out["method"] = "peebles3_fallback_fit"
            out["fallback"] = "fit"
            out["fallback_reason"] = (
                "non-converged"
                if not bool(info.get("converged", False))
                else "visibility_peak_boundary"
            )
            out["z_star_peebles3_raw"] = float(z_star_diag)
            out["z_star_fit"] = float(z_fit)
            return float(z_fit), out
        return float(z_star_diag), info
    raise ValueError(f"Unsupported recombination method: {method!r}. Allowed: fit, peebles3")


def _drag_integrand(
    z: float,
    *,
    H0_si: float,
    Omega_m: float,
    Omega_r: float,
    Omega_lambda: float,
    omega_b_h2: float,
    Tcmb_K: float,
    Y_p: float,
) -> float:
    sigma_t = 6.6524587321e-29
    one_plus_z = 1.0 + float(z)
    n_h = _n_h_m3(z=float(z), H0_si=float(H0_si), omega_b_h2=float(omega_b_h2), y_p=float(Y_p))
    n_e = float(n_h)  # diagnostic simplification: fully ionized around drag epoch
    h_z = _h_lcdm_rad_si(
        z=float(z),
        H0_si=float(H0_si),
        Omega_m=float(Omega_m),
        Omega_r=float(Omega_r),
        Omega_lambda=float(Omega_lambda),
    )
    omega_gamma_h2 = omega_gamma_h2_from_Tcmb(float(Tcmb_K))
    r_fac = (3.0 / 4.0) * (float(omega_b_h2) / float(omega_gamma_h2)) / one_plus_z
    if not (math.isfinite(r_fac) and r_fac > 0.0):
        raise ValueError("invalid baryon loading factor in drag integrand")
    return float(C_SI) * float(sigma_t) * float(n_e) / (one_plus_z * float(h_z) * float(r_fac))


def compute_z_drag(
    *,
    method: str,
    omega_b_h2: float,
    omega_m_h2: float,
    H0_si: float,
    Omega_m: float,
    Omega_r: float,
    Omega_lambda: float,
    Tcmb_K: float,
    Y_p: float,
    rtol: float = 1e-6,
    atol: float = 1e-6,
    max_steps: int = 48,
    z_max: float = 1.0e5,
) -> Tuple[float, Dict[str, Any]]:
    """Return drag redshift and diagnostics metadata.

    `ode` mode is a lightweight, diagnostic-only approximation and must not be
    interpreted as a precision recombination/drag engine.
    """
    mode = str(method).strip().lower()
    if mode == "eh98":
        z_drag = z_drag_eisenstein_hu(
            omega_m_h2=float(omega_m_h2),
            omega_b_h2=float(omega_b_h2),
        )
        return float(z_drag), {
            "method": "eh98",
            "converged": True,
            "steps": 0,
            "n_eval": 0,
            "rtol": None,
            "atol": None,
            "tau_residual": None,
        }

    if mode != "ode":
        raise ValueError(f"Unsupported drag method: {method!r}. Allowed: eh98, ode")

    if not (float(rtol) > 0.0 and math.isfinite(float(rtol))):
        raise ValueError("drag rtol must be finite and > 0")
    if not (float(atol) > 0.0 and math.isfinite(float(atol))):
        raise ValueError("drag atol must be finite and > 0")

    z_lo = 10.0
    z_hi = float(max(z_lo + 1.0, z_max))
    n_eval_total = 0

    def tau_drag(z_start: float) -> Tuple[float, int, float]:
        meta = adaptive_simpson_log1p_z_with_meta(
            lambda zz: _drag_integrand(
                float(zz),
                H0_si=float(H0_si),
                Omega_m=float(Omega_m),
                Omega_r=float(Omega_r),
                Omega_lambda=float(Omega_lambda),
                omega_b_h2=float(omega_b_h2),
                Tcmb_K=float(Tcmb_K),
                Y_p=float(Y_p),
            ),
            float(z_start),
            float(z_hi),
            eps_abs=1e-8,
            eps_rel=1e-8,
            max_depth=20,
        )
        return float(meta.value), int(meta.n_eval), float(meta.abs_err_est)

    tau_lo, n_lo, err_lo = tau_drag(z_lo)
    tau_hi, n_hi, err_hi = tau_drag(z_hi - 1.0)
    n_eval_total += int(n_lo + n_hi)

    if not (math.isfinite(tau_lo) and math.isfinite(tau_hi)):
        raise ValueError("drag ODE approximation produced non-finite optical depth")

    # If a bracket cannot be formed, fall back to EH98 while marking non-convergence.
    if not (tau_lo >= 1.0 and tau_hi <= 1.0):
        z_drag = z_drag_eisenstein_hu(
            omega_m_h2=float(omega_m_h2),
            omega_b_h2=float(omega_b_h2),
        )
        return float(z_drag), {
            "method": "ode",
            "converged": False,
            "steps": 0,
            "n_eval": int(n_eval_total),
            "rtol": float(rtol),
            "atol": float(atol),
            "tau_residual": None,
            "fallback": "eh98",
            "tau_lo": float(tau_lo),
            "tau_hi": float(tau_hi),
            "tau_lo_err": float(err_lo),
            "tau_hi_err": float(err_hi),
        }

    left = float(z_lo)
    right = float(z_hi - 1.0)
    z_mid = 0.5 * (left + right)
    tau_mid = float("nan")
    tau_mid_err = float("nan")
    converged = False

    for step in range(int(max_steps)):
        z_mid = 0.5 * (left + right)
        tau_mid, n_mid, tau_mid_err = tau_drag(z_mid)
        n_eval_total += int(n_mid)
        target_resid = abs(float(tau_mid) - 1.0)
        if target_resid <= max(float(atol), float(rtol)):
            converged = True
            break
        if tau_mid > 1.0:
            left = float(z_mid)
        else:
            right = float(z_mid)

    return float(z_mid), {
        "method": "ode",
        "converged": bool(converged),
        "steps": int(max_steps if not converged else step + 1),
        "n_eval": int(n_eval_total),
        "rtol": float(rtol),
        "atol": float(atol),
        "tau_residual": None if not math.isfinite(tau_mid) else float(abs(float(tau_mid) - 1.0)),
        "tau_mid_err": None if not math.isfinite(tau_mid_err) else float(tau_mid_err),
    }


__all__ = [
    "compute_z_star",
    "compute_z_drag",
]
