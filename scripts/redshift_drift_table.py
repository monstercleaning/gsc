#!/usr/bin/env python3
"""Print a small Sandage–Loeb (redshift drift) comparison table.

This script is intentionally dependency-free (stdlib only).

Run from repo root:
  python3 v11.0.0/scripts/redshift_drift_table.py
"""

from __future__ import annotations

from pathlib import Path
import sys


# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    H0_to_SI,
    PowerLawHistory,
    delta_v_cm_s,
)


def main() -> None:
    # Planck-like baseline (late-time).
    H0_km_s_Mpc = 67.4
    Omega_m = 0.315
    Omega_L = 0.685

    # Representative GSC toy parameterization from v10.1 text: 0<p<1.
    p = 0.5

    H0 = H0_to_SI(H0_km_s_Mpc)
    lcdm = FlatLambdaCDMHistory(H0=H0, Omega_m=Omega_m, Omega_Lambda=Omega_L)
    gsc = PowerLawHistory(H0=H0, p=p)

    years = 10.0
    points = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]

    print(f"H0 = {H0_km_s_Mpc} km/s/Mpc, years = {years}")
    print(f"LCDM: Omega_m={Omega_m}, Omega_L={Omega_L}")
    print(f"GSC toy: H(z)=H0*(1+z)^{p}")
    print("")
    print(" z    dv_10yr_lcdm[cm/s]    dv_10yr_gsc[cm/s]")
    print("---  -------------------    ------------------")
    for z in points:
        dv_lcdm = delta_v_cm_s(z=z, years=years, H0=H0, H_of_z=lcdm.H)
        dv_gsc = delta_v_cm_s(z=z, years=years, H0=H0, H_of_z=gsc.H)
        print(f"{z:>3.1f}  {dv_lcdm:>19.6f}    {dv_gsc:>18.6f}")


if __name__ == "__main__":
    main()

