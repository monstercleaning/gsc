"""SigmaTensor-v1: action-based background solver (Phase-3 scaffolding).

Model scope:
- Einstein-frame canonical scalar + standard matter/radiation sectors
- background dynamics only (no perturbations / Boltzmann hierarchy)
- deterministic fixed-grid RK4 integration in x=ln(a)
"""

from __future__ import annotations

from dataclasses import dataclass
import bisect
import math
from typing import Dict, List, Mapping, Optional, Tuple

from ..datasets.base import HzModel
from ..early_time.rd import omega_r_h2
from ..measurement_model import MPC_SI


_DENOM_EPS = 1.0e-10


@dataclass(frozen=True)
class SigmaTensorV1Params:
    H0_si: float
    Omega_m0: float
    w_phi0: float
    lambda_: float
    Tcmb_K: float = 2.7255
    N_eff: float = 3.046
    Omega_r0_override: Optional[float] = None
    sign_u0: int = +1


@dataclass(frozen=True)
class SigmaTensorV1Background:
    params: SigmaTensorV1Params
    z_grid: List[float]
    H_grid_si: List[float]
    phi_grid: List[float]
    u_grid: List[float]
    wphi_grid: List[float]
    Omphi_grid: List[float]
    meta: Dict[str, float]


class SigmaTensorV1History(HzModel):
    """Interpolation wrapper exposing H(z) and auxiliary background curves."""

    def __init__(self, background: SigmaTensorV1Background) -> None:
        self._bg = background
        self._z = tuple(float(x) for x in background.z_grid)
        self._H = tuple(float(x) for x in background.H_grid_si)
        self._phi = tuple(float(x) for x in background.phi_grid)
        self._u = tuple(float(x) for x in background.u_grid)
        self._wphi = tuple(float(x) for x in background.wphi_grid)
        self._omphi = tuple(float(x) for x in background.Omphi_grid)
        if len(self._z) < 2:
            raise ValueError("z_grid must contain at least two points")
        if any(self._z[i] > self._z[i + 1] for i in range(len(self._z) - 1)):
            raise ValueError("z_grid must be ascending")

    @property
    def background(self) -> SigmaTensorV1Background:
        return self._bg

    def _interp(self, z: float, ys: Tuple[float, ...]) -> float:
        zz = float(z)
        if not math.isfinite(zz):
            raise ValueError("z must be finite")
        z0 = self._z[0]
        z1 = self._z[-1]
        eps = 1.0e-12 * max(1.0, abs(z1))
        if zz < (z0 - eps) or zz > (z1 + eps):
            raise ValueError(f"z={zz} outside solved range [{z0}, {z1}]")
        if zz < z0:
            zz = z0
        if zz > z1:
            zz = z1
        idx = bisect.bisect_left(self._z, zz)
        if idx == 0:
            return ys[0]
        if idx >= len(self._z):
            return ys[-1]
        if self._z[idx] == zz:
            return ys[idx]
        zl = self._z[idx - 1]
        zr = self._z[idx]
        yl = ys[idx - 1]
        yr = ys[idx]
        t = (zz - zl) / (zr - zl)
        return float(yl + (yr - yl) * t)

    def H(self, z: float) -> float:
        return self._interp(z, self._H)

    def E(self, z: float) -> float:
        return self.H(z) / float(self._bg.params.H0_si)

    def phi(self, z: float) -> float:
        return self._interp(z, self._phi)

    def u(self, z: float) -> float:
        return self._interp(z, self._u)

    def w_phi(self, z: float) -> float:
        return self._interp(z, self._wphi)

    def Omega_phi(self, z: float) -> float:
        return self._interp(z, self._omphi)


def omega_r0_from_H0_Tcmb_Neff(H0_si: float, Tcmb_K: float, N_eff: float) -> float:
    """Compute present radiation fraction Omega_r0 from (H0, Tcmb, N_eff)."""
    h = float(H0_si) * float(MPC_SI) / 1000.0 / 100.0
    if not (h > 0.0 and math.isfinite(h)):
        raise ValueError("H0_si must be positive and finite")
    or_h2 = float(omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(N_eff)))
    out = or_h2 / (h * h)
    if not (out >= 0.0 and math.isfinite(out)):
        raise ValueError("computed Omega_r0 is not finite")
    return float(out)


