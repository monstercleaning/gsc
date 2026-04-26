"""Minimal LCDM compressed-CMB prior predictions (E1 bridge).

This module intentionally provides a lightweight bridge for compressed CMB
priors (e.g. theta_star, lA, R) without a full Boltzmann/recombination engine.
It is meant for E1 consistency checks, not for full CMB claims.
"""

from __future__ import annotations

import math
from typing import Dict, Mapping

from ..measurement_model import C_SI, H0_to_SI, MPC_SI
from ..numerics_adaptive_quad import (
    AdaptiveQuadResult,
    adaptive_simpson,
    adaptive_simpson_log1p_z,
    adaptive_simpson_log1p_z_with_meta,
    adaptive_simpson_with_meta,
)
from ..optional_deps import require_numpy
from .cmb_microphysics_knobs import MicrophysicsKnobs, knobs_from_dict
from .recombination_methods import compute_z_drag, compute_z_star
from .rd import compute_rd_Mpc, omega_gamma_h2_from_Tcmb, omega_r_h2

# The E1 "compressed CMB" predictor is intentionally lightweight and does not
# model full recombination microphysics. For strict CHW2018 distance priors
# (R, lA, omega_b_h2) the most sensitive observable is lA = pi * D_M(z*) / r_s(z*).
#
# Our current bridge-level r_s(z*) integral (with z* from a fitting formula)
# is systematically low by ~0.29% at Planck-like parameters, which inflates lA
# by the same fraction and dominates chi2. We apply a tiny, explicit calibration
# factor so strict E1.1 measures model/assumption tension rather than a known
# approximation offset in r_s.
#
# Calibration target: CHW2018 base_plikHM_TTTEEE_lowE mean lA at:
#   H0=67.4, Omega_m=0.315, omega_b_h2=0.02237, omega_c_h2=0.1200, Neff=3.046.
_RS_STAR_CALIB_CHW2018 = 1.0028886325651902

# Diagnostic-only closure knob: allow a multiplicative rescaling of D_M(z*) in
# the compressed-CMB distance-priors prediction path.
#
# This is intentionally *not* used by any canonical late-time pipeline runs; it
# exists only for "what would it take" E2 diagnostics (e.g. joint fits of R and
# lA under strict CHW2018 distance priors).


_require_numpy = require_numpy
_SUPPORTED_INTEGRATORS = frozenset({"trap", "adaptive_simpson"})
_SUPPORTED_RECOMBINATION_METHODS = frozenset({"fit", "peebles3"})
_SUPPORTED_DRAG_METHODS = frozenset({"eh98", "ode"})


def _validate_integrator(
    integrator: str,
    *,
    eps_abs: float,
    eps_rel: float,
) -> str:
    method = str(integrator).strip().lower()
    if method not in _SUPPORTED_INTEGRATORS:
        allowed = ", ".join(sorted(_SUPPORTED_INTEGRATORS))
        raise ValueError(f"Unsupported integrator: {integrator!r}. Allowed: {allowed}")
    if not (math.isfinite(float(eps_abs)) and float(eps_abs) > 0.0):
        raise ValueError("integration_eps_abs must be finite and > 0")
    if not (math.isfinite(float(eps_rel)) and float(eps_rel) > 0.0):
        raise ValueError("integration_eps_rel must be finite and > 0")
    return method


def _validate_recombination_method(method: str) -> str:
    out = str(method).strip().lower()
    if out not in _SUPPORTED_RECOMBINATION_METHODS:
        allowed = ", ".join(sorted(_SUPPORTED_RECOMBINATION_METHODS))
        raise ValueError(f"Unsupported recombination method: {method!r}. Allowed: {allowed}")
    return out


def _validate_drag_method(method: str) -> str:
    out = str(method).strip().lower()
    if out not in _SUPPORTED_DRAG_METHODS:
        allowed = ", ".join(sorted(_SUPPORTED_DRAG_METHODS))
        raise ValueError(f"Unsupported drag method: {method!r}. Allowed: {allowed}")
    return out


def _trap_integral_with_err(x, y, np) -> tuple[float, float, int]:
    integral = _np_trapezoid(np, y, x)
    n_eval = int(len(x))
    err = 0.0
    if int(len(x)) >= 3:
        x2 = x[::2]
        y2 = y[::2]
        if float(x2[-1]) != float(x[-1]):
            x2 = np.concatenate((x2, x[-1:]))
            y2 = np.concatenate((y2, y[-1:]))
        if int(len(x2)) >= 2:
            integral2 = _np_trapezoid(np, y2, x2)
            err = abs(float(integral) - float(integral2)) / 3.0
    if not (math.isfinite(err) and err >= 0.0):
        err = 0.0
    return float(integral), float(err), int(n_eval)


def _np_trapezoid(np, y, x) -> float:
    trap = getattr(np, "trapezoid", None)
    if callable(trap):
        return float(trap(y, x))
    trapz = getattr(np, "trapz", None)
    if callable(trapz):
        return float(trapz(y, x))
    y_arr = np.asarray(y, dtype=float)
    x_arr = np.asarray(x, dtype=float)
    if y_arr.shape != x_arr.shape:
        raise ValueError("trapezoid fallback requires x and y with matching shape")
    if int(y_arr.size) < 2:
        return 0.0
    return float(0.5 * np.sum((y_arr[1:] + y_arr[:-1]) * (x_arr[1:] - x_arr[:-1])))


def _adaptive_meta_to_dict(meta: AdaptiveQuadResult) -> Dict[str, float | int | str]:
    return {
        "method": str(meta.method),
        "n_eval": int(meta.n_eval),
        "abs_err_est": float(meta.abs_err_est),
        "rtol": float(meta.rtol),
        "atol": float(meta.atol),
    }


def _num_meta(
    *,
    method: str,
    n_eval: int,
    abs_err_est: float | None,
    rtol: float | None,
    atol: float | None,
) -> Dict[str, float | int | str | None]:
    return {
        "method": str(method),
        "n_eval": int(n_eval),
        "abs_err_est": None if abs_err_est is None else float(abs_err_est),
        "rtol": None if rtol is None else float(rtol),
        "atol": None if atol is None else float(atol),
    }


def _sum_num_meta(parts: list[Mapping[str, float | int | str | None]], *, method: str, rtol: float, atol: float) -> Dict[str, float | int | str]:
    n_eval = 0
    err = 0.0
    for part in parts:
        n_eval += int(part.get("n_eval", 0) or 0)
        raw_err = part.get("abs_err_est")
        if raw_err is None:
            continue
        fv = float(raw_err)
        if math.isfinite(fv) and fv >= 0.0:
            err += fv
    return {
        "method": str(method),
        "n_eval": int(n_eval),
        "abs_err_est": float(err),
        "rtol": float(rtol),
        "atol": float(atol),
    }


