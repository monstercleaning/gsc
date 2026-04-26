
"""
GSC Phase 3 utilities: compressed CMB/BAO/Growth diagnostics.

Design goals:
- Keep units explicit (H in km/s/Mpc, distances in Mpc).
- Provide transparent, modular functions (easy to swap a more rigorous background model later).
- Avoid claiming a full Boltzmann treatment; these are "distance-prior" and "compressed" checks.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

# Speed of light in vacuum [km/s]
C_KMS = 299792.458

# CMB temperature [K] (Fixsen 2009 / Planck; common reference value)
T_CMB_K = 2.7255

# Effective number of relativistic neutrino species
N_EFF = 3.046

@dataclass(frozen=True)
class CosmoParams:
    """
    Minimal cosmological parameter set for compressed diagnostics.

    Omega_bh2: physical baryon density
    Omega_ch2: physical CDM density
    h: reduced Hubble constant (H0/100 km/s/Mpc)
    """
    Omega_bh2: float = 0.02237
    Omega_ch2: float = 0.1200
    h: float = 0.6736

    @property
    def H0(self) -> float:
        """Hubble constant [km/s/Mpc]."""
        return 100.0 * self.h

    @property
    def Omega_b(self) -> float:
        return self.Omega_bh2 / (self.h ** 2)

    @property
    def Omega_c(self) -> float:
        return self.Omega_ch2 / (self.h ** 2)

    @property
    def Omega_m(self) -> float:
        return self.Omega_b + self.Omega_c

    @property
    def Omega_gamma_h2(self) -> float:
        # Photon density today, Ω_γ h^2 ≈ 2.469e-5 (T/2.7255)^4
        return 2.469e-5 * (T_CMB_K / 2.7255) ** 4

    @property
    def Omega_gamma(self) -> float:
        return self.Omega_gamma_h2 / (self.h ** 2)

    @property
    def Omega_r(self) -> float:
        # Ω_r = Ω_γ (1 + 0.2271 N_eff)
        return self.Omega_gamma * (1.0 + 0.2271 * N_EFF)

    @property
    def Omega_mh2(self) -> float:
        return self.Omega_bh2 + self.Omega_ch2


def z_star_hu_sugiyama(Omega_bh2: float, Omega_mh2: float) -> float:
    """
    Redshift of photon decoupling z_* (Hu & Sugiyama fitting form, widely used in distance-prior work).
    """
    g1 = 0.0783 * (Omega_bh2) ** (-0.238) / (1.0 + 39.5 * (Omega_bh2) ** 0.763)
    g2 = 0.560 / (1.0 + 21.1 * (Omega_bh2) ** 1.81)
    z_star = 1048.0 * (1.0 + 0.00124 * (Omega_bh2) ** (-0.738)) * (1.0 + g1 * (Omega_mh2) ** g2)
    return float(z_star)


def z_drag_eisenstein_hu(Omega_bh2: float, Omega_mh2: float) -> float:
    """
    Drag epoch redshift z_d (Eisenstein & Hu 1998 fitting form).
    """
    b1 = 0.313 * (Omega_mh2) ** (-0.419) * (1.0 + 0.607 * (Omega_mh2) ** 0.674)
    b2 = 0.238 * (Omega_mh2) ** 0.223
    z_d = 1291.0 * (Omega_mh2) ** 0.251 / (1.0 + 0.659 * (Omega_mh2) ** 0.828) * (1.0 + b1 * (Omega_bh2) ** b2)
    return float(z_d)


def E_LCDM_early(z: np.ndarray, params: CosmoParams) -> np.ndarray:
    """
    Early-time E(z) = H(z)/H0 assuming only matter+radiation.
    (Dark energy negligible at z >> 1 for these integrals.)
    """
    zp1 = 1.0 + np.asarray(z)
    return np.sqrt(params.Omega_r * zp1**4 + params.Omega_m * zp1**3)


def H_piecewise(z: np.ndarray, params: CosmoParams, p_late: float, z_transition: float = 5.0) -> np.ndarray:
    """
    Piecewise background H(z) [km/s/Mpc]:
      - for z <= z_transition: phenomenological 'collapse' law H = H0 (1+z)^p_late
      - for z >  z_transition: standard matter+radiation scaling H = H0 * E_LCDM_early(z)

    Notes:
      - z_transition is a phenomenological matching scale in Phase 3.
      - In a full model it should be derived from the RG/action dynamics.
    """
    z = np.asarray(z)
    H0 = params.H0
    out = np.empty_like(z, dtype=float)
    mask = z <= z_transition
    out[mask] = H0 * (1.0 + z[mask]) ** p_late
    out[~mask] = H0 * E_LCDM_early(z[~mask], params)
    return out


def comoving_distance_Mpc(z: float, params: CosmoParams, p_late: float, z_transition: float = 5.0, n_grid: int = 8000) -> float:
    """
    Line-of-sight comoving distance D_C(z) [Mpc] via numerical integration:
      D_C = ∫_0^z c/H(z') dz'

    Uses log(1+z) grid for stability up to z~1100.
    """
    if z <= 0:
        return 0.0
    x_max = np.log(1.0 + z)
    x = np.linspace(0.0, x_max, n_grid)
    z_grid = np.expm1(x)
    Hz = H_piecewise(z_grid, params, p_late=p_late, z_transition=z_transition)
    integrand = (C_KMS / Hz) * (1.0 + z_grid)  # dz = (1+z) dx
    Dc = np.trapz(integrand, x)
    return float(Dc)


def R_baryon_to_photon(z: np.ndarray, params: CosmoParams) -> np.ndarray:
    """
    R(z) = 3 ρ_b / (4 ρ_γ) = (3Ω_b / 4Ω_γ) * 1/(1+z)
    """
    z = np.asarray(z)
    return (3.0 * params.Omega_b) / (4.0 * params.Omega_gamma) * 1.0/(1.0 + z)


def sound_speed_kms(z: np.ndarray, params: CosmoParams) -> np.ndarray:
    """Photon-baryon sound speed c_s(z) [km/s]."""
    Rz = R_baryon_to_photon(z, params)
    return C_KMS / np.sqrt(3.0 * (1.0 + Rz))


def sound_horizon_Mpc(z: float, params: CosmoParams, z_max: float = 1e7, n_grid: int = 20000) -> float:
    """
    Sound horizon r_s(z) [Mpc]:
      r_s(z) = ∫_z^∞ c_s(z')/H(z') dz'

    Here we use the early-time H(z) (matter+radiation), which dominates for z>=z_*~1100.
    """
    if z <= 0:
        z = 0.0
    # log grid in 1+z to cover many decades
    x0 = np.log(1.0 + z)
    x1 = np.log(1.0 + z_max)
    x = np.linspace(x0, x1, n_grid)
    z_grid = np.expm1(x)
    cs = sound_speed_kms(z_grid, params)
    Hz = params.H0 * E_LCDM_early(z_grid, params)
    integrand = (cs / Hz) * (1.0 + z_grid)  # dz = (1+z) dx
    rs = np.trapz(integrand, x)
    return float(rs)


def theta_star(params: CosmoParams, p_late: float, z_transition: float = 5.0) -> dict:
    """
    Compute the angular sound horizon theta_* and related quantities.

    Returns a dict with:
      z_star, r_s_star, D_M_star, theta_star, 100*theta_star, l_A
    """
    zst = z_star_hu_sugiyama(params.Omega_bh2, params.Omega_mh2)
    rs = sound_horizon_Mpc(zst, params)
    DM = comoving_distance_Mpc(zst, params, p_late=p_late, z_transition=z_transition)
    th = rs / DM
    lA = np.pi / th
    return {
        "z_star": zst,
        "r_s_star_Mpc": rs,
        "D_M_star_Mpc": DM,
        "theta_star": th,
        "100_theta_star": 100.0 * th,
        "l_A": lA,
    }


def r_drag(params: CosmoParams) -> dict:
    """
    Compute r_d ≡ r_s(z_d) using Eisenstein-Hu fitting formula for z_d.

    Returns dict: z_d, r_d_Mpc
    """
    zd = z_drag_eisenstein_hu(params.Omega_bh2, params.Omega_mh2)
    rd = sound_horizon_Mpc(zd, params)
    return {"z_d": zd, "r_d_Mpc": rd}


def growth_factor_Da(params: CosmoParams, p_late: float, z_transition: float = 5.0, z_max: float = 50.0,
                     n_eval: int = 800) -> dict:
    """
    Linear growth factor D(a) and growth rate f(a) under GR growth equation
    with piecewise background H(z).

    IMPORTANT:
      - This is a diagnostic "effective GR" growth calculation.
      - A full GSC perturbation theory may alter the source term and slip.

    Returns arrays for z, a, D_norm, f.
    """
    from scipy.integrate import solve_ivp

    # Independent variable x = ln a
    a_min = 1.0 / (1.0 + z_max)
    x0 = np.log(a_min)
    x1 = 0.0

    # Transition scale in terms of a
    a_t = 1.0 / (1.0 + z_transition)

    def E_of_a(a: float) -> float:
        z = 1.0 / a - 1.0
        # Use H_piecewise with vectorized input
        return float(H_piecewise(np.array([z]), params, p_late=p_late, z_transition=z_transition)[0] / params.H0)

    def dlnH_dlnA(a: float) -> float:
        # analytic derivative within each regime; finite diff near boundary.
        if abs(a - a_t) / a_t < 1e-3:
            # central finite difference in ln a
            eps = 1e-4
            a1 = a * np.exp(-eps)
            a2 = a * np.exp(+eps)
            return (np.log(E_of_a(a2)) - np.log(E_of_a(a1))) / (2*eps)
        if a >= a_t:
            # late: H ∝ a^{-p}
            return -p_late
        # early: H ∝ sqrt(Ω_r a^-4 + Ω_m a^-3)
        Er = params.Omega_r * a**(-4)
        Em = params.Omega_m * a**(-3)
        E2 = Er + Em
        # d ln H / d ln a = (1/2) d ln E2 / d ln a
        dlnE2 = (a/E2) * ( (-4)*params.Omega_r * a**(-5) + (-3)*params.Omega_m * a**(-4) )
        return 0.5 * dlnE2

    def Omega_m_of_a(a: float) -> float:
        z = 1.0/a - 1.0
        E = E_of_a(a)
        return params.Omega_m * (1.0+z)**3 / (E**2)

    def mu_of_a(a: float) -> float:
        # Placeholder: GR mu=1. Phase 4 can insert modified gravity.
        return 1.0

    def rhs(x, y):
        # y = [D, dD/dx]
        a = np.exp(x)
        D, D1 = y
        dlnH = dlnH_dlnA(a)
        Om = Omega_m_of_a(a)
        mu = mu_of_a(a)
        D2 = -(2.0 + dlnH) * D1 + 1.5 * Om * mu * D
        return [D1, D2]

    # initial conditions at high z: in matter-dominated era, D ~ a, dD/dln a = D
    y0 = [a_min, a_min]

    x_eval = np.linspace(x0, x1, n_eval)
    sol = solve_ivp(rhs, t_span=(x0, x1), y0=y0, t_eval=x_eval, rtol=1e-8, atol=1e-10)

    a = np.exp(sol.t)
    D = sol.y[0]
    D1 = sol.y[1]
    f = D1 / D  # f = d ln D / d ln a

    # Normalize to D(a=1)=1 for convenience
    D_norm = D / D[-1]

    z = 1.0/a - 1.0
    return {"z": z, "a": a, "D": D_norm, "f": f}


def marginalize_sigma8(fsigma8_model: np.ndarray, fsigma8_data: np.ndarray, sigma: np.ndarray) -> tuple[float, float]:
    """
    Given model prediction proportional to sigma8_0:
        fσ8_pred(z) = sigma8_0 * fsigma8_model(z)
    return sigma8_0 best-fit (weighted least squares) and chi2_min.
    """
    w = 1.0 / (sigma**2)
    num = np.sum(w * fsigma8_model * fsigma8_data)
    den = np.sum(w * fsigma8_model**2)
    sigma8_best = num / den if den > 0 else np.nan
    chi2 = np.sum(w * (sigma8_best*fsigma8_model - fsigma8_data)**2)
    return float(sigma8_best), float(chi2)