def _validate_params(params: SigmaTensorV1Params) -> None:
    if not (float(params.H0_si) > 0.0 and math.isfinite(float(params.H0_si))):
        raise ValueError("H0_si must be positive and finite")
    if not (float(params.Omega_m0) >= 0.0 and math.isfinite(float(params.Omega_m0))):
        raise ValueError("Omega_m0 must be finite and >= 0")
    if not (math.isfinite(float(params.w_phi0)) and float(params.w_phi0) >= -1.0 and float(params.w_phi0) < 1.0):
        raise ValueError("w_phi0 must be finite and in [-1,1)")
    if not (float(params.lambda_) >= 0.0 and math.isfinite(float(params.lambda_))):
        raise ValueError("lambda_ must be finite and >= 0")
    if int(params.sign_u0) not in (-1, +1):
        raise ValueError("sign_u0 must be +1 or -1")
    if not (float(params.Tcmb_K) > 0.0 and math.isfinite(float(params.Tcmb_K))):
        raise ValueError("Tcmb_K must be positive and finite")
    if not (float(params.N_eff) >= 0.0 and math.isfinite(float(params.N_eff))):
        raise ValueError("N_eff must be finite and >= 0")
    if params.Omega_r0_override is not None:
        if not (float(params.Omega_r0_override) >= 0.0 and math.isfinite(float(params.Omega_r0_override))):
            raise ValueError("Omega_r0_override must be finite and >= 0")


def _initial_conditions(params: SigmaTensorV1Params) -> Dict[str, float]:
    Omega_r0 = (
        float(params.Omega_r0_override)
        if params.Omega_r0_override is not None
        else omega_r0_from_H0_Tcmb_Neff(float(params.H0_si), float(params.Tcmb_K), float(params.N_eff))
    )
    Omega_phi0 = 1.0 - float(params.Omega_m0) - float(Omega_r0)
    if not (Omega_phi0 > 0.0 and math.isfinite(Omega_phi0)):
        raise ValueError("Derived Omega_phi0 must be positive; adjust Omega_m0 / Omega_r0")

    one_plus_w0 = 1.0 + float(params.w_phi0)
    if one_plus_w0 < 0.0:
        raise ValueError("Canonical scalar requires w_phi0 >= -1")
    u0 = int(params.sign_u0) * math.sqrt(max(0.0, 3.0 * Omega_phi0 * one_plus_w0))
    Vhat0 = 0.5 * Omega_phi0 * (1.0 - float(params.w_phi0))

    if not (Vhat0 >= 0.0 and math.isfinite(Vhat0)):
        raise ValueError("Derived Vhat0 must be finite and >= 0")

    p_action = 0.5 * float(params.lambda_) * float(params.lambda_)

    return {
        "Omega_r0": float(Omega_r0),
        "Omega_phi0": float(Omega_phi0),
        "u0": float(u0),
        "Vhat0": float(Vhat0),
        "p_action": float(p_action),
    }


def _state_terms(
    *,
    x: float,
    phi: float,
    u: float,
    Omega_m0: float,
    Omega_r0: float,
    Vhat0: float,
    lambda_: float,
) -> Dict[str, float]:
    try:
        v = float(Vhat0) * math.exp(-float(lambda_) * float(phi))
    except OverflowError as exc:
        raise ValueError("Potential overflow in exp(-lambda*phi)") from exc

    exp3 = math.exp(-3.0 * float(x))
    exp4 = math.exp(-4.0 * float(x))
    denom = 1.0 - (float(u) * float(u)) / 6.0
    if not (denom > _DENOM_EPS and math.isfinite(denom)):
        raise ValueError("Friedmann denominator collapse: 1-u^2/6 <= 0")

    num = float(Omega_m0) * exp3 + float(Omega_r0) * exp4 + float(v)
    E2 = num / denom
    if not (E2 > 0.0 and math.isfinite(E2)):
        raise ValueError("Non-physical E^2 encountered")

    u2_over_6 = (float(u) * float(u)) / 6.0
    v_over_E2 = float(v) / float(E2)
    rad_over_3E2 = (float(Omega_r0) * exp4) / (3.0 * float(E2))
    w_eff = rad_over_3E2 + u2_over_6 - v_over_E2
    dlnHdx = -1.5 * (1.0 + w_eff)

    Omega_phi = u2_over_6 + v_over_E2
    if not (Omega_phi > 0.0 and math.isfinite(Omega_phi)):
        raise ValueError("Non-physical Omega_phi encountered")

    w_phi = (u2_over_6 - v_over_E2) / Omega_phi
    if not math.isfinite(w_phi):
        raise ValueError("Non-finite w_phi encountered")

    return {
        "v": float(v),
        "E2": float(E2),
        "w_eff": float(w_eff),
        "dlnHdx": float(dlnHdx),
        "Omega_phi": float(Omega_phi),
        "w_phi": float(w_phi),
    }


