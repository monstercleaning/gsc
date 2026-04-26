"""Phase 2 (v0.2): Distance–Drift tradeoff scan for the power-law H(z) ansatz.

Purpose
-------
This script is NOT a cosmological parameter fit.
It is a *pre-data sanity scan* that quantifies the inherent tension between:

  (A) demanding an always-positive redshift drift:  z_dot(z) = H0(1+z) - H(z) > 0  for all z
      -> for H(z)=H0(1+z)^p this requires p < 1

and

  (B) keeping standard distance–redshift relations close to a concordance LCDM baseline.

Because we work in an offline environment (no direct dataset download), we use
LCDM as a proxy baseline for late-time distance behavior. This is acceptable
at this stage because LCDM is known to fit SN/BAO distances well.

Outputs
-------
- phase2_tradeoff_max_dmu_vs_p.png
- phase2_tradeoff_vdot_vs_p.png
- phase2_tradeoff_scatter.png
- phase2_tradeoff_table.csv

How to interpret
----------------
- max|Δμ| is the maximum absolute distance-modulus residual vs LCDM on z∈[0, z_max].
- vdot(z*) is the apparent velocity drift at a chosen high-z target (default z*=3).

For a *strong* always-positive drift signature, you want vdot(z*) not too small.
For a *conservative* consistency with standard distances, you want max|Δμ| small.

"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import numpy as np
from scipy.integrate import quad
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -------- Constants
C_KM_S = 299792.458
SEC_PER_YEAR = 365.25 * 24 * 3600
MPC_KM = 3.085677581e19


@dataclass
class LCDM:
    H0_km_s_Mpc: float = 70.0
    Om: float = 0.30
    Ol: float = 0.70

    def H(self, z: float) -> float:
        return self.H0_km_s_Mpc * math.sqrt(self.Om * (1 + z) ** 3 + self.Ol)


@dataclass
class PowerLawHz:
    H0_km_s_Mpc: float = 70.0
    p: float = 0.8

    def H(self, z: float) -> float:
        return self.H0_km_s_Mpc * (1 + z) ** self.p

    def vdot_cm_s_yr(self, z: float) -> float:
        """Velocity drift in cm/s/year using standard relation:

            z_dot = H0(1+z) - H(z)
            v_dot = c * z_dot/(1+z)

        where H0 and H are in s^-1.
        """
        H0_si = (self.H0_km_s_Mpc * 1000.0) / (MPC_KM * 1000.0)  # km/s/Mpc -> 1/s
        Hz_si = (self.H(z) * 1000.0) / (MPC_KM * 1000.0)
        z_dot = H0_si * (1 + z) - Hz_si
        vdot_m_s_s = (299792458.0) * z_dot / (1 + z)
        return vdot_m_s_s * SEC_PER_YEAR * 100.0


def Dc_Mpc(z: float, H_of_z: Callable[[float], float]) -> float:
    """Comoving distance in Mpc for flat geometry."""
    integrand = lambda zp: C_KM_S / H_of_z(zp)
    val, _ = quad(integrand, 0, z, epsabs=1e-10, epsrel=1e-10, limit=400)
    return val


def dL_Mpc(z: float, H_of_z: Callable[[float], float]) -> float:
    return (1 + z) * Dc_Mpc(z, H_of_z)


def mu_mag(dL_mpc: float) -> float:
    return 5.0 * math.log10(dL_mpc) + 25.0


def scan(
    p_grid: np.ndarray,
    z_max_mu: float = 2.0,
    z_star_vdot: float = 3.0,
    lcdm: LCDM | None = None,
    H0_km_s_Mpc: float = 70.0,
) -> List[Dict[str, float]]:
    lcdm = lcdm or LCDM(H0_km_s_Mpc=H0_km_s_Mpc)

    z_samples = np.linspace(0.01, z_max_mu, 400)

    # Pre-compute LCDM mu(z)
    mu_l = np.array([mu_mag(dL_Mpc(z, lcdm.H)) for z in z_samples])

    rows: List[Dict[str, float]] = []
    for p in p_grid:
        model = PowerLawHz(H0_km_s_Mpc=H0_km_s_Mpc, p=float(p))
        mu_m = np.array([mu_mag(dL_Mpc(z, model.H)) for z in z_samples])
        dmu = mu_m - mu_l
        max_abs_dmu = float(np.max(np.abs(dmu)))
        vdot = float(model.vdot_cm_s_yr(z_star_vdot))

        # simple derived quantities (scalar-dominated exponential mapping)
        # For canonical scalar w = 2p/3 - 1.
        w_eff = 2.0 * float(p) / 3.0 - 1.0
        q0 = float(p) - 1.0

        rows.append(
            {
                "p": float(p),
                "max_abs_dmu_mag": max_abs_dmu,
                f"vdot_cm_s_yr_at_z{z_star_vdot:.1f}": vdot,
                "w_eff": w_eff,
                "q0": q0,
            }
        )

    return rows


def write_csv(rows: List[Dict[str, float]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_plots(rows: List[Dict[str, float]], out_dir: Path, z_star: float = 3.0) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ps = np.array([r["p"] for r in rows])
    maxdmu = np.array([r["max_abs_dmu_mag"] for r in rows])
    vdot_key = f"vdot_cm_s_yr_at_z{z_star:.1f}"
    vdot = np.array([r[vdot_key] for r in rows])

    # Plot 1: max|Δμ| vs p
    plt.figure()
    plt.plot(ps, maxdmu)
    plt.axhline(0.1)
    plt.axhline(0.2)
    plt.xlabel("p in H(z)=H0(1+z)^p")
    plt.ylabel(f"max|Δμ| vs LCDM on z∈[0,2] (mag)")
    plt.title("Distance residual envelope vs p")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "phase2_tradeoff_max_dmu_vs_p.png", dpi=180)
    plt.close()

    # Plot 2: vdot vs p
    plt.figure()
    plt.plot(ps, vdot)
    plt.axhline(0.0)
    plt.xlabel("p in H(z)=H0(1+z)^p")
    plt.ylabel(f"v̇(z={z_star:g})  (cm/s/year)")
    plt.title("Redshift-drift velocity signal vs p")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "phase2_tradeoff_vdot_vs_p.png", dpi=180)
    plt.close()

    # Plot 3: scatter tradeoff
    plt.figure()
    plt.scatter(maxdmu, vdot)
    plt.axvline(0.1)
    plt.axvline(0.2)
    plt.axhline(0.0)
    plt.xlabel("max|Δμ| vs LCDM (mag)")
    plt.ylabel(f"v̇(z={z_star:g})  (cm/s/year)")
    plt.title("Distance–Drift tradeoff (power-law H(z))")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "phase2_tradeoff_scatter.png", dpi=180)
    plt.close()


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "outputs"

    p_grid = np.linspace(0.45, 0.99, 55)
    rows = scan(p_grid=p_grid, z_max_mu=2.0, z_star_vdot=3.0)

    write_csv(rows, out_dir / "phase2_tradeoff_table.csv")
    make_plots(rows, out_dir=out_dir, z_star=3.0)

    print("[ok] wrote tradeoff outputs to:")
    print(f"  {out_dir}")


if __name__ == "__main__":
    main()
