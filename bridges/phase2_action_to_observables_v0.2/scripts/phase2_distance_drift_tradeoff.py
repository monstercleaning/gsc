#!/usr/bin/env python3
"""Phase 2 prototype: trade-off between luminosity-distance mimicry and always-positive redshift drift.

This script:
1) defines a reference flat LCDM curve (H0, Om, Ol)
2) defines an always-positive-drift toy family H(z) = H0 (1+z)^{p(z)} with p(z)=1 - A exp(-z/z0)
3) fits (A,z0) to minimize relative luminosity-distance error vs LCDM over z∈[0.05,2.5]
4) produces two plots:
   - relative difference in d_L(z)
   - redshift-drift velocity shift Δv over 10 years for LCDM and several toy models

NOTE: This is NOT derived from the GSC RG action; it is a feasibility scan for Phase 2.
"""

import os, math
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import scipy.optimize as opt

# -----------------
# Constants
# -----------------
c_kms = 299792.458
H0_km_s_Mpc = 67.4
Om, Ol = 0.315, 0.685
Mpc_km = 3.085677581e19
H0_s = H0_km_s_Mpc / Mpc_km
sec_per_year = 365.25*24*3600
T10 = 10*sec_per_year


# -----------------
# Runtime controls
# -----------------
DO_OPTIMIZE = False  # set True to run Nelder-Mead fit (slow)
A_PRESET = 0.621
Z0_PRESET = 0.680
# -----------------
# Reference LCDM
# -----------------
def H_lcdm_km_s_Mpc(z: float) -> float:
    return H0_km_s_Mpc*math.sqrt(Om*(1+z)**3 + Ol)

def Dc_numeric(z: float, H_func, n:int=1500) -> float:
    zs = np.linspace(0,z,n+1)
    Hz = np.array([H_func(float(zz)) for zz in zs])
    return c_kms*np.trapz(1/Hz, zs)

def dL_flat(z: float, H_func) -> float:
    return (1+z)*Dc_numeric(z, H_func)

def dzdt_lcdm_si(z: float) -> float:
    return H0_s*(1+z) - (H_lcdm_km_s_Mpc(z)/Mpc_km)

# -----------------
# Positive-drift toy model: H(z)=H0(1+z)^{p(z)},  p(z)=1 - A exp(-z/z0)
# -----------------
def p_run(z: float, A: float, z0: float) -> float:
    return 1 - A*math.exp(-z/z0)

def make_H_prun(A: float, z0: float):
    def H(z):
        pz = p_run(z, A, z0)
        return H0_km_s_Mpc*(1+z)**pz
    return H

def dzdt_prun_si(z: float, A: float, z0: float) -> float:
    H = make_H_prun(A,z0)
    return H0_s*(1+z) - (H(z)/Mpc_km)

# Power-law constant p
def dzdt_power_si(z: float, p: float) -> float:
    return H0_s*((1+z) - (1+z)**p)

def dv10_from_dzdt(z: float, dzdt_si: float) -> float:
    dz = dzdt_si*T10
    return c_kms*dz/(1+z)*1e5  # cm/s over 10 years

# -----------------
# Fit A,z0 to mimic LCDM distances for z<=2.5
# -----------------
def main(outdir: str | None = None):
    if outdir is None:
        outdir = str(Path(__file__).resolve().parent.parent / "outputs")
    os.makedirs(outdir, exist_ok=True)

    zs_fit = np.linspace(0.05, 2.5, 80)
    dL_lcdm = np.array([dL_flat(float(z), H_lcdm_km_s_Mpc) for z in zs_fit])

    def loss(params):
        A, logz0 = params
        z0 = math.exp(logz0)
        if A<=0 or A>=1 or z0<=0:
            return 1e9
        H = make_H_prun(A,z0)
        dL_model = np.array([dL_flat(float(z), H) for z in zs_fit])
        rel = (dL_model - dL_lcdm)/dL_lcdm
        return float(np.mean(rel**2))

    if DO_OPTIMIZE:
        res = opt.minimize(loss, x0=np.array([0.2, math.log(0.5)]), method="Nelder-Mead", options={"maxiter":120})
        A_opt, z0_opt = float(res.x[0]), float(math.exp(res.x[1]))
        print("Best-fit A =",A_opt, "z0 =",z0_opt, "loss =",res.fun)
    else:
        A_opt, z0_opt = float(A_PRESET), float(Z0_PRESET)
        print("Using preset A =",A_opt, "z0 =",z0_opt, "(set DO_OPTIMIZE=True to refit)")

    H_prun = make_H_prun(A_opt, z0_opt)

    zs_plot = np.linspace(0,5,400)[1:]
    dL_prun = np.array([dL_flat(float(z), H_prun) for z in zs_plot])
    dL_lcdm_plot = np.array([dL_flat(float(z), H_lcdm_km_s_Mpc) for z in zs_plot])
    rel_dL = (dL_prun - dL_lcdm_plot)/dL_lcdm_plot

    # Plot: relative distance difference
    plt.figure()
    plt.plot(zs_plot, rel_dL)
    plt.axhline(0, linewidth=1)
    plt.xlabel("z")
    plt.ylabel("Relative difference in d_L (model - LCDM)/LCDM")
    plt.title("Distance mimicry with always-positive drift (phenomenological)")
    plt.savefig(os.path.join(outdir, "phase2_dL_relative.png"), dpi=200, bbox_inches="tight")
    plt.close()

    # Drift plot
    dv10_lcdm = np.array([dv10_from_dzdt(float(z), dzdt_lcdm_si(float(z))) for z in zs_plot])
    dv10_prun = np.array([dv10_from_dzdt(float(z), dzdt_prun_si(float(z), A_opt, z0_opt)) for z in zs_plot])

    plt.figure()
    plt.plot(zs_plot, dv10_lcdm, label="LCDM")
    plt.plot(zs_plot, dv10_prun, label="Positive-drift fit")
    for p in [0.5,0.7,0.9]:
        dv = np.array([dv10_from_dzdt(float(z), dzdt_power_si(float(z),p)) for z in zs_plot])
        plt.plot(zs_plot, dv, label=f"Power-law p={p}")
    plt.axhline(0, linewidth=1)
    plt.xlabel("z")
    plt.ylabel("Δv over 10 years [cm/s]")
    plt.title("Redshift drift velocity shift")
    plt.legend()
    plt.savefig(os.path.join(outdir, "phase2_redshift_drift_compare.png"), dpi=200, bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    main()
