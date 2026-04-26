
"""
Phase 3 v0.2 — growth curves for several λ (p=λ²/2), diagnostic only.

Outputs:
- figures/growth_Dz_vs_z.png
- figures/growth_f_vs_z.png
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / 'outputs' / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

from gsc_cosmo_utils import CosmoParams, growth_factor_Da

def main():
    params = CosmoParams()
    z_transition = 5.0

    lam_list = [1.0, 1.2, 1.3, 1.4]  # representative
    plt.figure()
    for lam in lam_list:
        p = 0.5*lam**2
        gf = growth_factor_Da(params, p_late=p, z_transition=z_transition, z_max=50.0, n_eval=1400)
        z, D = gf["z"], gf["D"]
        # sort
        idx = np.argsort(z)
        plt.plot(z[idx], D[idx], label=f"λ={lam:.2f} (p={p:.2f})")
    plt.xlim(0, 3)
    plt.ylim(0.4, 1.02)
    plt.xlabel("z")
    plt.ylabel("D(z) normalized to 1 at z=0")
    plt.title("Linear growth factor D(z) (effective GR diagnostic)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'growth_Dz_vs_z.png', dpi=200)
    plt.close()

    plt.figure()
    for lam in lam_list:
        p = 0.5*lam**2
        gf = growth_factor_Da(params, p_late=p, z_transition=z_transition, z_max=50.0, n_eval=1400)
        z, f = gf["z"], gf["f"]
        idx = np.argsort(z)
        plt.plot(z[idx], f[idx], label=f"λ={lam:.2f} (p={p:.2f})")
    plt.xlim(0, 3)
    plt.ylim(0.2, 1.2)
    plt.xlabel("z")
    plt.ylabel("growth rate f(z) = d ln D / d ln a")
    plt.title("Growth rate f(z) (effective GR diagnostic)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'growth_f_vs_z.png', dpi=200)
    plt.close()

if __name__ == "__main__":
    main()