def z_star_hu_sugiyama(*, omega_b_h2: float, omega_m_h2: float) -> float:
    """Approximate recombination redshift z_* (Hu & Sugiyama style fit)."""
    if not (omega_b_h2 > 0 and math.isfinite(omega_b_h2)):
        raise ValueError("omega_b_h2 must be positive and finite")
    if not (omega_m_h2 > 0 and math.isfinite(omega_m_h2)):
        raise ValueError("omega_m_h2 must be positive and finite")

    g1 = (0.0783 * (omega_b_h2 ** -0.238)) / (1.0 + 39.5 * (omega_b_h2 ** 0.763))
    g2 = 0.560 / (1.0 + 21.1 * (omega_b_h2 ** 1.81))
    z_star = 1048.0 * (1.0 + 0.00124 * (omega_b_h2 ** -0.738)) * (1.0 + g1 * (omega_m_h2 ** g2))
    if not (z_star > 0 and math.isfinite(z_star)):
        raise ValueError("Computed z_star is non-physical")
    return float(z_star)


def _e_lcdm_radiation(
    z,
    *,
    omega_m: float,
    omega_r: float,
    omega_lambda: float,
):
    return (omega_r * (1.0 + z) ** 4 + omega_m * (1.0 + z) ** 3 + omega_lambda) ** 0.5


def _comoving_distance_model_to_z_m(
    *,
    z: float,
    model,
    n: int = 4096,
    integrator: str = "trap",
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    return_meta: bool = False,
) -> float | tuple[float, Dict[str, float | int | str | None]]:
    """Return comoving distance D_M(z) in meters by integrating a model's H(z).

    The model is expected to expose `H(z)` returning SI units [1/s].
    """
    method = _validate_integrator(integrator, eps_abs=eps_abs, eps_rel=eps_rel)
    if not (z >= 0 and math.isfinite(z)):
        raise ValueError("z must be finite and >= 0")
    if z == 0.0:
        return 0.0
    if method == "trap" and n < 256:
        raise ValueError("integration grid too small")
    if method == "trap":
        np = _require_numpy()
        zz = np.linspace(0.0, float(z), int(n), dtype=float)
        Hz = np.asarray([float(model.H(float(zi))) for zi in zz], dtype=float)
        if not (np.isfinite(Hz).all() and float(Hz.min()) > 0.0):
            raise ValueError("H(z) must be finite and strictly positive on [0,z]")
        integral, err_est, n_eval = _trap_integral_with_err(zz, 1.0 / Hz, np)
        meta = _num_meta(
            method="trap",
            n_eval=int(n_eval),
            abs_err_est=float(err_est),
            rtol=float(eps_rel),
            atol=float(eps_abs),
        )
    else:
        def inv_h(zi: float) -> float:
            hz = float(model.H(float(zi)))
            if not (math.isfinite(hz) and hz > 0.0):
                raise ValueError("H(z) must be finite and strictly positive on [0,z]")
            return 1.0 / hz

        meta_obj = adaptive_simpson_with_meta(
            inv_h,
            0.0,
            float(z),
            eps_abs=float(eps_abs),
            eps_rel=float(eps_rel),
        )
        integral = float(meta_obj.value)
        meta = _adaptive_meta_to_dict(meta_obj)
    value = float(C_SI) * float(integral)
    if not bool(return_meta):
        return float(value)
    meta_out = dict(meta)
    if meta_out.get("abs_err_est") is not None:
        meta_out["abs_err_est"] = float(meta_out["abs_err_est"]) * float(C_SI)
    return float(value), meta_out


def _comoving_distance_to_z_m(
    *,
    z: float,
    H0_si: float,
    omega_m: float,
    omega_r: float,
    omega_lambda: float,
    n: int = 8192,
    integrator: str = "trap",
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    return_meta: bool = False,
) -> float | tuple[float, Dict[str, float | int | str | None]]:
    method = _validate_integrator(integrator, eps_abs=eps_abs, eps_rel=eps_rel)
    if not (z > 0 and math.isfinite(z)):
        raise ValueError("z must be positive and finite")
    if method == "trap" and n < 256:
        raise ValueError("integration grid too small")
    if method == "trap":
        np = _require_numpy()
        zz = np.linspace(0.0, float(z), int(n), dtype=float)
        Ez = _e_lcdm_radiation(zz, omega_m=float(omega_m), omega_r=float(omega_r), omega_lambda=float(omega_lambda))
        integrand = 1.0 / Ez
        integral, err_est, n_eval = _trap_integral_with_err(zz, integrand, np)
        meta = _num_meta(
            method="trap",
            n_eval=int(n_eval),
            abs_err_est=float(err_est),
            rtol=float(eps_rel),
            atol=float(eps_abs),
        )
    else:
        def inv_e(zi: float) -> float:
            e_val = float(_e_lcdm_radiation(float(zi), omega_m=float(omega_m), omega_r=float(omega_r), omega_lambda=float(omega_lambda)))
            if not (math.isfinite(e_val) and e_val > 0.0):
                raise ValueError("E(z) must be finite and strictly positive on [0,z]")
            return 1.0 / e_val

        meta_obj = adaptive_simpson_with_meta(
            inv_e,
            0.0,
            float(z),
            eps_abs=float(eps_abs),
            eps_rel=float(eps_rel),
        )
        integral = float(meta_obj.value)
        meta = _adaptive_meta_to_dict(meta_obj)
    value = float(C_SI) / float(H0_si) * float(integral)
    if not bool(return_meta):
        return float(value)
    meta_out = dict(meta)
    if meta_out.get("abs_err_est") is not None:
        meta_out["abs_err_est"] = (float(C_SI) / float(H0_si)) * float(meta_out["abs_err_est"])
    return float(value), meta_out


