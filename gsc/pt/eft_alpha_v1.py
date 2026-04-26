"""SigmaTensor-v1 EFT-alpha diagnostic mapping (Phase-3 scaffolding).

This module exports a Bellini-Sawicki-style subset for canonical quintessence
in GR, based on background-only trajectories:

- alpha_M = 0
- alpha_B = 0
- alpha_T = 0
- alpha_K = u^2, where u=dphi/d(ln a)
- c_s2 = 1

For canonical scalar fields, alpha_K also satisfies:
alpha_K = 3 * Omega_phi * (1 + w_phi)
which is included as a cross-check array.
"""

from __future__ import annotations

from typing import Dict, List

from ..theory.sigmatensor_v1 import SigmaTensorV1Background


def sigmatensor_v1_eft_alphas(bg: SigmaTensorV1Background) -> Dict[str, List[float]]:
    """Return deterministic EFT-alpha arrays aligned with ``bg.z_grid``."""
    n = len(bg.z_grid)
    u = [float(x) for x in bg.u_grid]
    omphi = [float(x) for x in bg.Omphi_grid]
    wphi = [float(x) for x in bg.wphi_grid]
    if not (len(u) == n and len(omphi) == n and len(wphi) == n):
        raise ValueError("background arrays must have equal lengths")

    alpha_k = [ui * ui for ui in u]
    alpha_k_cross = [3.0 * om * (1.0 + w) for om, w in zip(omphi, wphi)]
    zeros = [0.0] * n
    cs2 = [1.0] * n
    return {
        "alpha_K": alpha_k,
        "alpha_K_from_Omega_phi_w_phi": alpha_k_cross,
        "alpha_M": list(zeros),
        "alpha_B": list(zeros),
        "alpha_T": list(zeros),
        "c_s2": cs2,
    }


__all__ = [
    "sigmatensor_v1_eft_alphas",
]

