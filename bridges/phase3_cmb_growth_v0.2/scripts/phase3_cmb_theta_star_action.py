
"""
Phase 3 v0.2 — CMB acoustic-scale (theta_*) diagnostic, linked to Phase 2 via p = λ^2 / 2.

Outputs:
- figures/theta_star_vs_lambda.png
- figures/zstar_required_shift.png
- results/theta_star_action_summary.txt
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / 'outputs' / 'figures'
RES_DIR = ROOT / 'outputs' / 'results'
FIG_DIR.mkdir(parents=True, exist_ok=True)
RES_DIR.mkdir(parents=True, exist_ok=True)

from gsc_cosmo_utils import CosmoParams, theta_star

# Planck 2018 (ΛCDM) acoustic scale: 100*theta_* ≈ 1.04109 ± 0.00030 (representative; see report refs).
PLANCK_100THETA = 1.04109
PLANCK_SIGMA = 0.00030


def solve_zstar_to_match(theta_target: float, params: CosmoParams, p_late: float, z_transition: float,
                         z_min: float = 700.0, z_max: float = 1500.0, n_grid: int = 200) -> tuple[float, float]:
    """
    Find a z_* that best matches a target theta_* value by scanning.
    This is a diagnostic for "how much recombination physics must shift" in a freeze-frame picture.
    """
    from gsc_cosmo_utils import sound_horizon_Mpc, comoving_distance_Mpc

    z_grid = np.linspace(z_min, z_max, n_grid)
    rs = np.array([sound_horizon_Mpc(z, params) for z in z_grid])
    DM = np.array([comoving_distance_Mpc(z, params, p_late=p_late, z_transition=z_transition) for z in z_grid])
    th = rs / DM
    idx = np.argmin(np.abs(th - theta_target))
    return float(z_grid[idx]), float(th[idx])


def main():
    params = CosmoParams()  # Planck-like baseline
    z_transition = 5.0

    # Scan λ and derived p = λ^2/2
    lam = np.linspace(0.9, 1.6, 40)   # corresponds to p ~ 0.4 .. 1.3
    p = 0.5 * lam**2

    vals = []
    for pi in p:
        out = theta_star(params, p_late=float(pi), z_transition=z_transition)
        vals.append(out["100_theta_star"])
    vals = np.array(vals)

    # Compute required z_* shift to exactly match Planck theta_*
    z_req = []
    th_req = []
    for pi in p:
        z_i, th_i = solve_zstar_to_match(theta_target=PLANCK_100THETA/100.0, params=params,
                                         p_late=float(pi), z_transition=z_transition)
        z_req.append(z_i)
        th_req.append(th_i*100.0)
    z_req = np.array(z_req)
    th_req = np.array(th_req)

    # Plot 100 theta_* vs λ
    plt.figure()
    plt.plot(lam, vals, label="GSC (piecewise background)")
    plt.axhline(PLANCK_100THETA, linestyle="--", label="Planck 2018 mean")
    plt.axhspan(PLANCK_100THETA-PLANCK_SIGMA, PLANCK_100THETA+PLANCK_SIGMA, alpha=0.2, label="Planck 1σ")
    plt.xlabel(r"$\lambda$  (Phase-2 exponential slope)")
    plt.ylabel(r"$100\,\theta_*$")
    plt.title(r"CMB acoustic scale diagnostic (z_transition=5)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'theta_star_vs_lambda.png', dpi=200)
    plt.close()

    # Plot required z_* shift vs λ
    # baseline z_* from Hu-Sugiyama
    from gsc_cosmo_utils import z_star_hu_sugiyama
    z0 = z_star_hu_sugiyama(params.Omega_bh2, params.Omega_mh2)
    plt.figure()
    plt.plot(lam, (z_req - z0)/z0 * 100.0, label="required Δz_*/z_* (%)")
    plt.axhline(0.0, linestyle="--")
    plt.xlabel(r"$\lambda$")
    plt.ylabel(r"required shift in $z_*$  [%]")
    plt.title("How much must recombination shift to preserve Planck θ*?")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'zstar_required_shift.png', dpi=200)
    plt.close()

    # Write summary
    # pick "Phase 2 plausible" λ range ~ [1.2, 1.3] -> p ~ 0.72..0.85
    mask = (lam >= 1.15) & (lam <= 1.35)
    summary = []
    summary.append("Phase 3 v0.2 — theta_* diagnostic\n")
    summary.append(f"Assumptions: piecewise H(z), z_transition={z_transition}\n")
    summary.append(f"Baseline params: Omega_bh2={params.Omega_bh2}, Omega_ch2={params.Omega_ch2}, h={params.h}\n")
    summary.append(f"Planck target: 100*theta_* = {PLANCK_100THETA} ± {PLANCK_SIGMA}\n\n")
    summary.append("Selected λ range (Phase-2 plausible) and resulting 100θ*:\n")
    for li, pi, vi, zi in zip(lam[mask], p[mask], vals[mask], z_req[mask]):
        summary.append(f"  λ={li:5.3f}  p=λ^2/2={pi:5.3f}  100θ*={vi:8.5f}  z*_req={zi:8.1f}\n")
    summary.append("\nInterpretation:\n")
    summary.append("  • If 100θ* is outside the Planck band, the model must either:\n")
    summary.append("    (i) change late-time background (p, z_transition), or\n")
    summary.append("    (ii) modify early-time microphysics mapping (effective z_*),\n")
    summary.append("    which in GSC would come from the scale–temperature correspondence in the freeze frame.\n")
    (RES_DIR / 'theta_star_action_summary.txt').write_text("".join(summary))

if __name__ == "__main__":
        main()