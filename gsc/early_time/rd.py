"""Early-time drag-scale helpers (E0 rd-only closure).

This module provides a minimal, deterministic `r_d` computation for the
v11.0.0 Option-2 bridge. The default method is a standard closed-form
Eisenstein & Hu (1998) approximation, implemented with stdlib `math` only.
"""

from __future__ import annotations

import math
from typing import Tuple

from ..measurement_model import MPC_SI


_C_KM_S = 299_792.458
_NEFF_FACTOR = 0.22710731766


def omega_gamma_h2_from_Tcmb(Tcmb_K: float = 2.7255) -> float:
    """Photon physical density omega_gamma = Omega_gamma * h^2.

    Uses the standard approximation:
      omega_gamma = 2.469e-5 * (Tcmb / 2.7255)^4
    """
    if not (Tcmb_K > 0 and math.isfinite(Tcmb_K)):
        raise ValueError("Tcmb_K must be positive and finite")
    return 2.469e-5 * (Tcmb_K / 2.7255) ** 4


def omega_r_h2(*, Tcmb_K: float = 2.7255, N_eff: float = 3.046) -> float:
    """Radiation physical density omega_r = omega_gamma * (1 + 0.2271 N_eff)."""
    if not (N_eff >= 0 and math.isfinite(N_eff)):
        raise ValueError("N_eff must be finite and non-negative")
    omega_gamma = omega_gamma_h2_from_Tcmb(Tcmb_K)
    return omega_gamma * (1.0 + _NEFF_FACTOR * N_eff)


def z_drag_eisenstein_hu(*, omega_m_h2: float, omega_b_h2: float) -> float:
    """Drag epoch z_d from Eisenstein & Hu (1998) fitting formula."""
    if not (omega_m_h2 > 0 and math.isfinite(omega_m_h2)):
        raise ValueError("omega_m_h2 must be positive and finite")
    if not (omega_b_h2 > 0 and math.isfinite(omega_b_h2)):
        raise ValueError("omega_b_h2 must be positive and finite")

    b1 = 0.313 * (omega_m_h2 ** -0.419) * (1.0 + 0.607 * (omega_m_h2 ** 0.674))
    b2 = 0.238 * (omega_m_h2 ** 0.223)
    z_d = (
        1291.0
        * (omega_m_h2 ** 0.251)
        / (1.0 + 0.659 * (omega_m_h2 ** 0.828))
        * (1.0 + b1 * (omega_b_h2 ** b2))
    )
    if not (z_d > 0 and math.isfinite(z_d)):
        raise ValueError("Computed z_drag is non-physical")
    return z_d


def _rd_eisenstein_hu_1998_Mpc(
    *,
    omega_b_h2: float,
    omega_c_h2: float,
    N_eff: float,
    Tcmb_K: float,
) -> float:
    """Closed-form E&H 1998 drag-scale approximation in comoving Mpc."""
    omega_m_h2 = omega_b_h2 + omega_c_h2
    omega_gamma_h2 = omega_gamma_h2_from_Tcmb(Tcmb_K=Tcmb_K)
    omega_r_h2_val = omega_r_h2(Tcmb_K=Tcmb_K, N_eff=N_eff)

    z_eq = omega_m_h2 / omega_r_h2_val - 1.0
    if not (z_eq > 0 and math.isfinite(z_eq)):
        raise ValueError("Computed z_eq is non-physical")

    # R(z) = 3 rho_b / (4 rho_gamma)
    r_eq = (3.0 / 4.0) * (omega_b_h2 / omega_gamma_h2) / (1.0 + z_eq)

    z_d = z_drag_eisenstein_hu(omega_m_h2=omega_m_h2, omega_b_h2=omega_b_h2)
    if not (800.0 <= z_d <= 1500.0):
        raise ValueError(f"z_drag out of expected range [800,1500]: {z_d:.6g}")

    r_d = (3.0 / 4.0) * (omega_b_h2 / omega_gamma_h2) / (1.0 + z_d)

    # k_eq = (100/c) * sqrt(2) * omega_m / sqrt(omega_r)  [1/Mpc]
    k_eq = (100.0 / _C_KM_S) * math.sqrt(2.0) * omega_m_h2 / math.sqrt(omega_r_h2_val)
    if not (k_eq > 0 and math.isfinite(k_eq)):
        raise ValueError("Computed k_eq is non-physical")

    log_arg = (math.sqrt(1.0 + r_d) + math.sqrt(r_d + r_eq)) / (1.0 + math.sqrt(r_eq))
    if not (log_arg > 1.0 and math.isfinite(log_arg)):
        raise ValueError("Invalid logarithm argument in EH98 r_d computation")

    rd_mpc = (2.0 / (3.0 * k_eq)) * math.sqrt(6.0 / r_eq) * math.log(log_arg)
    if not (rd_mpc > 0 and math.isfinite(rd_mpc)):
        raise ValueError("Computed r_d is non-physical")
    return rd_mpc


def compute_rd_Mpc(
    omega_b_h2: float,
    omega_c_h2: float,
    *,
    N_eff: float = 3.046,
    Neff: float | None = None,
    Tcmb_K: float = 2.7255,
    method: str = "eisenstein_hu_1998",
) -> float:
    """Compute r_d (comoving drag sound horizon) in Mpc.

    Parameters are physical densities (`omega_x_h2`).
    In E0 we expose only the minimal set needed for a stable rd-only closure.
    """
    method_norm = str(method).strip().lower()
    if method_norm not in {"eisenstein_hu_1998", "eh1998", "ehu1998"}:
        raise ValueError(f"Unsupported rd method: {method!r}")
    if not (omega_b_h2 > 0 and math.isfinite(omega_b_h2)):
        raise ValueError("omega_b_h2 must be positive and finite")
    if not (omega_c_h2 >= 0 and math.isfinite(omega_c_h2)):
        raise ValueError("omega_c_h2 must be finite and non-negative")

    # Backward-compatible alias used in some CLI/docs examples.
    if Neff is not None:
        if not math.isfinite(Neff):
            raise ValueError("Neff must be finite")
        if abs(float(N_eff) - float(Neff)) > 1e-12:
            raise ValueError("Both N_eff and Neff provided with different values")
        N_eff = float(Neff)

    return _rd_eisenstein_hu_1998_Mpc(
        omega_b_h2=omega_b_h2,
        omega_c_h2=omega_c_h2,
        N_eff=N_eff,
        Tcmb_K=Tcmb_K,
    )


def rd_and_zdrag(
    omega_b_h2: float,
    omega_c_h2: float,
    *,
    N_eff: float = 3.046,
    Tcmb_K: float = 2.7255,
    method: str = "eisenstein_hu_1998",
) -> Tuple[float, float]:
    """Return `(r_d_Mpc, z_drag)` for diagnostics/manifests."""
    omega_m_h2 = omega_b_h2 + omega_c_h2
    z_d = z_drag_eisenstein_hu(omega_m_h2=omega_m_h2, omega_b_h2=omega_b_h2)
    rd = compute_rd_Mpc(
        omega_b_h2=omega_b_h2,
        omega_c_h2=omega_c_h2,
        N_eff=N_eff,
        Tcmb_K=Tcmb_K,
        method=method,
    )
    return rd, z_d
