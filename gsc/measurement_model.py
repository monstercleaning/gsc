"""GSC v11.0.0 — Measurement Model helpers (Option 2: freeze-frame).

This module implements the minimal "measurement model" layer for v11.0.0:
- definition of redshift in terms of the universal matter scale σ(t)
- Sandage–Loeb redshift drift (kinematic relation; late-time scope)
- baseline distance relations under a conservative reciprocity assumption

Important scope note:
This is NOT a full early-universe/CMB mapping. It is a late-time, reproducible
translation layer for z, drift, and baseline distances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Callable, Optional

# SI constants (kept local to avoid extra deps)
C_SI = 299_792_458.0  # m/s
PC_SI = 3.085677581e16  # m
MPC_SI = 3.085677581e22  # m
SEC_PER_YR = 365.25 * 24 * 3600


def z_from_sigma(*, sigma_emit: float, sigma_obs: float) -> float:
    """Operational redshift definition for Option 2.

    With universal scaling:
      (1+z) = sigma_emit / sigma_obs
    """
    if sigma_emit <= 0 or sigma_obs <= 0:
        raise ValueError("sigma must be positive")
    return sigma_emit / sigma_obs - 1.0


def sigma_ratio_from_z(z: float) -> float:
    """Return sigma_emit/sigma_obs = 1+z."""
    if z < -1.0:
        raise ValueError("Require z >= -1")
    return 1.0 + z


def time_dilation_factor(z: float) -> float:
    """Return the observed light-curve stretch factor.

    Under universal scaling in the freeze-frame measurement model, emitter
    clocks at t_e run slower than today's atomic clocks by (1+z), so:
      Δt_obs = (1+z) Δt_emit
    """
    return sigma_ratio_from_z(z)


def tolman_surface_brightness_ratio(z: float) -> float:
    """Return the Tolman surface brightness scaling B_obs/B_emit.

    In standard FLRW, surface brightness scales as (1+z)^(-4).

    In Option 2 this scaling is recovered under the conservative reciprocity
    hypothesis (Etherington distance duality) and universal metrology scaling.

    Note:
    This helper encodes the classical relation; it does not, by itself, derive
    source-physics corrections for specific populations (SN Ia, galaxies, ...).
    """
    if z < -1.0:
        raise ValueError("Require z >= -1")
    return (1.0 + z) ** (-4.0)


def a_from_sigma(*, sigma: float, sigma0: float) -> float:
    """Convenience: effective scale factor a = sigma0/sigma."""
    if sigma <= 0 or sigma0 <= 0:
        raise ValueError("sigma must be positive")
    return sigma0 / sigma


def hsigma_from_sigma(*, sigma_dot: float, sigma: float) -> float:
    """Collapse rate H_σ = -σ̇/σ in 1/s."""
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    return -sigma_dot / sigma


def z_dot_sandage_loeb(*, z: float, H0: float, H_of_z: Callable[[float], float]) -> float:
    """Redshift drift ż = dz/dt0 in 1/s.

    We use the standard kinematic relation:
      ż = H0*(1+z) - H(z)

    At this level the relation is frame-independent: changing conformal-frame
    variables does not change ż if the same physical H(z) history is used.
    Observational differences arise only from different histories H(z), not
    from the frame label itself. In particular, this relation does not by
    itself discriminate "freeze frame vs expansion" interpretations.

    In Option 2 this is interpreted as a statement about the effective collapse
    history H_σ(z) under the bookkeeping map a(t)=sigma0/sigma(t), and dt0 is
    the observer's proper time measured by local clocks.
    """
    if z < -1.0:
        raise ValueError("Require z >= -1")
    if H0 <= 0:
        raise ValueError("H0 must be positive (1/s)")
    Hz = float(H_of_z(z))
    return H0 * (1.0 + z) - Hz


def v_dot_from_z_dot(*, z: float, z_dot: float, c: float = C_SI) -> float:
    """Velocity drift rate v̇ in m/s per second."""
    if z < -1.0:
        raise ValueError("Require z >= -1")
    return c * z_dot / (1.0 + z)


def delta_v(*, z: float, years: float, H0: float, H_of_z: Callable[[float], float], c: float = C_SI) -> float:
    """Velocity drift Δv over 'years' years, in m/s."""
    if years < 0:
        raise ValueError("years must be >= 0")
    z_dot = z_dot_sandage_loeb(z=z, H0=H0, H_of_z=H_of_z)
    v_dot = v_dot_from_z_dot(z=z, z_dot=z_dot, c=c)
    return v_dot * (years * SEC_PER_YR)


def delta_v_cm_s(*, z: float, years: float, H0: float, H_of_z: Callable[[float], float], c: float = C_SI) -> float:
    """Velocity drift Δv over 'years' years, in cm/s."""
    return 100.0 * delta_v(z=z, years=years, H0=H0, H_of_z=H_of_z, c=c)


def H0_to_SI(H0_km_s_Mpc: float) -> float:
    """Convert H0 from km/s/Mpc to 1/s."""
    return H0_km_s_Mpc * 1000.0 / MPC_SI


def integrate_trapezoid(f: Callable[[float], float], a: float, b: float, *, n: int = 10_000) -> float:
    """Simple trapezoid integrator for smooth functions."""
    if n <= 0:
        raise ValueError("n must be > 0")
    if b < a:
        raise ValueError("Require b >= a")
    if a == b:
        return 0.0
    h = (b - a) / n
    s = 0.5 * (float(f(a)) + float(f(b)))
    for i in range(1, n):
        s += float(f(a + i * h))
    return s * h


def comoving_distance_flat(
    *,
    z: float,
    H_of_z: Callable[[float], float],
    c: float = C_SI,
    n: int = 10_000,
) -> float:
    """Comoving distance χ(z) in meters (flat), using χ = c∫dz/H(z)."""
    if z < 0:
        raise ValueError("Require z >= 0 for this helper")

    def inv_H(zz: float) -> float:
        Hz = float(H_of_z(zz))
        if Hz <= 0:
            raise ValueError("H(z) must be positive in this helper")
        return 1.0 / Hz

    return c * integrate_trapezoid(inv_H, 0.0, z, n=n)


def D_M_flat(*, z: float, H_of_z: Callable[[float], float], c: float = C_SI, n: int = 10_000) -> float:
    """Transverse comoving distance D_M(z)=χ(z) (flat)."""
    return comoving_distance_flat(z=z, H_of_z=H_of_z, c=c, n=n)


def D_A_flat(*, z: float, H_of_z: Callable[[float], float], c: float = C_SI, n: int = 10_000) -> float:
    """Angular diameter distance D_A(z)=D_M(z)/(1+z) (flat)."""
    return D_M_flat(z=z, H_of_z=H_of_z, c=c, n=n) / (1.0 + z)


def D_L_flat(*, z: float, H_of_z: Callable[[float], float], c: float = C_SI, n: int = 10_000) -> float:
    """Luminosity distance D_L(z)=(1+z)D_M(z) (flat)."""
    return (1.0 + z) * D_M_flat(z=z, H_of_z=H_of_z, c=c, n=n)


def distance_modulus_from_D_L(*, D_L_m: float, pc: float = PC_SI) -> float:
    """Return distance modulus μ given luminosity distance in meters.

    Standard definition:
      μ = 5 log10(D_L / 10 pc)
    """
    if D_L_m <= 0:
        raise ValueError("D_L must be positive")
    ten_pc = 10.0 * pc
    return 5.0 * math.log10(D_L_m / ten_pc)


def D_L_from_distance_modulus(*, mu: float, pc: float = PC_SI) -> float:
    """Inverse of distance_modulus_from_D_L: return D_L in meters."""
    ten_pc = 10.0 * pc
    return ten_pc * (10.0 ** (mu / 5.0))


def distance_modulus_flat(
    *,
    z: float,
    H_of_z: Callable[[float], float],
    c: float = C_SI,
    n: int = 10_000,
    pc: float = PC_SI,
) -> float:
    """Distance modulus μ(z) using the v11.0.0 baseline D_L(z) hypothesis."""
    return distance_modulus_from_D_L(D_L_m=D_L_flat(z=z, H_of_z=H_of_z, c=c, n=n), pc=pc)


@dataclass(frozen=True)
class PowerLawHistory:
    """Late-time toy history used in v10.1: H(z)=H0(1+z)^p."""

    H0: float
    p: float

    def H(self, z: float) -> float:
        if z < -1.0:
            raise ValueError("Require z >= -1")
        if self.H0 <= 0:
            raise ValueError("H0 must be positive")
        return self.H0 * (1.0 + z) ** self.p


@dataclass(frozen=True)
class FlatLambdaCDMHistory:
    """Late-time flat ΛCDM reference history.

    We ignore radiation at v11.0.0 scope (post-recombination kinematics).
    """

    H0: float
    Omega_m: float
    Omega_Lambda: float

    def H(self, z: float) -> float:
        if z < -1.0:
            raise ValueError("Require z >= -1")
        if self.H0 <= 0:
            raise ValueError("H0 must be positive")
        if self.Omega_m < 0 or self.Omega_Lambda < 0:
            raise ValueError("Require non-negative density parameters")
        return self.H0 * math.sqrt(self.Omega_m * (1.0 + z) ** 3 + self.Omega_Lambda)


@dataclass(frozen=True)
class GSCTransitionHistory:
    """A late-time "transition" history used for Option-2 GSC scorecards.

    Piecewise definition (E(z)=H(z)/H0):
    - for z <= z_transition: use a flat ΛCDM-like E(z)
    - for z > z_transition: switch to a power-law E(z) = E(z_t) * ((1+z)/(1+z_t))^p

    This keeps low-z distances close to ΛCDM while allowing a different
    high-z drift behavior, without making early-universe claims at v11.0.0.
    """

    H0: float
    Omega_m: float
    Omega_Lambda: float
    p: float
    z_transition: float
    _E_transition: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.H0 <= 0:
            raise ValueError("H0 must be positive")
        if self.Omega_m < 0 or self.Omega_Lambda < 0:
            raise ValueError("Require non-negative density parameters")
        if self.p <= 0:
            raise ValueError("p must be positive")
        if self.z_transition < 0:
            raise ValueError("z_transition must be >= 0")
        zt = float(self.z_transition)
        E_t = math.sqrt(self.Omega_m * (1.0 + zt) ** 3 + self.Omega_Lambda)
        object.__setattr__(self, "_E_transition", float(E_t))

    def E(self, z: float) -> float:
        if z < -1.0:
            raise ValueError("Require z >= -1")
        if z <= self.z_transition:
            return math.sqrt(self.Omega_m * (1.0 + z) ** 3 + self.Omega_Lambda)
        ratio = (1.0 + z) / (1.0 + self.z_transition)
        return self._E_transition * (ratio**self.p)

    def H(self, z: float) -> float:
        return self.H0 * self.E(z)


# =============================================================================
# Null-prediction demos (universal scaling): helper functions for lock-tests
# =============================================================================


def universal_scaling_exponents() -> dict[str, float]:
    """Return the v11.0.0 universal-scaling exponents as powers of σ.

    Convention: if a quantity X scales as X ∝ σ^p, return p.

    These encode the measurement-model axioms documented in:
      v11.0.0/docs/measurement_model.md

    Notes:
    - These helpers are used only in lock-tests and docs translation.
    - They are not used by the late-time fit/figure pipeline.
    """
    return {
        # Bound rulers.
        "length_bound": +1.0,
        # Bound masses (electrons, nuclei, ...).
        "mass": -1.0,
        # Infrared Newton coupling (from M_Pl ∝ σ^-1).
        "G_IR": +2.0,
        # Representative atomic transition frequency (hydrogenic intuition with constant α):
        # ν_atom ∝ E_atom ∝ m_e ∝ σ^-1.
        "nu_atomic": -1.0,
    }


def _scaling_factor(*, sigma: float, sigma_ref: float, power: float) -> float:
    """Return X(sigma)/X(sigma_ref) for X ∝ σ^power."""
    if not (sigma > 0.0 and math.isfinite(sigma)):
        raise ValueError("sigma must be positive and finite")
    if not (sigma_ref > 0.0 and math.isfinite(sigma_ref)):
        raise ValueError("sigma_ref must be positive and finite")
    return (sigma / sigma_ref) ** float(power)


def kepler_orbital_frequency_scaling_power() -> float:
    """Scaling power for a Kepler orbital frequency under universal scaling.

    Using the Kepler relation ω^2 ∝ G M / r^3 and the universal scaling axioms:
    - G ∝ σ^(+2), M ∝ σ^(-1), r ∝ σ^(+1)
    therefore:
      ω ∝ σ^((2 + (-1) - 3*1)/2) = σ^(-1)

    This is the simplest "geometric lock" example: orbital and atomic frequencies
    co-scale, so their ratio is invariant.
    """
    ex = universal_scaling_exponents()
    p_G = float(ex["G_IR"])
    p_M = float(ex["mass"])
    p_r = float(ex["length_bound"])
    return 0.5 * (p_G + p_M - 3.0 * p_r)


def demo_ratio_nu_atom_over_nu_orb(*, sigma: float, sigma_ref: float = 1.0) -> float:
    """Return (ν_atom/ν_orb)(sigma) / (ν_atom/ν_orb)(sigma_ref).

    Under strict universal scaling, this ratio is a null prediction: it should
    be invariant (== 1) because both numerator and denominator scale as σ^-1.
    """
    ex = universal_scaling_exponents()
    p_atom = float(ex["nu_atomic"])
    p_orb = float(kepler_orbital_frequency_scaling_power())
    nu_atom_rel = _scaling_factor(sigma=sigma, sigma_ref=sigma_ref, power=p_atom)
    nu_orb_rel = _scaling_factor(sigma=sigma, sigma_ref=sigma_ref, power=p_orb)
    return float(nu_atom_rel / nu_orb_rel)


def demo_ratio_clock_comparison(
    *,
    sigma: float,
    sigma_ref: float = 1.0,
    nu_a0: float = 1.0,
    nu_b0: float = 2.0,
) -> float:
    """Return (ν_a/ν_b)(sigma) / (ν_a/ν_b)(sigma_ref) for two local clocks.

    In the strict universal-scaling limit, both clocks share the same σ-scaling,
    so their dimensionless ratio is invariant.
    """
    if not (nu_a0 > 0.0 and math.isfinite(nu_a0)):
        raise ValueError("nu_a0 must be positive and finite")
    if not (nu_b0 > 0.0 and math.isfinite(nu_b0)):
        raise ValueError("nu_b0 must be positive and finite")
    ex = universal_scaling_exponents()
    p_atom = float(ex["nu_atomic"])

    nu_a_rel = float(nu_a0) * _scaling_factor(sigma=sigma, sigma_ref=sigma_ref, power=p_atom)
    nu_b_rel = float(nu_b0) * _scaling_factor(sigma=sigma, sigma_ref=sigma_ref, power=p_atom)

    # By construction at sigma_ref, the relative scaling is 1.
    ratio = (nu_a_rel / nu_b_rel) / (float(nu_a0) / float(nu_b0))
    return float(ratio)
