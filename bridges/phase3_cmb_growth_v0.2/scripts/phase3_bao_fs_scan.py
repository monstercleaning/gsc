
"""
Phase 3 v0.2 — BAO+FS (BOSS DR12 consensus) compressed likelihood test.

We use the BAO+FS consensus constraints from Alam et al. (2017),
including the provided reduced covariance matrix (Table 8).

Model:
- H(z): piecewise with late-time H = H0 (1+z)^p, early = matter+radiation.
- r_d: computed from Eisenstein-Hu z_d + numerical sound horizon integral.
- Distances compared in the same scaled form used by BOSS:
    D_M(z) * (r_d,fid / r_d)   and   H(z) * (r_d / r_d,fid)

RSD:
- fσ8(z) = σ8_0 * f(z) * D(z), with σ8_0 analytically marginalized
  (generalized least squares) using the full covariance.

Outputs:
- figures/chi2_vs_lambda.png
- results/bao_fs_summary.txt
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

from gsc_cosmo_utils import CosmoParams, comoving_distance_Mpc, H_piecewise, r_drag, growth_factor_Da, theta_star

# BOSS DR12 consensus (BAO+FS) values (Alam et al. 2017, Table 7) with stat and sys errors.
# We use the MEAN and σ_i values from Table 8 (already includes systematic errors in σ_i).
# Observable vector order:
#   [DM0.38, H0.38, fs80.38, DM0.51, H0.51, fs80.51, DM0.61, H0.61, fs80.61]
DATA_MEAN = np.array([1518.0, 81.5, 0.497, 1977.0, 90.4, 0.458, 2283.0, 97.3, 0.436], dtype=float)
SIGMA = np.array([22.0, 1.9, 0.045, 27.0, 1.9, 0.038, 32.0, 2.1, 0.034], dtype=float)

# Reduced covariance matrix entries cij * 1e4 given in Table 8 (lower triangle).
# We'll reconstruct full cij and then full covariance Σ = diag(σ) * C * diag(σ).
C_LOWER_1E4 = {
    (1,0): 2280,
    (2,0): 3882, (2,1): 3249,
    (3,0): 4970, (3,1): 1536, (3,2): 1639,
    (4,0): 1117, (4,1): 4873, (4,2): 1060, (4,3): 2326,
    (5,0): 1797, (5,1): 1726, (5,2): 4773, (5,3): 3891, (5,4): 3039,
    (6,0): 1991, (6,1): 984,  (6,2): 237,  (6,3): 5120, (6,4): 1571, (6,5): 2046,
    (7,0): 520,  (7,1): 2307, (7,2): 108,  (7,3): 1211, (7,4): 5449, (7,5): 1231, (7,6): 2408,
    (8,0): 567,  (8,1): 725,  (8,2): 1704, (8,3): 1992, (8,4): 1584, (8,5): 5103, (8,6): 4358, (8,7): 2971,
}
N = len(DATA_MEAN)

def build_covariance():
    C = np.eye(N)
    for (i,j), v in C_LOWER_1E4.items():
        C[i,j] = v/1e4
        C[j,i] = v/1e4
    Sigma = np.diag(SIGMA) @ C @ np.diag(SIGMA)
    return Sigma

SIGMA_MAT = build_covariance()
INV_SIGMA = np.linalg.inv(SIGMA_MAT)

RD_FID = 147.78  # Mpc (Alam et al. 2017 Table 7)


def model_vector(params: CosmoParams, p_late: float, z_transition: float = 5.0):
    # r_d (model)
    rd = r_drag(params)["r_d_Mpc"]
    z_pts = np.array([0.38, 0.51, 0.61])

    # DM(z) and H(z)
    DM = np.array([comoving_distance_Mpc(z, params, p_late=p_late, z_transition=z_transition) for z in z_pts])
    H = np.array([H_piecewise(np.array([z]), params, p_late=p_late, z_transition=z_transition)[0] for z in z_pts])

    DM_scaled = DM * (RD_FID/rd)
    H_scaled = H * (rd/RD_FID)

    # Growth: compute f and D on a grid and interpolate
    gf = growth_factor_Da(params, p_late=p_late, z_transition=z_transition, z_max=50.0, n_eval=1200)
    z_grid, D_grid, f_grid = gf["z"], gf["D"], gf["f"]

    # interpolate at z_pts
    # z_grid is decreasing (high->low), so sort
    order = np.argsort(z_grid)
    zg = z_grid[order]
    Dg = D_grid[order]
    fg = f_grid[order]

    D_pts = np.interp(z_pts, zg, Dg)
    f_pts = np.interp(z_pts, zg, fg)
    # fsigma8 model is linear in sigma8_0: fs8 = sigma8_0 * (f * D)
    u_fs8 = f_pts * D_pts

    # Build b (sigma8_0-independent part) and u (sigma8_0 coefficient vector)
    b = np.zeros(N, dtype=float)
    u = np.zeros(N, dtype=float)

    # Fill DM,H entries
    b[0], b[1] = DM_scaled[0], H_scaled[0]
    b[3], b[4] = DM_scaled[1], H_scaled[1]
    b[6], b[7] = DM_scaled[2], H_scaled[2]

    # Fill fσ8 coefficient positions
    u[2], u[5], u[8] = u_fs8[0], u_fs8[1], u_fs8[2]

    return b, u, rd


def bestfit_sigma8_and_chi2(b: np.ndarray, u: np.ndarray):
    # Minimize chi2(a) where model = b + a u.
    # a_best = (u^T Σ^{-1} (d-b)) / (u^T Σ^{-1} u)
    dmb = DATA_MEAN - b
    num = u @ (INV_SIGMA @ dmb)
    den = u @ (INV_SIGMA @ u)
    a_best = num/den if den > 0 else np.nan
    resid = dmb - a_best*u
    chi2 = resid @ (INV_SIGMA @ resid)
    return float(a_best), float(chi2)


def main():
    params = CosmoParams()
    z_transition = 5.0

    lam = np.linspace(0.9, 1.6, 45)
    p = 0.5*lam**2

    chi2 = []
    sig8 = []
    rd_list = []
    for pi in p:
        b,u,rd = model_vector(params, p_late=float(pi), z_transition=z_transition)
        a_best, chi2_i = bestfit_sigma8_and_chi2(b,u)
        chi2.append(chi2_i)
        sig8.append(a_best)
        rd_list.append(rd)

    chi2 = np.array(chi2)
    sig8 = np.array(sig8)
    rd_list = np.array(rd_list)

    # Add a separate Planck theta_* prior (simple 1D Gaussian) for illustration.
    # Planck: 100 theta_* = 1.04109 ± 0.00030
    PLANCK_100THETA = 1.04109
    PLANCK_SIGMA = 0.00030
    chi2_theta = []
    for pi in p:
        th = theta_star(params, p_late=float(pi), z_transition=z_transition)["100_theta_star"]
        chi2_theta.append(((th-PLANCK_100THETA)/PLANCK_SIGMA)**2)
    chi2_theta = np.array(chi2_theta)
    chi2_joint = chi2 + chi2_theta

    # Plot
    plt.figure()
    plt.plot(lam, chi2, label="BOSS BAO+FS χ² (σ8 marginalized)")
    plt.plot(lam, chi2_joint, label="BOSS + Planck θ* (illustrative)")
    plt.xlabel(r"$\lambda$ (p = λ²/2)")
    plt.ylabel(r"$\chi^2$")
    plt.title("Compressed constraints scan (z_transition=5)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'chi2_vs_lambda.png', dpi=200)
    plt.close()

    # Summary text
    i_best = int(np.argmin(chi2_joint))
    i_best_boss = int(np.argmin(chi2))
    summary = []
    summary.append("Phase 3 v0.2 — BAO+FS compressed test (BOSS DR12 consensus)\n\n")
    summary.append(f"Params: Omega_bh2={params.Omega_bh2}, Omega_ch2={params.Omega_ch2}, h={params.h}\n")
    summary.append(f"Background: piecewise H(z), z_transition={z_transition}\n")
    summary.append(f"Data: Alam et al. 2017 Table 7/8 (BAO+FS consensus, with covariance)\n\n")

    summary.append("Best fit (BOSS-only, σ8 marginalized):\n")
    summary.append(f"  λ={lam[i_best_boss]:.3f}  p={p[i_best_boss]:.3f}  chi2={chi2[i_best_boss]:.2f}  sigma8_0={sig8[i_best_boss]:.3f}  r_d={rd_list[i_best_boss]:.2f} Mpc\n\n")

    summary.append("Best fit (BOSS + Planck θ* prior; illustrative):\n")
    summary.append(f"  λ={lam[i_best]:.3f}  p={p[i_best]:.3f}  chi2_joint={chi2_joint[i_best]:.2f}  chi2_BOSS={chi2[i_best]:.2f}  chi2_theta={chi2_theta[i_best]:.2f}\n")
    summary.append(f"  sigma8_0={sig8[i_best]:.3f}  r_d={rd_list[i_best]:.2f} Mpc\n\n")

    summary.append("Note:\n")
    summary.append("  • This is not a full Boltzmann likelihood analysis; it's a compressed diagnostic.\n")
    summary.append("  • In Phase 4, implement full CMB spectra + lensing + MCMC fits.\n")

    from pathlib import Path
    (RES_DIR / 'bao_fs_summary.txt').write_text("".join(summary))

if __name__ == "__main__":
    main()