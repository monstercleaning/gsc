"""
Phase 2 diagnostic: distance-ladder vs. redshift-drift consistency.

This script compares a simple action-motivated power-law H(z) = H0 (1+z)^p
(typical of scalar-field solutions with exponential potentials) against a
reference flat LambdaCDM model.

Outputs (saved to ../outputs):
- phase2_action_H_over_H0.png
- phase2_action_distance_modulus_residual.png
- phase2_action_drift_velocity.png
- phase2_action_drift_samples.csv
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import quad


# -----------------------------
# Cosmology helpers
# -----------------------------

C_KM_S = 299792.458  # km/s
C_CM_S = C_KM_S * 1e5

MPC_KM = 3.085677581e19  # km
SEC_PER_YR = 31557600.0  # Julian year


def H0_to_per_year(H0_km_s_Mpc: float) -> float:
    """Convert H0 from km/s/Mpc to 1/yr."""
    H0_per_s = H0_km_s_Mpc / MPC_KM
    return H0_per_s * SEC_PER_YR


def E_lcdm(z: float, Om: float = 0.3, Ol: float = 0.7) -> float:
    return math.sqrt(Om * (1.0 + z) ** 3 + Ol)


def H_lcdm(z: float, H0_km_s_Mpc: float = 70.0, Om: float = 0.3, Ol: float = 0.7) -> float:
    return H0_km_s_Mpc * E_lcdm(z, Om, Ol)


def H_powerlaw(z: float, H0_km_s_Mpc: float = 70.0, p: float = 0.5) -> float:
    return H0_km_s_Mpc * (1.0 + z) ** p


def comoving_distance_Mpc(z: float, H_func) -> float:
    """Line-of-sight comoving distance in Mpc: Dc = c * ∫ dz/H(z)."""
    # H in km/s/Mpc => c/H yields Mpc
    integrand = lambda zp: C_KM_S / H_func(zp)
    val, _ = quad(integrand, 0.0, z, epsabs=1e-10, epsrel=1e-10, limit=200)
    return val


def luminosity_distance_Mpc(z: float, H_func) -> float:
    return (1.0 + z) * comoving_distance_Mpc(z, H_func)


def distance_modulus(dL_Mpc: float) -> float:
    # mu = 5 log10(dL / 10 pc) = 5 log10(dL/Mpc) + 25
    return 5.0 * math.log10(dL_Mpc) + 25.0


def main() -> None:
    outdir = Path(__file__).resolve().parent.parent / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    H0 = 70.0
    Om, Ol = 0.3, 0.7
    p = 0.5  # corresponds to lambda=1 in scalar exponential potential solutions

    z = np.linspace(0.0, 5.0, 401)[1:]  # exclude 0 to avoid log issues

    H_LCDM = np.array([H_lcdm(zi, H0, Om, Ol) for zi in z])
    H_PL = np.array([H_powerlaw(zi, H0, p) for zi in z])

    # Distance modulus residual
    mu_LCDM = np.array([
        distance_modulus(luminosity_distance_Mpc(zi, lambda zp: H_lcdm(zp, H0, Om, Ol)))
        for zi in z
    ])
    mu_PL = np.array([
        distance_modulus(luminosity_distance_Mpc(zi, lambda zp: H_powerlaw(zp, H0, p)))
        for zi in z
    ])
    dmu = mu_PL - mu_LCDM

    # Plot H(z) and mu residual
    plt.figure()
    plt.plot(z, H_LCDM / H0, label="LCDM: H(z)/H0")
    plt.plot(z, H_PL / H0, label=f"Power-law: p={p:.2f}")
    plt.xlabel("z")
    plt.ylabel("H(z)/H0")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "phase2_action_H_over_H0.png", dpi=200)
    plt.close()

    plt.figure()
    plt.plot(z, dmu)
    plt.axhline(0.0, linewidth=1)
    plt.xlabel("z")
    plt.ylabel("Δμ = μ_powerlaw − μ_LCDM  [mag]")
    plt.tight_layout()
    plt.savefig(outdir / "phase2_action_distance_modulus_residual.png", dpi=200)
    plt.close()

    # Redshift drift as velocity drift (cm/s per year)
    H0_yr = H0_to_per_year(H0)
    Hz_lcdm_yr = np.array([H0_to_per_year(H_lcdm(zi, H0, Om, Ol)) for zi in z])
    Hz_pl_yr = np.array([H0_to_per_year(H_powerlaw(zi, H0, p)) for zi in z])

    # z_dot = H0*(1+z) - H(z)
    z_dot_lcdm = H0_yr * (1.0 + z) - Hz_lcdm_yr
    z_dot_pl = H0_yr * (1.0 + z) - Hz_pl_yr

    # v_dot = c * z_dot /(1+z)
    v_dot_lcdm = C_CM_S * z_dot_lcdm / (1.0 + z)
    v_dot_pl = C_CM_S * z_dot_pl / (1.0 + z)

    plt.figure()
    plt.plot(z, v_dot_lcdm, label="LCDM")
    plt.plot(z, v_dot_pl, label=f"Power-law p={p:.2f}")
    plt.axhline(0.0, linewidth=1)
    plt.xlabel("z")
    plt.ylabel("Velocity drift  dv/dt0  [cm/s/yr]")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "phase2_action_drift_velocity.png", dpi=200)
    plt.close()

    # Save a small numeric summary
    z_probe = [0.5, 1.0, 2.0, 3.0, 4.0]
    rows = []
    for zi in z_probe:
        v1 = float(C_CM_S * (H0_yr*(1+zi) - H0_to_per_year(H_lcdm(zi, H0, Om, Ol))) / (1+zi))
        v2 = float(C_CM_S * (H0_yr*(1+zi) - H0_to_per_year(H_powerlaw(zi, H0, p))) / (1+zi))
        rows.append((zi, v1, v2))

    txt = "z, dv/dt0_LCDM [cm/s/yr], dv/dt0_powerlaw [cm/s/yr]\n"
    for zi, v1, v2 in rows:
        txt += f"{zi:.2f}, {v1:.6f}, {v2:.6f}\n"
    (outdir / "phase2_action_drift_samples.csv").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
