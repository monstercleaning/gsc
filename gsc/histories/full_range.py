"""E2.7 diagnostic-only full-range histories (no-stitch).

Design goals
------------
- Diagnostic / opt-in only: must not affect canonical late-time outputs.
- Unified H(z) over z in [0, z*] for early-time closure experiments.
- Include an explicit BBN safety guardrail: at very high z, enforce LCDM+rad.

This module uses only stdlib `math` (no numpy, no astropy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Optional

from ..measurement_model import MPC_SI
from ..early_time.rd import omega_r_h2


def _H0_si_to_h(H0_si: float) -> float:
    """Return little-h given H0 in SI [1/s]."""
    if not (H0_si > 0.0 and math.isfinite(H0_si)):
        raise ValueError("H0 must be positive and finite")
    H0_km_s_Mpc = float(H0_si) * float(MPC_SI) / 1000.0
    return float(H0_km_s_Mpc) / 100.0


def _Omega_r_from_H0_Tcmb_Neff(*, H0_si: float, Tcmb_K: float, N_eff: float) -> float:
    """Return Omega_r given H0 and (Tcmb, N_eff)."""
    h = _H0_si_to_h(float(H0_si))
    or_h2 = float(omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(N_eff)))
    Omega_r = float(or_h2) / (h * h)
    if not (Omega_r >= 0.0 and math.isfinite(Omega_r)):
        raise ValueError("Omega_r must be finite and >= 0")
    return float(Omega_r)


@dataclass(frozen=True)
class FlatLCDMRadHistory:
    """Flat LCDM history including radiation (diagnostic baseline reference)."""

    H0: float
    Omega_m: float
    N_eff: float = 3.046
    Tcmb_K: float = 2.7255

    Omega_r: float = field(init=False)
    Omega_Lambda: float = field(init=False)

    def __post_init__(self) -> None:
        if not (self.H0 > 0.0 and math.isfinite(self.H0)):
            raise ValueError("H0 must be positive and finite")
        if not (0.0 < float(self.Omega_m) < 1.0 and math.isfinite(self.Omega_m)):
            raise ValueError("Omega_m must be finite and in (0,1)")
        if not (self.Tcmb_K > 0.0 and math.isfinite(self.Tcmb_K)):
            raise ValueError("Tcmb_K must be positive and finite")
        if not (self.N_eff >= 0.0 and math.isfinite(self.N_eff)):
            raise ValueError("N_eff must be finite and >= 0")

        Omega_r = _Omega_r_from_H0_Tcmb_Neff(H0_si=float(self.H0), Tcmb_K=float(self.Tcmb_K), N_eff=float(self.N_eff))
        Omega_L = 1.0 - float(self.Omega_m) - float(Omega_r)
        if Omega_L < 0.0:
            raise ValueError("Derived Omega_Lambda < 0; adjust inputs")

        object.__setattr__(self, "Omega_r", float(Omega_r))
        object.__setattr__(self, "Omega_Lambda", float(Omega_L))

    def H(self, z: float) -> float:
        if z < -1.0:
            raise ValueError("Require z >= -1")
        one_p = 1.0 + float(z)
        Ez2 = float(self.Omega_r) * one_p**4 + float(self.Omega_m) * one_p**3 + float(self.Omega_Lambda)
        if not (Ez2 > 0.0 and math.isfinite(Ez2)):
            raise ValueError("Non-physical E(z)^2")
        return float(self.H0) * math.sqrt(Ez2)


@dataclass(frozen=True)
class GSCTransitionFullHistory:
    """Full-range diagnostic history: late-time GSC transition + high-z relaxation.

    Construction (diagnostic):
    - The "GSC component" is the canonical late-time transition model (LCDM-like
      at z<=z_transition, power-law above), with a relaxed exponent p_eff(z)
      approaching 1.5 at high z (matter-era slope).
    - Radiation is added as an explicit standard term in quadrature:
        H(z)^2 = H_gsc(z)^2 + H_rad(z)^2
      where H_rad(z) = H0 * sqrt(Omega_r) * (1+z)^2.

    Optional BBN guardrail:
    - for z >= z_bbn_clamp, we *force* H(z)=H_LCDM+rad(z).
      This is a diagnostic safety clamp (recorded in manifests), not a claim.
    """

    H0: float
    Omega_m: float
    p_late: float
    z_transition: float
    z_relax: float = math.inf
    z_relax_start: Optional[float] = None
    p_target: float = 1.5
    N_eff: float = 3.046
    Tcmb_K: float = 2.7255
    z_bbn_clamp: Optional[float] = 1.0e7

    Omega_r: float = field(init=False)
    Omega_Lambda: float = field(init=False)
    _lcdm_rad: FlatLCDMRadHistory = field(init=False, repr=False)
    _H_gsc_at_zt: float = field(init=False, repr=False)
    _H_gsc_at_relax_start: float = field(init=False, repr=False)
    _z_relax_start_eff: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not (self.H0 > 0.0 and math.isfinite(self.H0)):
            raise ValueError("H0 must be positive and finite")
        if not (0.0 < float(self.Omega_m) < 1.0 and math.isfinite(self.Omega_m)):
            raise ValueError("Omega_m must be finite and in (0,1)")
        if not (self.p_late > 0.0 and math.isfinite(self.p_late)):
            raise ValueError("p_late must be finite and > 0")
        if not (self.z_transition >= 0.0 and math.isfinite(self.z_transition)):
            raise ValueError("z_transition must be finite and >= 0")
        if not (math.isfinite(self.z_relax) or math.isinf(self.z_relax)):
            raise ValueError("z_relax must be finite or inf")
        if math.isfinite(self.z_relax) and not (self.z_relax > 0.0):
            raise ValueError("z_relax must be > 0 (or inf for no relax)")
        if self.z_relax_start is not None:
            if not (math.isfinite(float(self.z_relax_start)) and float(self.z_relax_start) >= 0.0):
                raise ValueError("z_relax_start must be finite and >= 0, or None")
            if float(self.z_relax_start) < float(self.z_transition):
                raise ValueError("z_relax_start must be >= z_transition")
        if not (self.p_target > 0.0 and math.isfinite(self.p_target)):
            raise ValueError("p_target must be finite and > 0")
        if self.z_bbn_clamp is not None:
            if not (self.z_bbn_clamp > 0.0 and math.isfinite(float(self.z_bbn_clamp))):
                raise ValueError("z_bbn_clamp must be finite and > 0, or None")

        Omega_r = _Omega_r_from_H0_Tcmb_Neff(H0_si=float(self.H0), Tcmb_K=float(self.Tcmb_K), N_eff=float(self.N_eff))
        Omega_L = 1.0 - float(self.Omega_m) - float(Omega_r)
        if Omega_L < 0.0:
            raise ValueError("Derived Omega_Lambda < 0; adjust inputs")

        lcdm_rad = FlatLCDMRadHistory(
            H0=float(self.H0),
            Omega_m=float(self.Omega_m),
            N_eff=float(self.N_eff),
            Tcmb_K=float(self.Tcmb_K),
        )

        zt = float(self.z_transition)
        H_zt = float(self.H0) * math.sqrt(float(self.Omega_m) * (1.0 + zt) ** 3 + float(Omega_L))
        if not (H_zt > 0.0 and math.isfinite(H_zt)):
            raise ValueError("Non-physical H(z_transition) for GSC component")

        zrs_eff = float(self.z_relax_start) if self.z_relax_start is not None else float(self.z_transition)
        if zrs_eff < zt:
            raise ValueError("internal error: z_relax_start_eff < z_transition")
        if zrs_eff == zt:
            H_zrs = float(H_zt)
        else:
            ratio = (1.0 + float(zrs_eff)) / (1.0 + float(zt))
            H_zrs = float(H_zt) * (ratio ** float(self.p_late))
        if not (H_zrs > 0.0 and math.isfinite(H_zrs)):
            raise ValueError("Non-physical H(z_relax_start) for GSC component")

        object.__setattr__(self, "Omega_r", float(Omega_r))
        object.__setattr__(self, "Omega_Lambda", float(Omega_L))
        object.__setattr__(self, "_lcdm_rad", lcdm_rad)
        object.__setattr__(self, "_H_gsc_at_zt", float(H_zt))
        object.__setattr__(self, "_H_gsc_at_relax_start", float(H_zrs))
        object.__setattr__(self, "_z_relax_start_eff", float(zrs_eff))

    def _p_eff(self, z: float) -> float:
        """Effective exponent for the high-z (z>z_transition) GSC component."""
        if z <= float(self.z_transition):
            return float(self.p_late)
        if math.isinf(float(self.z_relax)):
            return float(self.p_late)
        if self.z_relax_start is None:
            dz = float(z) - float(self.z_transition)
            relax = float(self.z_relax)
            # Legacy: p_eff transitions from p_late at z=z_transition to p_target as z grows.
            return float(self.p_late) + (float(self.p_target) - float(self.p_late)) * (1.0 - math.exp(-dz / relax))

        # Guarded mode: keep exact power-law until z_relax_start, then relax in x=ln((1+z)/(1+z_relax_start)).
        zrs = float(self._z_relax_start_eff)
        if z <= zrs:
            return float(self.p_late)
        x = math.log((1.0 + float(z)) / (1.0 + float(zrs)))
        relax_x = float(self.z_relax)  # interpreted as a scale in x-units
        return float(self.p_late) + (float(self.p_target) - float(self.p_late)) * (1.0 - math.exp(-x / relax_x))

    def _H_gsc_component(self, z: float) -> float:
        """Return the late-time/GSC component (no radiation) in SI [1/s]."""
        if z <= float(self.z_transition):
            one_p = 1.0 + float(z)
            Ez2 = float(self.Omega_m) * one_p**3 + float(self.Omega_Lambda)
            if not (Ez2 > 0.0 and math.isfinite(Ez2)):
                raise ValueError("Non-physical E(z)^2 in GSC component")
            return float(self.H0) * math.sqrt(Ez2)

        # Legacy mode: relax starts at z_transition and uses the historical (non-integrated) exponent map.
        if self.z_relax_start is None:
            ratio = (1.0 + float(z)) / (1.0 + float(self.z_transition))
            p_eff = self._p_eff(float(z))
            return float(self._H_gsc_at_zt) * (ratio**float(p_eff))

        # Guarded mode: keep exact power-law until z_relax_start, then relax in log-space with an analytic integral.
        zrs = float(self._z_relax_start_eff)
        if z <= zrs:
            ratio = (1.0 + float(z)) / (1.0 + float(self.z_transition))
            return float(self._H_gsc_at_zt) * (ratio**float(self.p_late))

        H_start = float(self._H_gsc_at_relax_start)
        if math.isinf(float(self.z_relax)):
            ratio = (1.0 + float(z)) / (1.0 + float(zrs))
            return float(H_start) * (ratio**float(self.p_late))

        # x = ln((1+z)/(1+zrs)), and define p_eff(x) = p_late + (p_target-p_late)*(1-exp(-x/s)).
        x = math.log((1.0 + float(z)) / (1.0 + float(zrs)))
        s = float(self.z_relax)  # scale in x-units
        p0 = float(self.p_late)
        pt = float(self.p_target)
        # ∫_0^x p_eff(x') dx' = pt*x - (pt-p0)*s*(1-exp(-x/s))
        integral = pt * x - (pt - p0) * s * (1.0 - math.exp(-x / s))
        return float(H_start) * math.exp(float(integral))

    def H(self, z: float) -> float:
        if z < -1.0:
            raise ValueError("Require z >= -1")
        if self.z_bbn_clamp is not None and float(z) >= float(self.z_bbn_clamp):
            return float(self._lcdm_rad.H(float(z)))

        H_gsc = float(self._H_gsc_component(float(z)))
        one_p = 1.0 + float(z)
        H_rad = float(self.H0) * math.sqrt(float(self.Omega_r)) * (one_p**2)
        Hz2 = float(H_gsc) * float(H_gsc) + float(H_rad) * float(H_rad)
        if not (Hz2 > 0.0 and math.isfinite(Hz2)):
            raise ValueError("Non-physical H(z)^2 in full history")
        return math.sqrt(Hz2)


def _smoothstep01(t: float) -> float:
    """C1 smoothstep on [0,1]."""
    x = float(t)
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return float(x * x * (3.0 - 2.0 * x))


@dataclass(frozen=True)
class HBoostWrapper:
    """Diagnostic-only multiplicative H(z) deformation A(z) applied above a guard redshift.

    This exists to test early-time "distance closure" requirements while preserving the
    late-time drift window (choose `z_boost_start >= 5`).

    Contract:
    - A(z)=1 for z <= z_boost_start (protect the drift window).
    - A(z)=1 for z >= z_bbn_clamp (preserve the BBN safety clamp).
    - Optional: A(z)=1 for z >= z_boost_end (finite support).
    """

    base_history: object = field(repr=False)
    z_boost_start: float
    z_boost_end: Optional[float] = None
    z_bbn_clamp: Optional[float] = None
    transition_width: float = 0.0

    boost_mode: str = "const"
    A_const: float = 1.0

    # Logistic mode parameters (diagnostic-only).
    Amax: float = 1.0
    z0: float = 10.0
    width: float = 1.0

    def __post_init__(self) -> None:
        if not hasattr(self.base_history, "H"):
            raise ValueError("base_history must expose H(z)")
        if not (math.isfinite(float(self.z_boost_start)) and float(self.z_boost_start) >= 0.0):
            raise ValueError("z_boost_start must be finite and >= 0")
        if self.z_boost_end is not None:
            if not (math.isfinite(float(self.z_boost_end)) and float(self.z_boost_end) > float(self.z_boost_start)):
                raise ValueError("z_boost_end must be finite and > z_boost_start, or None")
        if self.z_bbn_clamp is not None:
            if not (math.isfinite(float(self.z_bbn_clamp)) and float(self.z_bbn_clamp) > 0.0):
                raise ValueError("z_bbn_clamp must be finite and > 0, or None")
        if not (math.isfinite(float(self.transition_width)) and float(self.transition_width) >= 0.0):
            raise ValueError("transition_width must be finite and >= 0")

        mode = str(self.boost_mode).strip().lower()
        if mode not in ("const", "logistic"):
            raise ValueError("boost_mode must be 'const' or 'logistic'")
        object.__setattr__(self, "boost_mode", mode)

        if not (float(self.A_const) > 0.0 and math.isfinite(float(self.A_const))):
            raise ValueError("A_const must be finite and > 0")
        if not (float(self.Amax) > 0.0 and math.isfinite(float(self.Amax))):
            raise ValueError("Amax must be finite and > 0")
        if not (math.isfinite(float(self.z0))):
            raise ValueError("z0 must be finite")
        if not (float(self.width) > 0.0 and math.isfinite(float(self.width))):
            raise ValueError("width must be finite and > 0")

    def _A_raw(self, z: float) -> float:
        mode = str(self.boost_mode)
        if mode == "const":
            return float(self.A_const)
        # logistic
        x = (float(z) - float(self.z0)) / float(self.width)
        # stable logistic
        if x >= 0:
            ex = math.exp(-x)
            s = 1.0 / (1.0 + ex)
        else:
            ex = math.exp(x)
            s = ex / (1.0 + ex)
        return 1.0 + (float(self.Amax) - 1.0) * float(s)

    def A(self, z: float) -> float:
        """Return the multiplicative deformation A(z)."""
        zz = float(z)
        if zz <= float(self.z_boost_start):
            return 1.0
        if self.z_boost_end is not None and zz >= float(self.z_boost_end):
            return 1.0
        if self.z_bbn_clamp is not None and zz >= float(self.z_bbn_clamp):
            return 1.0

        A = float(self._A_raw(zz))
        if not (A > 0.0 and math.isfinite(A)):
            raise ValueError("Non-physical A(z)")

        tw = float(self.transition_width)
        if tw > 0.0 and zz < float(self.z_boost_start) + tw:
            t = (zz - float(self.z_boost_start)) / tw
            s = _smoothstep01(float(t))
            A = 1.0 + (float(A) - 1.0) * float(s)
        return float(A)

    def H(self, z: float) -> float:
        Hz = float(self.base_history.H(float(z)))
        if not (Hz > 0.0 and math.isfinite(Hz)):
            raise ValueError("base_history.H(z) must be finite and > 0")
        return float(Hz) * float(self.A(float(z)))
