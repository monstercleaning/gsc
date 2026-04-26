#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2 prototype:
Action -> scaling solution -> redshift drift.

This script demonstrates that the phenomenological power law
    H(z) = H0 (1+z)^p
can emerge as an attractor from a minimal canonical scalar-field action
with an exponential potential:
    V(ϕ) = V0 exp(-λ ϕ / M_P)

For a scalar-dominated attractor:
    w = λ^2/3 - 1
    p = λ^2/2

It then computes the redshift drift observable:
    z_dot = H0 (1+z) - H(z)
and expresses it as a spectroscopic velocity drift:
    v_dot = c z_dot/(1+z)

Units:
- H0 is set to 70 km/s/Mpc in SI (s^-1).
- v_dot is output in cm/s per year.

Outputs:
- phase2_action_redshift_drift.png
- phase2_action_attractor.png
- phase2_action_mapping.png
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp


# -----------------------------
# Constants / conversions
# -----------------------------
C = 299792458.0  # m/s
MPC = 3.085677581491367e22  # meters
SEC_PER_YEAR = 365.25 * 24 * 3600

H0_KM_S_MPC = 70.0
H0_SI = (H0_KM_S_MPC * 1000.0) / MPC  # s^-1


@dataclass(frozen=True)
class LCDMParams:
    Omega_m: float = 0.3
    Omega_L: float = 0.7


def H_lcdm(z: np.ndarray, params: LCDMParams) -> np.ndarray:
    """Flat ΛCDM H(z) (ignore radiation for z<=5 demonstrations)."""
    return H0_SI * np.sqrt(params.Omega_m * (1.0 + z) ** 3 + params.Omega_L)


def z_dot_from_H(z: np.ndarray, H_of_z: np.ndarray) -> np.ndarray:
    """Sandage–Loeb redshift drift formula (same as used in v10.1 scripts)."""
    return H0_SI * (1.0 + z) - H_of_z


def vdot_cm_s_yr(z: np.ndarray, z_dot: np.ndarray) -> np.ndarray:
    """Convert z-dot [1/s] to spectroscopic velocity drift [cm/s/yr]."""
    vdot_m_s_per_s = C * z_dot / (1.0 + z)
    return vdot_m_s_per_s * SEC_PER_YEAR * 100.0


# -----------------------------
# Action-derived model
# -----------------------------
def H_action_exponential(z: np.ndarray, lam: float) -> np.ndarray:
    """
    For a canonical scalar with V=V0 exp(-λϕ/Mp) in the scalar-dominated attractor:
        H(z) = H0 (1+z)^(λ^2/2)
    """
    p = lam ** 2 / 2.0
    return H0_SI * (1.0 + z) ** p


def x_prime(N: float, x: float, lam: float) -> float:
    """
    Autonomous equation for x = ϕ̇/(√6 H Mp) in a scalar-only universe with exponential potential.
    Derived directly from the action (see Copeland–Liddle–Wands 1998).
    """
    return -3.0 * x + math.sqrt(3.0 / 2.0) * lam * (1.0 - x**2) + 3.0 * x**3


def integrate_attractor(lam: float, x0: float, N_span=(-10.0, 0.0), num=2000) -> tuple[np.ndarray, np.ndarray]:
    """Integrate x(N) to show convergence to x* = λ/√6."""
    sol = solve_ivp(
        fun=lambda N, y: [x_prime(N, y[0], lam)],
        t_span=N_span,
        y0=[x0],
        dense_output=True,
        max_step=0.02,
    )
    N = np.linspace(N_span[0], N_span[1], num)
    x = sol.sol(N)[0]
    return N, x


def main() -> None:
    outdir = Path(__file__).resolve().parent.parent / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    # Redshift grid
    z = np.linspace(0.0, 5.0, 501)

    # ΛCDM baseline
    lcdm = LCDMParams()
    H_LCDM = H_lcdm(z, lcdm)
    v_LCDM = vdot_cm_s_yr(z, z_dot_from_H(z, H_LCDM))

    # Action model curves for multiple λ (chosen < √2 so p<1)
    lambdas: List[float] = [0.8, 1.0, 1.2, 1.35]
    action_curves: Dict[float, np.ndarray] = {}
    for lam in lambdas:
        H = H_action_exponential(z, lam)
        action_curves[lam] = vdot_cm_s_yr(z, z_dot_from_H(z, H))

    # ---- Plot 1: redshift drift
    plt.figure()
    plt.plot(z, v_LCDM, label="ΛCDM (Ωm=0.3, ΩΛ=0.7)")
    for lam in lambdas:
        p = lam**2 / 2.0
        plt.plot(z, action_curves[lam], label=f"GSC-Action: λ={lam:.2f} (p={p:.3f})")
    plt.axhline(0.0, linewidth=1)
    plt.xlabel("Redshift z")
    plt.ylabel("Spectroscopic velocity drift Δv̇ [cm/s/yr]")
    plt.title("Redshift drift from an exponential-potential action (Phase 2 prototype)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "phase2_action_redshift_drift.png", dpi=200)
    plt.close()

    # ---- Plot 2: attractor convergence
    lam = 1.0
    x_star = lam / math.sqrt(6.0)
    init_conditions = [0.0, 0.3, 0.8, -0.3]
    plt.figure()
    for x0 in init_conditions:
        N, x = integrate_attractor(lam=lam, x0=x0)
        plt.plot(N, x, label=f"x0={x0:+.1f}")
    plt.axhline(x_star, linestyle="--", linewidth=1, label=f"attractor x* = λ/√6 = {x_star:.3f}")
    plt.xlabel("e-fold N = ln a")
    plt.ylabel("x = ϕ̇/(√6 H M_P)")
    plt.title("Attractor behavior from the action (exponential potential, λ=1)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "phase2_action_attractor.png", dpi=200)
    plt.close()

    # ---- Plot 3: mapping between λ and (p,w)
    lam_grid = np.linspace(0.1, 1.4, 200)
    p_grid = lam_grid**2 / 2.0
    w_grid = lam_grid**2 / 3.0 - 1.0
    plt.figure()
    plt.plot(lam_grid, p_grid, label="p = λ²/2")
    plt.plot(lam_grid, w_grid, label="w = λ²/3 − 1")
    plt.axhline(-1.0 / 3.0, linestyle="--", linewidth=1, label="w = −1/3 (acceleration threshold)")
    plt.axvline(math.sqrt(2.0), linestyle="--", linewidth=1, label="λ = √2 (p=1)")
    plt.xlabel("Exponential slope parameter λ")
    plt.ylabel("Derived parameter value")
    plt.title("Mapping between action parameter λ and phenomenological p, w")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "phase2_action_mapping.png", dpi=200)
    plt.close()

    print("Generated:")
    print(" - phase2_action_redshift_drift.png")
    print(" - phase2_action_attractor.png")
    print(" - phase2_action_mapping.png")


if __name__ == "__main__":
    main()