def _sound_horizon_from_z_m(
    *,
    z: float,
    H0_si: float,
    omega_b_h2: float,
    omega_gamma_h2: float,
    omega_m: float,
    omega_r: float,
    omega_lambda: float,
    z_max: float = 1.0e7,
    n: int = 8192,
    integrator: str = "trap",
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    return_meta: bool = False,
) -> float | tuple[float, Dict[str, float | int | str | None]]:
    method = _validate_integrator(integrator, eps_abs=eps_abs, eps_rel=eps_rel)
    if not (z > 0 and z_max > z and math.isfinite(z_max)):
        raise ValueError("Require z_max > z > 0 for sound-horizon integral")
    if method == "trap" and n < 512:
        raise ValueError("integration grid too small")

    def cs_over_h(zz: float) -> float:
        one_plus_z = 1.0 + float(zz)
        R = (3.0 / 4.0) * (float(omega_b_h2) / float(omega_gamma_h2)) / one_plus_z
        cs = float(C_SI) / math.sqrt(3.0 * (1.0 + R))
        Ez = float(_e_lcdm_radiation(float(zz), omega_m=float(omega_m), omega_r=float(omega_r), omega_lambda=float(omega_lambda)))
        Hz = float(H0_si) * Ez
        if not (math.isfinite(Hz) and Hz > 0.0):
            raise ValueError("H(z) must be finite and strictly positive in sound-horizon integral")
        return cs / Hz

    if method == "trap":
        np = _require_numpy()
        # Integrate over u = ln(1+z) to sample early times efficiently.
        u0 = math.log1p(float(z))
        u1 = math.log1p(float(z_max))
        uu = np.linspace(u0, u1, int(n), dtype=float)
        one_plus_z = np.exp(uu)
        zz = one_plus_z - 1.0

        R = (3.0 / 4.0) * (float(omega_b_h2) / float(omega_gamma_h2)) / one_plus_z
        cs = float(C_SI) / np.sqrt(3.0 * (1.0 + R))
        Ez = _e_lcdm_radiation(zz, omega_m=float(omega_m), omega_r=float(omega_r), omega_lambda=float(omega_lambda))
        Hz = float(H0_si) * Ez

        # dz = (1+z) du
        integrand = (cs / Hz) * one_plus_z
        rs, err_est, n_eval = _trap_integral_with_err(uu, integrand, np)
        meta = _num_meta(
            method="trap",
            n_eval=int(n_eval),
            abs_err_est=float(err_est),
            rtol=float(eps_rel),
            atol=float(eps_abs),
        )
    else:
        meta_obj = adaptive_simpson_log1p_z_with_meta(
            cs_over_h,
            float(z),
            float(z_max),
            eps_abs=float(eps_abs),
            eps_rel=float(eps_rel),
        )
        rs = float(meta_obj.value)
        meta = _adaptive_meta_to_dict(meta_obj)
    if not (rs > 0 and math.isfinite(rs)):
        raise ValueError("Computed sound horizon is non-physical")
    if not bool(return_meta):
        return float(rs)
    return float(rs), dict(meta)


def _sound_horizon_model_from_z_m(
    *,
    z: float,
    model,
    omega_b_h2: float,
    omega_gamma_h2: float,
    z_max: float = 1.0e7,
    n: int = 8192,
    integrator: str = "trap",
    eps_abs: float = 1e-10,
    eps_rel: float = 1e-10,
    return_meta: bool = False,
) -> float | tuple[float, Dict[str, float | int | str | None]]:
    """Return the sound horizon r_s(z) in meters by integrating cs/H over a model.H(z).

    This is a diagnostic-only helper for E2 "full history" experiments. It keeps the
    standard baryon/photon sound speed c_s(z) (via R(z)) but uses the supplied
    full-range history for H(z).
    """
    method = _validate_integrator(integrator, eps_abs=eps_abs, eps_rel=eps_rel)
    if not (z > 0 and z_max > z and math.isfinite(z_max)):
        raise ValueError("Require z_max > z > 0 for sound-horizon integral")
    if method == "trap" and n < 512:
        raise ValueError("integration grid too small")

    def cs_over_h(zz: float) -> float:
        one_plus_z = 1.0 + float(zz)
        R = (3.0 / 4.0) * (float(omega_b_h2) / float(omega_gamma_h2)) / one_plus_z
        cs = float(C_SI) / math.sqrt(3.0 * (1.0 + R))
        hz = float(model.H(float(zz)))
        if not (math.isfinite(hz) and hz > 0.0):
            raise ValueError("H(z) must be finite and strictly positive in sound-horizon integral")
        return cs / hz

    if method == "trap":
        np = _require_numpy()
        u0 = math.log1p(float(z))
        u1 = math.log1p(float(z_max))
        uu = np.linspace(u0, u1, int(n), dtype=float)
        one_plus_z = np.exp(uu)
        zz = one_plus_z - 1.0

        R = (3.0 / 4.0) * (float(omega_b_h2) / float(omega_gamma_h2)) / one_plus_z
        cs = float(C_SI) / np.sqrt(3.0 * (1.0 + R))
        Hz = np.asarray([float(model.H(float(zi))) for zi in zz], dtype=float)
        if not (np.isfinite(Hz).all() and float(Hz.min()) > 0.0):
            raise ValueError("H(z) must be finite and strictly positive in sound-horizon integral")

        # dz = (1+z) du
        integrand = (cs / Hz) * one_plus_z
        rs, err_est, n_eval = _trap_integral_with_err(uu, integrand, np)
        meta = _num_meta(
            method="trap",
            n_eval=int(n_eval),
            abs_err_est=float(err_est),
            rtol=float(eps_rel),
            atol=float(eps_abs),
        )
    else:
        meta_obj = adaptive_simpson_log1p_z_with_meta(
            cs_over_h,
            float(z),
            float(z_max),
            eps_abs=float(eps_abs),
            eps_rel=float(eps_rel),
        )
        rs = float(meta_obj.value)
        meta = _adaptive_meta_to_dict(meta_obj)
    if not (rs > 0 and math.isfinite(rs)):
        raise ValueError("Computed sound horizon is non-physical")
    if not bool(return_meta):
        return float(rs)
    return float(rs), dict(meta)