def _rhs(
    *,
    x: float,
    phi: float,
    u: float,
    Omega_m0: float,
    Omega_r0: float,
    Vhat0: float,
    lambda_: float,
) -> Tuple[float, float]:
    terms = _state_terms(
        x=x,
        phi=phi,
        u=u,
        Omega_m0=Omega_m0,
        Omega_r0=Omega_r0,
        Vhat0=Vhat0,
        lambda_=lambda_,
    )
    du = -(3.0 + float(terms["dlnHdx"])) * float(u) + (3.0 * float(lambda_) * float(terms["v"])) / float(terms["E2"])
    if not math.isfinite(du):
        raise ValueError("Non-finite u' encountered")
    return float(u), float(du)


def solve_sigmatensor_v1_background(
    params: SigmaTensorV1Params,
    *,
    z_max: float = 5.0,
    n_steps: int = 2048,
) -> SigmaTensorV1Background:
    """Solve SigmaTensor-v1 background on a fixed x=ln(a) grid."""
    _validate_params(params)
    if not (float(z_max) > 0.0 and math.isfinite(float(z_max))):
        raise ValueError("z_max must be finite and > 0")
    if int(n_steps) < 2:
        raise ValueError("n_steps must be >= 2")

    ic = _initial_conditions(params)
    Omega_r0 = float(ic["Omega_r0"])
    Omega_phi0 = float(ic["Omega_phi0"])
    u0 = float(ic["u0"])
    Vhat0 = float(ic["Vhat0"])
    p_action = float(ic["p_action"])

    x0 = 0.0
    x_end = -math.log(1.0 + float(z_max))
    n = int(n_steps)
    h = (x_end - x0) / float(n)

    phi = 0.0
    u = float(u0)

    z_grid: List[float] = []
    H_grid_si: List[float] = []
    phi_grid: List[float] = []
    u_grid: List[float] = []
    wphi_grid: List[float] = []
    Omphi_grid: List[float] = []

    for i in range(n + 1):
        x = x0 + float(i) * h
        terms = _state_terms(
            x=x,
            phi=phi,
            u=u,
            Omega_m0=float(params.Omega_m0),
            Omega_r0=Omega_r0,
            Vhat0=Vhat0,
            lambda_=float(params.lambda_),
        )
        z = math.exp(-x) - 1.0
        E = math.sqrt(float(terms["E2"]))
        H_si = float(params.H0_si) * E

        z_grid.append(float(z))
        H_grid_si.append(float(H_si))
        phi_grid.append(float(phi))
        u_grid.append(float(u))
        wphi_grid.append(float(terms["w_phi"]))
        Omphi_grid.append(float(terms["Omega_phi"]))

        if i == n:
            break

        k1_phi, k1_u = _rhs(
            x=x,
            phi=phi,
            u=u,
            Omega_m0=float(params.Omega_m0),
            Omega_r0=Omega_r0,
            Vhat0=Vhat0,
            lambda_=float(params.lambda_),
        )
        k2_phi, k2_u = _rhs(
            x=x + 0.5 * h,
            phi=phi + 0.5 * h * k1_phi,
            u=u + 0.5 * h * k1_u,
            Omega_m0=float(params.Omega_m0),
            Omega_r0=Omega_r0,
            Vhat0=Vhat0,
            lambda_=float(params.lambda_),
        )
        k3_phi, k3_u = _rhs(
            x=x + 0.5 * h,
            phi=phi + 0.5 * h * k2_phi,
            u=u + 0.5 * h * k2_u,
            Omega_m0=float(params.Omega_m0),
            Omega_r0=Omega_r0,
            Vhat0=Vhat0,
            lambda_=float(params.lambda_),
        )
        k4_phi, k4_u = _rhs(
            x=x + h,
            phi=phi + h * k3_phi,
            u=u + h * k3_u,
            Omega_m0=float(params.Omega_m0),
            Omega_r0=Omega_r0,
            Vhat0=Vhat0,
            lambda_=float(params.lambda_),
        )

        phi = phi + (h / 6.0) * (k1_phi + 2.0 * k2_phi + 2.0 * k3_phi + k4_phi)
        u = u + (h / 6.0) * (k1_u + 2.0 * k2_u + 2.0 * k3_u + k4_u)
        if not (math.isfinite(phi) and math.isfinite(u)):
            raise ValueError("Non-finite integration state encountered")

    meta: Dict[str, float] = {
        "Omega_r0": Omega_r0,
        "Omega_phi0": Omega_phi0,
        "u0": u0,
        "Vhat0": Vhat0,
        "p_action": p_action,
    }

    return SigmaTensorV1Background(
        params=params,
        z_grid=z_grid,
        H_grid_si=H_grid_si,
        phi_grid=phi_grid,
        u_grid=u_grid,
        wphi_grid=wphi_grid,
        Omphi_grid=Omphi_grid,
        meta=meta,
    )


__all__ = [
    "SigmaTensorV1Params",
    "SigmaTensorV1Background",
    "SigmaTensorV1History",
    "omega_r0_from_H0_Tcmb_Neff",
    "solve_sigmatensor_v1_background",
]
