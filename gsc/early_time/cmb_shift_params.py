"""CMB shift-parameter facade for Phase 2 early-universe scaffolding.

This module provides first-class, stable entry points for compressed CMB
observables (theta*, lA, R) while reusing the existing lightweight E1 bridge
calculations.
"""

from __future__ import annotations

from typing import Dict, Mapping

from .cmb_distance_priors import (
    _RS_STAR_CALIB_CHW2018,
    compute_bridged_distance_priors,
    compute_full_history_distance_priors,
    compute_lcdm_distance_priors,
    z_star_hu_sugiyama,
)


def compute_lcdm_shift_params(
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
    microphysics: Mapping[str, float] | None = None,
    integrator: str = "trap",
    integration_eps_abs: float = 1e-10,
    integration_eps_rel: float = 1e-10,
    recombination_method: str = "fit",
    drag_method: str = "eh98",
    recombination_rtol: float = 1e-6,
    recombination_atol: float = 1e-10,
    recombination_max_steps: int = 4096,
) -> Dict[str, float]:
    """Return LCDM compressed-CMB shift parameters and metadata."""
    return compute_lcdm_distance_priors(
        H0_km_s_Mpc=float(H0_km_s_Mpc),
        Omega_m=float(Omega_m),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(N_eff),
        Tcmb_K=float(Tcmb_K),
        rs_star_calibration=float(rs_star_calibration),
        dm_star_calibration=float(dm_star_calibration),
        z_star=None if z_star is None else float(z_star),
        Y_p=None if Y_p is None else float(Y_p),
        microphysics=None if microphysics is None else dict(microphysics),
        integrator=str(integrator),
        integration_eps_abs=float(integration_eps_abs),
        integration_eps_rel=float(integration_eps_rel),
        recombination_method=str(recombination_method),
        drag_method=str(drag_method),
        recombination_rtol=float(recombination_rtol),
        recombination_atol=float(recombination_atol),
        recombination_max_steps=int(recombination_max_steps),
    )


def compute_bridged_shift_params(
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
    microphysics: Mapping[str, float] | None = None,
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
    """Return bridged compressed-CMB shift parameters and metadata."""
    return compute_bridged_distance_priors(
        model=model,
        z_bridge=float(z_bridge),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(N_eff),
        Tcmb_K=float(Tcmb_K),
        rs_star_calibration=float(rs_star_calibration),
        dm_star_calibration=float(dm_star_calibration),
        z_star=None if z_star is None else float(z_star),
        Y_p=None if Y_p is None else float(Y_p),
        microphysics=None if microphysics is None else dict(microphysics),
        D_M_model_to_z_bridge_m=None if D_M_model_to_z_bridge_m is None else float(D_M_model_to_z_bridge_m),
        integrator=str(integrator),
        integration_eps_abs=float(integration_eps_abs),
        integration_eps_rel=float(integration_eps_rel),
        recombination_method=str(recombination_method),
        drag_method=str(drag_method),
        recombination_rtol=float(recombination_rtol),
        recombination_atol=float(recombination_atol),
        recombination_max_steps=int(recombination_max_steps),
    )


def compute_full_history_shift_params(
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
    microphysics: Mapping[str, float] | None = None,
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
    """Return full-history compressed-CMB shift parameters and metadata."""
    return compute_full_history_distance_priors(
        history_full=history_full,
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(N_eff),
        Tcmb_K=float(Tcmb_K),
        rs_star_calibration=float(rs_star_calibration),
        dm_star_calibration=float(dm_star_calibration),
        z_star=None if z_star is None else float(z_star),
        Y_p=None if Y_p is None else float(Y_p),
        microphysics=None if microphysics is None else dict(microphysics),
        z_max_rs=float(z_max_rs),
        n_D_M=int(n_D_M),
        n_r_s=int(n_r_s),
        integrator=str(integrator),
        integration_eps_abs=float(integration_eps_abs),
        integration_eps_rel=float(integration_eps_rel),
        recombination_method=str(recombination_method),
        drag_method=str(drag_method),
        recombination_rtol=float(recombination_rtol),
        recombination_atol=float(recombination_atol),
        recombination_max_steps=int(recombination_max_steps),
    )


__all__ = [
    "_RS_STAR_CALIB_CHW2018",
    "compute_lcdm_shift_params",
    "compute_bridged_shift_params",
    "compute_full_history_shift_params",
    "z_star_hu_sugiyama",
]