def compute_bridged_distance_priors(
    *,
    model,
    z_bridge: float,
    omega_b_h2: float,
    omega_c_h2: float,
    N_eff: float = 3.046,
    Tcmb_K: float = 2.7255,
    rs_star_calibration: float = 1.0,
    dm_star_calibration: float = 1.0,
    z_star: float | None = None,
    Y_p: float | None = None,
    microphysics: MicrophysicsKnobs | Mapping[str, float] | None = None,
    D_M_model_to_z_bridge_m: float | None = None,
    integrator: str = "trap",
    integration_eps_abs: float = 1e-10,
    integration_eps_rel: float = 1e-10,
    recombination_method: str = "fit",
    drag_method: str = "eh98",
    recombination_rtol: float = 1e-6,
    recombination_atol: float = 1e-10,
    recombination_max_steps: int = 4096,
) -> Dict[str, float]:
    """Return compressed-CMB prior predictions using a late-time/early-time bridge.

    This is an E1 bridge helper for non-LCDM late-time histories:
    - Use the provided `model.H(z)` for 0 <= z <= z_bridge (late-time history).
    - Use a standard LCDM+rad early-time history for z > z_bridge when computing
      the integral contribution to D_M(z_star) and for r_s(z_star).

    Notes:
    - This is intentionally approximate and should be treated as a bridge /
      consistency check, not a full CMB likelihood.
    - If `D_M_model_to_z_bridge_m` is supplied, it is used directly to avoid
      re-integrating the late-time model (useful in grid search where D_M is
      already interpolated).
    """
    if not (z_bridge > 0 and math.isfinite(z_bridge)):
        raise ValueError("z_bridge must be finite and > 0")
    if not (omega_b_h2 > 0 and omega_c_h2 >= 0):
        raise ValueError("omega_b_h2 must be >0 and omega_c_h2 must be >=0")
    if not (rs_star_calibration > 0 and math.isfinite(rs_star_calibration)):
        raise ValueError("rs_star_calibration must be finite and > 0")
    if not (dm_star_calibration > 0 and math.isfinite(dm_star_calibration)):
        raise ValueError("dm_star_calibration must be finite and > 0")
    knobs = knobs_from_dict(microphysics)
    integration_method = _validate_integrator(
        integrator,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
    )
    recomb_method = _validate_recombination_method(recombination_method)
    drag_method_use = _validate_drag_method(drag_method)
    if not (math.isfinite(float(recombination_rtol)) and float(recombination_rtol) > 0.0):
        raise ValueError("recombination_rtol must be finite and > 0")
    if not (math.isfinite(float(recombination_atol)) and float(recombination_atol) > 0.0):
        raise ValueError("recombination_atol must be finite and > 0")
    if int(recombination_max_steps) <= 0:
        raise ValueError("recombination_max_steps must be > 0")

    if integration_method == "trap":
        np = _require_numpy()
        _ = np

    H0_si = float(model.H(0.0))
    if not (H0_si > 0 and math.isfinite(H0_si)):
        raise ValueError("model.H(0) must be positive and finite (SI)")

    # Convert to km/s/Mpc to compute h.
    H0_km_s_Mpc = float(H0_si) * float(MPC_SI) / 1000.0
    h = float(H0_km_s_Mpc) / 100.0

    omega_g_h2 = omega_gamma_h2_from_Tcmb(float(Tcmb_K))
    omega_r_h2_val = omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(N_eff))
    Omega_r = float(omega_r_h2_val) / (h * h)

    omega_m_h2 = float(omega_b_h2) + float(omega_c_h2)
    Omega_m_early = float(omega_m_h2) / (h * h)

    Omega_lambda_early = 1.0 - float(Omega_m_early) - float(Omega_r)
    if Omega_lambda_early < 0:
        raise ValueError("Derived Omega_lambda_early < 0; adjust inputs")

    y_p_use = 0.245 if Y_p is None else float(Y_p)
    if not (0.0 <= float(y_p_use) < 1.0 and math.isfinite(float(y_p_use))):
        raise ValueError("Y_p must be finite and in [0,1)")
    if z_star is not None:
        z_star_base = float(z_star)
        z_star_meta: Dict[str, float | int | bool | None | str] = {
            "method": "explicit",
            "converged": True,
            "steps": 0,
            "steps_attempted": 0,
            "last_h_u": None,
            "rtol": None,
            "atol": None,
            "max_steps": 0,
        }
    else:
        z_star_base, z_star_meta = compute_z_star(
            method=str(recomb_method),
            omega_b_h2=float(omega_b_h2),
            omega_m_h2=float(omega_m_h2),
            H0_si=float(H0_si),
            Omega_m=float(Omega_m_early),
            Omega_r=float(Omega_r),
            Omega_lambda=float(Omega_lambda_early),
            Tcmb_K=float(Tcmb_K),
            Y_p=float(y_p_use),
            rtol=float(recombination_rtol),
            atol=float(recombination_atol),
            max_steps=int(recombination_max_steps),
        )
    z_star_use = float(z_star_base) * float(knobs.z_star_scale)
    if not (z_star_use > 0.0 and math.isfinite(z_star_use)):
        raise ValueError("Scaled z_star is non-physical")
    z_b = float(min(float(z_bridge), float(z_star_use)))

    z_drag, z_drag_meta = compute_z_drag(
        method=str(drag_method_use),
        omega_b_h2=float(omega_b_h2),
        omega_m_h2=float(omega_m_h2),
        H0_si=float(H0_si),
        Omega_m=float(Omega_m_early),
        Omega_r=float(Omega_r),
        Omega_lambda=float(Omega_lambda_early),
        Tcmb_K=float(Tcmb_K),
        Y_p=float(y_p_use),
        rtol=float(recombination_rtol),
        atol=max(float(recombination_atol), 1e-6),
        max_steps=max(8, int(recombination_max_steps) // 64),
    )

    # Late-time part: D_M(0->z_b) from the provided model.
    if D_M_model_to_z_bridge_m is None:
        D_low_m, D_low_meta = _comoving_distance_model_to_z_m(
            z=z_b,
            model=model,
            n=4096,
            integrator=integration_method,
            eps_abs=float(integration_eps_abs),
            eps_rel=float(integration_eps_rel),
            return_meta=True,
        )
    else:
        D_low_m = float(D_M_model_to_z_bridge_m)
        if not (D_low_m >= 0 and math.isfinite(D_low_m)):
            raise ValueError("D_M_model_to_z_bridge_m must be finite and >= 0")
        D_low_meta = _num_meta(
            method="precomputed",
            n_eval=0,
            abs_err_est=0.0,
            rtol=float(integration_eps_rel),
            atol=float(integration_eps_abs),
        )

    # Early-time part: add the remaining distance using LCDM+rad, to avoid
    # integrating the late-time model out to z~1100.
    D_early_star_m, D_early_star_meta = _comoving_distance_to_z_m(
        z=z_star_use,
        H0_si=H0_si,
        omega_m=float(Omega_m_early),
        omega_r=float(Omega_r),
        omega_lambda=float(Omega_lambda_early),
        integrator=integration_method,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
        return_meta=True,
    )
    D_early_b_m, D_early_b_meta = _comoving_distance_to_z_m(
        z=z_b,
        H0_si=H0_si,
        omega_m=float(Omega_m_early),
        omega_r=float(Omega_r),
        omega_lambda=float(Omega_lambda_early),
        n=2048,
        integrator=integration_method,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
        return_meta=True,
    )
    dm_num_meta = _sum_num_meta(
        [D_low_meta, D_early_star_meta, D_early_b_meta],
        method=str(integration_method),
        rtol=float(integration_eps_rel),
        atol=float(integration_eps_abs),
    )
    D_M_star_m_raw = float(D_low_m + (D_early_star_m - D_early_b_m))
    if not (D_M_star_m_raw > 0 and math.isfinite(D_M_star_m_raw)):
        raise ValueError("Computed bridged D_M(z_star) is non-physical")
    # Diagnostic-only calibration: rescale D_M(z*) after the integral is formed.
    # This affects R and lA, but is not a physical early-time closure.
    D_M_star_m = float(D_M_star_m_raw) * float(dm_star_calibration)

    r_s_star_m_raw, rs_num_meta = _sound_horizon_from_z_m(
        z=z_star_use,
        H0_si=H0_si,
        omega_b_h2=float(omega_b_h2),
        omega_gamma_h2=float(omega_g_h2),
        omega_m=float(Omega_m_early),
        omega_r=float(Omega_r),
        omega_lambda=float(Omega_lambda_early),
        integrator=integration_method,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
        return_meta=True,
    )
    # Stopgap calibration: this is an effective correction for the bridge-level
    # z_star fit + r_s(z*) integral accuracy. It must only be applied to r_s at
    # recombination (z*), and must not affect r_d / BAO.
    #
    # TODO(v10+): replace this with a higher-precision early-time engine or an
    # explicitly-derived freeze-frame treatment of recombination.
    r_s_star_m = float(r_s_star_m_raw) * float(rs_star_calibration) * float(knobs.r_s_scale)

    theta_star = float(r_s_star_m / D_M_star_m)
    lA = float(math.pi / theta_star)
    R = float(math.sqrt(float(Omega_m_early)) * H0_si * D_M_star_m / float(C_SI))
    rd_mpc_base = float(
        compute_rd_Mpc(
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(N_eff),
            Tcmb_K=float(Tcmb_K),
            method="eisenstein_hu_1998",
        )
    )
    rd_mpc = float(rd_mpc_base) * float(knobs.r_d_scale)

    # Bridge diagnostics (helps interpret mismatches).
    H_bridge_model = float(model.H(float(z_b)))
    H_bridge_early = float(H0_si) * float(_e_lcdm_radiation(float(z_b), omega_m=float(Omega_m_early), omega_r=float(Omega_r), omega_lambda=float(Omega_lambda_early)))
    bridge_ratio = float(H_bridge_model / H_bridge_early) if (H_bridge_early > 0 and math.isfinite(H_bridge_model)) else float("nan")

    return {
        "theta_star": theta_star,
        "lA": lA,
        "R": R,
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
        "z_star": z_star_use,
        "z_star_base": float(z_star_base),
        "z_drag": float(z_drag),
        "r_s_star_Mpc": float(r_s_star_m / float(MPC_SI)),
        "D_M_star_Mpc": float(D_M_star_m / float(MPC_SI)),
        "D_M_star_Mpc_raw": float(D_M_star_m_raw / float(MPC_SI)),
        # Distance split provenance (helps interpret bridge sensitivity).
        #
        # D_M(z*) is computed as:
        #   D_M_total = D_M_model(0->z_b) + (D_M_early(0->z*) - D_M_early(0->z_b))
        "D_M_0_to_bridge_Mpc": float(D_low_m / float(MPC_SI)),
        "D_M_bridge_to_zstar_Mpc": float((D_early_star_m - D_early_b_m) / float(MPC_SI)),
        "rd_Mpc": rd_mpc,
        "rs_star_calibration": float(rs_star_calibration),
        "rs_star_calibration_applied": bool(float(rs_star_calibration) != 1.0),
        "dm_star_calibration": float(dm_star_calibration),
        "dm_star_calibration_applied": bool(float(dm_star_calibration) != 1.0),
        "dm_star_calibration_reason": (
            "diagnostic-only: D_M(z*) rescaling for compressed-CMB distance priors"
            if float(dm_star_calibration) != 1.0
            else ""
        ),
        "integration_method": str(integration_method),
        "recombination_method": str(z_star_meta.get("method", recomb_method)),
        "recomb_converged": bool(z_star_meta.get("converged", True)),
        "recomb_steps": int(z_star_meta.get("steps", 0) or 0),
        "recomb_steps_attempted": int(z_star_meta.get("steps_attempted", 0) or 0),
        "recomb_last_h_u": (
            float(z_star_meta["last_h_u"])
            if z_star_meta.get("last_h_u") is not None and math.isfinite(float(z_star_meta["last_h_u"]))
            else None
        ),
        "recomb_rtol": (
            float(z_star_meta["rtol"])
            if z_star_meta.get("rtol") is not None and math.isfinite(float(z_star_meta["rtol"]))
            else None
        ),
        "recomb_atol": (
            float(z_star_meta["atol"])
            if z_star_meta.get("atol") is not None and math.isfinite(float(z_star_meta["atol"]))
            else None
        ),
        "drag_method": str(z_drag_meta.get("method", drag_method_use)),
        "drag_converged": bool(z_drag_meta.get("converged", True)),
        "drag_steps": int(z_drag_meta.get("steps", 0) or 0),
        "drag_n_eval": int(z_drag_meta.get("n_eval", 0) or 0),
        "cmb_num_method": str(dm_num_meta.get("method", integration_method)),
        "cmb_num_rtol": float(integration_eps_rel),
        "cmb_num_atol": float(integration_eps_abs),
        "cmb_num_n_eval_dm": int(dm_num_meta.get("n_eval", 0) or 0),
        "cmb_num_err_dm": float(dm_num_meta.get("abs_err_est", 0.0) or 0.0),
        "cmb_num_n_eval_rs": int(rs_num_meta.get("n_eval", 0) or 0),
        "cmb_num_err_rs": float(rs_num_meta.get("abs_err_est", 0.0) or 0.0),
        "cmb_num_n_eval_rs_drag": int(z_drag_meta.get("n_eval", 0) or 0),
        "cmb_num_err_rs_drag": (
            float(z_drag_meta["tau_mid_err"])
            if z_drag_meta.get("tau_mid_err") is not None and math.isfinite(float(z_drag_meta["tau_mid_err"]))
            else None
        ),
        # bridge metadata (debug only; not part of the priors vector)
        "bridge_z": float(z_b),
        "bridge_H_ratio": bridge_ratio,
        "Omega_m_early": float(Omega_m_early),
        "Omega_r": float(Omega_r),
        "microphysics_z_star_scale": float(knobs.z_star_scale),
        "microphysics_r_s_scale": float(knobs.r_s_scale),
        "microphysics_r_d_scale": float(knobs.r_d_scale),
    }


def compute_full_history_distance_priors(
    *,
    history_full,
    omega_b_h2: float,
    omega_c_h2: float,
    N_eff: float = 3.046,
    Tcmb_K: float = 2.7255,
    rs_star_calibration: float = 1.0,
    dm_star_calibration: float = 1.0,
    z_star: float | None = None,
    Y_p: float | None = None,
    microphysics: MicrophysicsKnobs | Mapping[str, float] | None = None,
    z_max_rs: float = 1.0e7,
    n_D_M: int = 8192,
    n_r_s: int = 8192,
    integrator: str = "trap",
    integration_eps_abs: float = 1e-10,
    integration_eps_rel: float = 1e-10,
    recombination_method: str = "fit",
    drag_method: str = "eh98",
    recombination_rtol: float = 1e-6,
    recombination_atol: float = 1e-10,
    recombination_max_steps: int = 4096,
) -> Dict[str, float]:
    """Return compressed-CMB prior predictions by integrating a full-range history.

    Diagnostic-only (E2.7): integrates D_M(z*) using the supplied `history_full.H(z)`
    over the full range 0..z*, without any stitch/bridge knob.

    Notes:
    - Uses the same approximate z_* fit as the E1 bridge.
    - Uses a standard c_s(z) model for the sound horizon but integrates using the
      full history H(z).
    - The optional `rs_star_calibration` / `dm_star_calibration` are *diagnostic*
      knobs consistent with the existing E1 tooling.
    """
    if not (omega_b_h2 > 0 and omega_c_h2 >= 0):
        raise ValueError("omega_b_h2 must be >0 and omega_c_h2 must be >=0")
    if not (rs_star_calibration > 0 and math.isfinite(rs_star_calibration)):
        raise ValueError("rs_star_calibration must be finite and > 0")
    if not (dm_star_calibration > 0 and math.isfinite(dm_star_calibration)):
        raise ValueError("dm_star_calibration must be finite and > 0")
    if not (z_max_rs > 0 and math.isfinite(z_max_rs)):
        raise ValueError("z_max_rs must be finite and > 0")
    knobs = knobs_from_dict(microphysics)
    integration_method = _validate_integrator(
        integrator,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
    )
    recomb_method = _validate_recombination_method(recombination_method)
    drag_method_use = _validate_drag_method(drag_method)
    if integration_method == "trap" and int(n_D_M) < 512:
        raise ValueError("n_D_M too small for distance integral")
    if integration_method == "trap" and int(n_r_s) < 512:
        raise ValueError("n_r_s too small for sound-horizon integral")
    if not (math.isfinite(float(recombination_rtol)) and float(recombination_rtol) > 0.0):
        raise ValueError("recombination_rtol must be finite and > 0")
    if not (math.isfinite(float(recombination_atol)) and float(recombination_atol) > 0.0):
        raise ValueError("recombination_atol must be finite and > 0")
    if int(recombination_max_steps) <= 0:
        raise ValueError("recombination_max_steps must be > 0")

    if integration_method == "trap":
        np = _require_numpy()
        _ = np  # keep the requirement explicit (used by helpers)

    H0_si = float(history_full.H(0.0))
    if not (H0_si > 0 and math.isfinite(H0_si)):
        raise ValueError("history_full.H(0) must be positive and finite (SI)")

    H0_km_s_Mpc = float(H0_si) * float(MPC_SI) / 1000.0
    h = float(H0_km_s_Mpc) / 100.0

    omega_g_h2 = omega_gamma_h2_from_Tcmb(float(Tcmb_K))
    omega_r_h2_val = omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(N_eff))
    Omega_r = float(omega_r_h2_val) / (h * h)

    omega_m_h2 = float(omega_b_h2) + float(omega_c_h2)
    Omega_m_early = float(omega_m_h2) / (h * h)
    Omega_lambda_early = 1.0 - float(Omega_m_early) - float(Omega_r)
    if Omega_lambda_early < 0:
        raise ValueError("Derived Omega_lambda_early < 0; adjust inputs")

    y_p_use = 0.245 if Y_p is None else float(Y_p)
    if not (0.0 <= float(y_p_use) < 1.0 and math.isfinite(float(y_p_use))):
        raise ValueError("Y_p must be finite and in [0,1)")

    if z_star is not None:
        z_star_base = float(z_star)
        z_star_meta: Dict[str, float | int | bool | None | str] = {
            "method": "explicit",
            "converged": True,
            "steps": 0,
            "steps_attempted": 0,
            "last_h_u": None,
            "rtol": None,
            "atol": None,
            "max_steps": 0,
        }
    else:
        z_star_base, z_star_meta = compute_z_star(
            method=str(recomb_method),
            omega_b_h2=float(omega_b_h2),
            omega_m_h2=float(omega_m_h2),
            H0_si=float(H0_si),
            Omega_m=float(Omega_m_early),
            Omega_r=float(Omega_r),
            Omega_lambda=float(Omega_lambda_early),
            Tcmb_K=float(Tcmb_K),
            Y_p=float(y_p_use),
            rtol=float(recombination_rtol),
            atol=float(recombination_atol),
            max_steps=int(recombination_max_steps),
        )
    z_star_use = float(z_star_base) * float(knobs.z_star_scale)
    if not (z_star_use > 0.0 and math.isfinite(z_star_use)):
        raise ValueError("Scaled z_star is non-physical")

    z_drag, z_drag_meta = compute_z_drag(
        method=str(drag_method_use),
        omega_b_h2=float(omega_b_h2),
        omega_m_h2=float(omega_m_h2),
        H0_si=float(H0_si),
        Omega_m=float(Omega_m_early),
        Omega_r=float(Omega_r),
        Omega_lambda=float(Omega_lambda_early),
        Tcmb_K=float(Tcmb_K),
        Y_p=float(y_p_use),
        rtol=float(recombination_rtol),
        atol=max(float(recombination_atol), 1e-6),
        max_steps=max(8, int(recombination_max_steps) // 64),
    )

    D_M_star_m_raw, dm_num_meta = _comoving_distance_model_to_z_m(
        z=z_star_use,
        model=history_full,
        n=int(n_D_M),
        integrator=integration_method,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
        return_meta=True,
    )
    if not (D_M_star_m_raw > 0 and math.isfinite(D_M_star_m_raw)):
        raise ValueError("Computed full-history D_M(z_star) is non-physical")
    D_M_star_m = float(D_M_star_m_raw) * float(dm_star_calibration)

    r_s_star_m_raw, rs_num_meta = _sound_horizon_model_from_z_m(
        z=z_star_use,
        model=history_full,
        omega_b_h2=float(omega_b_h2),
        omega_gamma_h2=float(omega_g_h2),
        z_max=float(z_max_rs),
        n=int(n_r_s),
        integrator=integration_method,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
        return_meta=True,
    )
    r_s_star_m = float(r_s_star_m_raw) * float(rs_star_calibration) * float(knobs.r_s_scale)

    theta_star = float(r_s_star_m / D_M_star_m)
    lA = float(math.pi / theta_star)
    R = float(math.sqrt(float(Omega_m_early)) * H0_si * D_M_star_m / float(C_SI))
    rd_mpc_base = float(
        compute_rd_Mpc(
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(N_eff),
            Tcmb_K=float(Tcmb_K),
            method="eisenstein_hu_1998",
        )
    )
    rd_mpc = float(rd_mpc_base) * float(knobs.r_d_scale)

    H_star_si = float(history_full.H(float(z_star_use)))
    D_H_star_Mpc = float((float(C_SI) / float(H_star_si)) / float(MPC_SI)) if (H_star_si > 0 and math.isfinite(H_star_si)) else float("nan")

    out: Dict[str, float] = {
        "theta_star": theta_star,
        "lA": lA,
        "R": R,
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
        "z_star": z_star_use,
        "z_star_base": float(z_star_base),
        "z_drag": float(z_drag),
        "r_s_star_Mpc": float(r_s_star_m / float(MPC_SI)),
        "D_M_star_Mpc": float(D_M_star_m / float(MPC_SI)),
        "D_M_star_Mpc_raw": float(D_M_star_m_raw / float(MPC_SI)),
        "D_H_star_Mpc": float(D_H_star_Mpc),
        "rd_Mpc": rd_mpc,
        "rs_star_calibration": float(rs_star_calibration),
        "rs_star_calibration_applied": bool(float(rs_star_calibration) != 1.0),
        "dm_star_calibration": float(dm_star_calibration),
        "dm_star_calibration_applied": bool(float(dm_star_calibration) != 1.0),
        "dm_star_calibration_reason": (
            "diagnostic-only: D_M(z*) rescaling for compressed-CMB distance priors"
            if float(dm_star_calibration) != 1.0
            else ""
        ),
        "integration_method": str(integration_method),
        "recombination_method": str(z_star_meta.get("method", recomb_method)),
        "recomb_converged": bool(z_star_meta.get("converged", True)),
        "recomb_steps": int(z_star_meta.get("steps", 0) or 0),
        "recomb_steps_attempted": int(z_star_meta.get("steps_attempted", 0) or 0),
        "recomb_last_h_u": (
            float(z_star_meta["last_h_u"])
            if z_star_meta.get("last_h_u") is not None and math.isfinite(float(z_star_meta["last_h_u"]))
            else None
        ),
        "recomb_rtol": (
            float(z_star_meta["rtol"])
            if z_star_meta.get("rtol") is not None and math.isfinite(float(z_star_meta["rtol"]))
            else None
        ),
        "recomb_atol": (
            float(z_star_meta["atol"])
            if z_star_meta.get("atol") is not None and math.isfinite(float(z_star_meta["atol"]))
            else None
        ),
        "drag_method": str(z_drag_meta.get("method", drag_method_use)),
        "drag_converged": bool(z_drag_meta.get("converged", True)),
        "drag_steps": int(z_drag_meta.get("steps", 0) or 0),
        "drag_n_eval": int(z_drag_meta.get("n_eval", 0) or 0),
        "cmb_num_method": str(dm_num_meta.get("method", integration_method)),
        "cmb_num_rtol": float(integration_eps_rel),
        "cmb_num_atol": float(integration_eps_abs),
        "cmb_num_n_eval_dm": int(dm_num_meta.get("n_eval", 0) or 0),
        "cmb_num_err_dm": float(dm_num_meta.get("abs_err_est", 0.0) or 0.0),
        "cmb_num_n_eval_rs": int(rs_num_meta.get("n_eval", 0) or 0),
        "cmb_num_err_rs": float(rs_num_meta.get("abs_err_est", 0.0) or 0.0),
        "cmb_num_n_eval_rs_drag": int(z_drag_meta.get("n_eval", 0) or 0),
        "cmb_num_err_rs_drag": (
            float(z_drag_meta["tau_mid_err"])
            if z_drag_meta.get("tau_mid_err") is not None and math.isfinite(float(z_drag_meta["tau_mid_err"]))
            else None
        ),
        "Omega_m_early": float(Omega_m_early),
        "Omega_r": float(Omega_r),
        "Omega_lambda_early": float(Omega_lambda_early),
        "microphysics_z_star_scale": float(knobs.z_star_scale),
        "microphysics_r_s_scale": float(knobs.r_s_scale),
        "microphysics_r_d_scale": float(knobs.r_d_scale),
    }

    # Optional: carry BBN-clamp metadata if present on the history object.
    z_bbn_clamp = getattr(history_full, "z_bbn_clamp", None)
    if z_bbn_clamp is not None and math.isfinite(float(z_bbn_clamp)):
        out["z_bbn_clamp"] = float(z_bbn_clamp)
        out["bbn_clamp_enabled"] = True
    else:
        out["bbn_clamp_enabled"] = False
    return out


def compute_lcdm_distance_priors(
    *,
    H0_km_s_Mpc: float,
    Omega_m: float,
    omega_b_h2: float,
    omega_c_h2: float,
    N_eff: float = 3.046,
    Tcmb_K: float = 2.7255,
    rs_star_calibration: float = 1.0,
    dm_star_calibration: float = 1.0,
    z_star: float | None = None,
    Y_p: float | None = None,
    microphysics: MicrophysicsKnobs | Mapping[str, float] | None = None,
    integrator: str = "trap",
    integration_eps_abs: float = 1e-10,
    integration_eps_rel: float = 1e-10,
    recombination_method: str = "fit",
    drag_method: str = "eh98",
    recombination_rtol: float = 1e-6,
    recombination_atol: float = 1e-10,
    recombination_max_steps: int = 4096,
) -> Dict[str, float]:
    """Return a dictionary of LCDM compressed-CMB prior predictions.

    Keys include:
    - theta_star
    - lA
    - R
    - omega_b_h2
    - omega_c_h2
    - z_star
    - r_s_star_Mpc
    - D_M_star_Mpc
    - rd_Mpc (from E0 EH98 helper)
    """
    if not (H0_km_s_Mpc > 0 and math.isfinite(H0_km_s_Mpc)):
        raise ValueError("H0_km_s_Mpc must be positive and finite")
    if not (0.0 < Omega_m < 1.0 and math.isfinite(Omega_m)):
        raise ValueError("Omega_m must be in (0,1)")
    if not (omega_b_h2 > 0 and omega_c_h2 >= 0):
        raise ValueError("omega_b_h2 must be >0 and omega_c_h2 must be >=0")
    if not (rs_star_calibration > 0 and math.isfinite(rs_star_calibration)):
        raise ValueError("rs_star_calibration must be finite and > 0")
    if not (dm_star_calibration > 0 and math.isfinite(dm_star_calibration)):
        raise ValueError("dm_star_calibration must be finite and > 0")
    knobs = knobs_from_dict(microphysics)
    integration_method = _validate_integrator(
        integrator,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
    )
    recomb_method = _validate_recombination_method(recombination_method)
    drag_method_use = _validate_drag_method(drag_method)
    if not (math.isfinite(float(recombination_rtol)) and float(recombination_rtol) > 0.0):
        raise ValueError("recombination_rtol must be finite and > 0")
    if not (math.isfinite(float(recombination_atol)) and float(recombination_atol) > 0.0):
        raise ValueError("recombination_atol must be finite and > 0")
    if int(recombination_max_steps) <= 0:
        raise ValueError("recombination_max_steps must be > 0")
    if integration_method == "trap":
        np = _require_numpy()
        _ = np

    h = float(H0_km_s_Mpc) / 100.0
    H0_si = H0_to_SI(float(H0_km_s_Mpc))
    omega_g_h2 = omega_gamma_h2_from_Tcmb(float(Tcmb_K))
    omega_r_h2_val = omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(N_eff))
    Omega_r = float(omega_r_h2_val) / (h * h)

    # Keep flatness in the late-time sense while adding radiation.
    Omega_lambda = 1.0 - float(Omega_m) - float(Omega_r)
    if Omega_lambda < 0:
        raise ValueError("Derived Omega_lambda < 0; adjust inputs")

    omega_m_h2 = float(omega_b_h2) + float(omega_c_h2)
    y_p_use = 0.245 if Y_p is None else float(Y_p)
    if not (0.0 <= float(y_p_use) < 1.0 and math.isfinite(float(y_p_use))):
        raise ValueError("Y_p must be finite and in [0,1)")

    if z_star is not None:
        z_star_base = float(z_star)
        z_star_meta: Dict[str, float | int | bool | None | str] = {
            "method": "explicit",
            "converged": True,
            "steps": 0,
            "steps_attempted": 0,
            "last_h_u": None,
            "rtol": None,
            "atol": None,
            "max_steps": 0,
        }
    else:
        z_star_base, z_star_meta = compute_z_star(
            method=str(recomb_method),
            omega_b_h2=float(omega_b_h2),
            omega_m_h2=float(omega_m_h2),
            H0_si=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_r=float(Omega_r),
            Omega_lambda=float(Omega_lambda),
            Tcmb_K=float(Tcmb_K),
            Y_p=float(y_p_use),
            rtol=float(recombination_rtol),
            atol=float(recombination_atol),
            max_steps=int(recombination_max_steps),
        )
    z_star_use = float(z_star_base) * float(knobs.z_star_scale)
    if not (z_star_use > 0.0 and math.isfinite(z_star_use)):
        raise ValueError("Scaled z_star is non-physical")

    z_drag, z_drag_meta = compute_z_drag(
        method=str(drag_method_use),
        omega_b_h2=float(omega_b_h2),
        omega_m_h2=float(omega_m_h2),
        H0_si=float(H0_si),
        Omega_m=float(Omega_m),
        Omega_r=float(Omega_r),
        Omega_lambda=float(Omega_lambda),
        Tcmb_K=float(Tcmb_K),
        Y_p=float(y_p_use),
        rtol=float(recombination_rtol),
        atol=max(float(recombination_atol), 1e-6),
        max_steps=max(8, int(recombination_max_steps) // 64),
    )

    D_M_star_m_raw, dm_num_meta = _comoving_distance_to_z_m(
        z=z_star_use,
        H0_si=H0_si,
        omega_m=float(Omega_m),
        omega_r=float(Omega_r),
        omega_lambda=float(Omega_lambda),
        integrator=integration_method,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
        return_meta=True,
    )
    D_M_star_m = float(D_M_star_m_raw) * float(dm_star_calibration)

    r_s_star_m_raw, rs_num_meta = _sound_horizon_from_z_m(
        z=z_star_use,
        H0_si=H0_si,
        omega_b_h2=float(omega_b_h2),
        omega_gamma_h2=float(omega_g_h2),
        omega_m=float(Omega_m),
        omega_r=float(Omega_r),
        omega_lambda=float(Omega_lambda),
        integrator=integration_method,
        eps_abs=float(integration_eps_abs),
        eps_rel=float(integration_eps_rel),
        return_meta=True,
    )
    # Stopgap calibration: this is an effective correction for the bridge-level
    # z_star fit + r_s(z*) integral accuracy. It must only be applied to r_s at
    # recombination (z*), and must not affect r_d / BAO.
    #
    # TODO(v10+): replace this with a higher-precision early-time engine or an
    # explicitly-derived freeze-frame treatment of recombination.
    r_s_star_m = float(r_s_star_m_raw) * float(rs_star_calibration) * float(knobs.r_s_scale)

    theta_star = float(r_s_star_m / D_M_star_m)
    lA = float(math.pi / theta_star)
    R = float(math.sqrt(float(Omega_m)) * H0_si * D_M_star_m / float(C_SI))
    rd_mpc_base = float(
        compute_rd_Mpc(
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(N_eff),
            Tcmb_K=float(Tcmb_K),
            method="eisenstein_hu_1998",
        )
    )
    rd_mpc = float(rd_mpc_base) * float(knobs.r_d_scale)

    return {
        "theta_star": theta_star,
        "lA": lA,
        "R": R,
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
        "z_star": z_star_use,
        "z_star_base": float(z_star_base),
        "z_drag": float(z_drag),
        "r_s_star_Mpc": float(r_s_star_m / float(MPC_SI)),
        "D_M_star_Mpc": float(D_M_star_m / float(MPC_SI)),
        "D_M_star_Mpc_raw": float(D_M_star_m_raw / float(MPC_SI)),
        "rd_Mpc": rd_mpc,
        "rs_star_calibration": float(rs_star_calibration),
        "rs_star_calibration_applied": bool(float(rs_star_calibration) != 1.0),
        "dm_star_calibration": float(dm_star_calibration),
        "dm_star_calibration_applied": bool(float(dm_star_calibration) != 1.0),
        "dm_star_calibration_reason": (
            "diagnostic-only: D_M(z*) rescaling for compressed-CMB distance priors"
            if float(dm_star_calibration) != 1.0
            else ""
        ),
        "integration_method": str(integration_method),
        "recombination_method": str(z_star_meta.get("method", recomb_method)),
        "recomb_converged": bool(z_star_meta.get("converged", True)),
        "recomb_steps": int(z_star_meta.get("steps", 0) or 0),
        "recomb_steps_attempted": int(z_star_meta.get("steps_attempted", 0) or 0),
        "recomb_last_h_u": (
            float(z_star_meta["last_h_u"])
            if z_star_meta.get("last_h_u") is not None and math.isfinite(float(z_star_meta["last_h_u"]))
            else None
        ),
        "recomb_rtol": (
            float(z_star_meta["rtol"])
            if z_star_meta.get("rtol") is not None and math.isfinite(float(z_star_meta["rtol"]))
            else None
        ),
        "recomb_atol": (
            float(z_star_meta["atol"])
            if z_star_meta.get("atol") is not None and math.isfinite(float(z_star_meta["atol"]))
            else None
        ),
        "drag_method": str(z_drag_meta.get("method", drag_method_use)),
        "drag_converged": bool(z_drag_meta.get("converged", True)),
        "drag_steps": int(z_drag_meta.get("steps", 0) or 0),
        "drag_n_eval": int(z_drag_meta.get("n_eval", 0) or 0),
        "cmb_num_method": str(dm_num_meta.get("method", integration_method)),
        "cmb_num_rtol": float(integration_eps_rel),
        "cmb_num_atol": float(integration_eps_abs),
        "cmb_num_n_eval_dm": int(dm_num_meta.get("n_eval", 0) or 0),
        "cmb_num_err_dm": float(dm_num_meta.get("abs_err_est", 0.0) or 0.0),
        "cmb_num_n_eval_rs": int(rs_num_meta.get("n_eval", 0) or 0),
        "cmb_num_err_rs": float(rs_num_meta.get("abs_err_est", 0.0) or 0.0),
        "cmb_num_n_eval_rs_drag": int(z_drag_meta.get("n_eval", 0) or 0),
        "cmb_num_err_rs_drag": (
            float(z_drag_meta["tau_mid_err"])
            if z_drag_meta.get("tau_mid_err") is not None and math.isfinite(float(z_drag_meta["tau_mid_err"]))
            else None
        ),
        "microphysics_z_star_scale": float(knobs.z_star_scale),
        "microphysics_r_s_scale": float(knobs.r_s_scale),
        "microphysics_r_d_scale": float(knobs.r_d_scale),
    }
