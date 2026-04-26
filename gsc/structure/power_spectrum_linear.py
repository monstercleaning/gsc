"""Linear matter power-spectrum baseline (stdlib-only).

This module provides a deterministic approximation-first bridge from primordial
curvature amplitude (A_s, n_s) to linear matter power observables
(P(k), sigma_R, sigma8, f*sigma8). It is intended for diagnostic use and does
not replace a full Boltzmann hierarchy.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, Iterable, List, Mapping, Optional

from .growth_factor import growth_observables_from_solution, solve_growth_ln_a
from .transfer_bbks import transfer_bbks
from .transfer_eh98 import transfer_eh98_nowiggle

C_KM_S = 299792.458
DEFAULT_K0_MPC = 0.05
DEFAULT_K_PIVOT_MPC = DEFAULT_K0_MPC


def _finite(value: float, *, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _finite_positive(value: float, *, name: str) -> float:
    out = _finite(value, name=name)
    if out <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return out


def _validate_k_bounds(kmin: float, kmax: float, nk: int) -> None:
    k_lo = _finite_positive(float(kmin), name="kmin")
    k_hi = _finite_positive(float(kmax), name="kmax")
    if k_hi <= k_lo:
        raise ValueError("kmax must be > kmin")
    if int(nk) < 8:
        raise ValueError("nk must be >= 8")


def _resolve_k_pivot(*, k0_mpc: float, k_pivot_mpc: Optional[float]) -> float:
    if k_pivot_mpc is None:
        return _finite_positive(float(k0_mpc), name="k0_mpc")
    return _finite_positive(float(k_pivot_mpc), name="k_pivot_mpc")


def _canonical_transfer_model(name: str) -> str:
    raw = str(name).strip().lower()
    if raw in {"bbks"}:
        return "bbks"
    if raw in {"eh98", "eh98_nowiggle"}:
        return "eh98_nowiggle"
    raise ValueError("unsupported transfer model; expected one of: bbks, eh98_nowiggle")


def transfer_units_for_model(model: str) -> str:
    """Return the canonical k-unit convention for transfer backends."""
    _ = _canonical_transfer_model(model)
    return "k in 1/Mpc"


def _default_E_of_z(z: float, *, omega_m0: float, omega_lambda0: float) -> float:
    zz = _finite(float(z), name="z")
    if zz <= -1.0:
        raise ValueError("z must satisfy z > -1")
    e2 = float(omega_m0) * (1.0 + zz) ** 3 + float(omega_lambda0)
    if not (math.isfinite(e2) and e2 > 0.0):
        raise ValueError("invalid E(z)^2 for default LCDM background")
    return float(math.sqrt(e2))


def _solve_growth_obs(
    z_targets: Iterable[float],
    *,
    omega_m0: float,
    z_start: float,
    n_steps: int,
    eps_dlnH: float,
    E_of_z: Optional[Callable[[float], float]] = None,
    omega_lambda0: Optional[float] = None,
) -> Mapping[str, List[float]]:
    if E_of_z is None:
        if omega_lambda0 is None:
            omega_lambda0 = 1.0 - float(omega_m0)

        def E_callable(z: float) -> float:
            return _default_E_of_z(z, omega_m0=float(omega_m0), omega_lambda0=float(omega_lambda0))

    else:

        def E_callable(z: float) -> float:
            e_val = _finite_positive(float(E_of_z(float(z))), name="E(z)")
            return float(e_val)

    sol = solve_growth_ln_a(
        E_callable,
        float(omega_m0),
        z_start=float(z_start),
        z_targets=[float(z) for z in z_targets],
        n_steps=int(n_steps),
        eps_dlnH=float(eps_dlnH),
    )
    return growth_observables_from_solution(sol, [float(z) for z in z_targets])


def primordial_power_law(
    k_mpc: float,
    A_s: float,
    n_s: float,
    k_pivot_mpc: float = DEFAULT_K_PIVOT_MPC,
) -> float:
    """Dimensionless primordial power-law factor.

    Approximation-first convention:
      P_R(k) factor ~ A_s * (k / k_pivot)^(n_s - 1)
    with k in 1/Mpc.
    """
    k = _finite_positive(float(k_mpc), name="k_mpc")
    a_s = _finite_positive(float(A_s), name="A_s")
    n_s_val = _finite(float(n_s), name="n_s")
    k_pivot = _finite_positive(float(k_pivot_mpc), name="k_pivot_mpc")
    out = a_s * (k / k_pivot) ** (n_s_val - 1.0)
    if not (math.isfinite(out) and out > 0.0):
        raise ValueError("non-finite primordial_power_law")
    return float(out)


def primordial_delta2_R(
    k_mpc: float,
    As: float,
    ns: float,
    k0_mpc: float = DEFAULT_K0_MPC,
    k_pivot_mpc: Optional[float] = None,
) -> float:
    """Dimensionless primordial curvature spectrum Delta^2_R(k)."""
    k_pivot = _resolve_k_pivot(k0_mpc=float(k0_mpc), k_pivot_mpc=k_pivot_mpc)
    return primordial_power_law(float(k_mpc), float(As), float(ns), float(k_pivot))


def primordial_P_R(
    k_mpc: float,
    As: float,
    ns: float,
    k0_mpc: float = DEFAULT_K0_MPC,
    k_pivot_mpc: Optional[float] = None,
) -> float:
    """Primordial curvature power P_R(k) = (2*pi^2/k^3) * Delta^2_R(k)."""
    k = _finite_positive(float(k_mpc), name="k_mpc")
    delta2 = primordial_delta2_R(
        k,
        float(As),
        float(ns),
        k0_mpc=float(k0_mpc),
        k_pivot_mpc=k_pivot_mpc,
    )
    out = (2.0 * math.pi * math.pi / (k**3.0)) * delta2
    if not (math.isfinite(out) and out > 0.0):
        raise ValueError("non-finite primordial_P_R")
    return float(out)


def M_kz_from_curvature(k_mpc: float, z: float, omega_m0: float, h: float, Tk: float, Dz: float) -> float:
    """GR baseline mapping from primordial curvature to linear matter overdensity.

    M(k,z) = (2/5) * (k^2 T(k) D(z)) / (Omega_m * (H0/c)^2)
    with H0/c in 1/Mpc when H0 is in km/s/Mpc and c in km/s.
    """
    _ = _finite(float(z), name="z")
    k = _finite_positive(float(k_mpc), name="k_mpc")
    om0 = _finite_positive(float(omega_m0), name="omega_m0")
    hh = _finite_positive(float(h), name="h")
    t_k = _finite(float(Tk), name="Tk")
    d_z = _finite(float(Dz), name="Dz")

    h0_over_c = (100.0 * hh) / C_KM_S  # 1/Mpc
    denom = om0 * (h0_over_c**2.0)
    if not (math.isfinite(denom) and denom > 0.0):
        raise ValueError("invalid denominator in M(k,z)")

    out = (2.0 / 5.0) * ((k * k) * t_k * d_z) / denom
    if not math.isfinite(out):
        raise ValueError("non-finite M(k,z)")
    return float(out)


def P_mm_phys_Mpc3(
    k_mpc: float,
    z: float,
    *,
    As: float,
    ns: float,
    k0_mpc: float,
    k_pivot_mpc: Optional[float] = None,
    omega_m0: float,
    h: float,
    Tk_func: Callable[[float], float],
    D_func: Callable[[float], float],
) -> float:
    """Linear matter spectrum in physical units (Mpc^3)."""
    k = _finite_positive(float(k_mpc), name="k_mpc")
    zz = _finite(float(z), name="z")

    t_k = _finite(float(Tk_func(k)), name="Tk_func(k)")
    d_z = _finite(float(D_func(zz)), name="D_func(z)")

    m_kz = M_kz_from_curvature(k, zz, float(omega_m0), float(h), t_k, d_z)
    p_r = primordial_P_R(
        k,
        float(As),
        float(ns),
        k0_mpc=float(k0_mpc),
        k_pivot_mpc=(None if k_pivot_mpc is None else float(k_pivot_mpc)),
    )
    out = (m_kz * m_kz) * p_r
    if not (math.isfinite(out) and out >= 0.0):
        raise ValueError("non-finite P_mm_phys")
    return float(out)


def P_mm_h_Mpch3(
    k_hmpc: float,
    z: float,
    *,
    As: float,
    ns: float,
    k0_mpc: float,
    k_pivot_mpc: Optional[float] = None,
    omega_m0: float,
    h: float,
    Tk_func: Callable[[float], float],
    D_func: Callable[[float], float],
) -> float:
    """Linear matter spectrum in (Mpc/h)^3 with k in h/Mpc."""
    k_h = _finite_positive(float(k_hmpc), name="k_hmpc")
    hh = _finite_positive(float(h), name="h")
    k_phys = hh * k_h
    p_phys = P_mm_phys_Mpc3(
        k_phys,
        float(z),
        As=float(As),
        ns=float(ns),
        k0_mpc=float(k0_mpc),
        k_pivot_mpc=(None if k_pivot_mpc is None else float(k_pivot_mpc)),
        omega_m0=float(omega_m0),
        h=hh,
        Tk_func=Tk_func,
        D_func=D_func,
    )
    out = (hh**3.0) * p_phys
    if not (math.isfinite(out) and out >= 0.0):
        raise ValueError("non-finite P_mm_h")
    return float(out)


def linear_matter_pk(
    k_mpc: float,
    z: float,
    *,
    As: float,
    ns: float = 1.0,
    k_pivot_mpc: float = DEFAULT_K_PIVOT_MPC,
    omega_m0: float,
    h: float,
    Tk_func: Callable[[float], float],
    D_func: Callable[[float], float],
) -> float:
    """Convenience wrapper for linear P_mm(k,z) in physical units (Mpc^3)."""
    return P_mm_phys_Mpc3(
        float(k_mpc),
        float(z),
        As=float(As),
        ns=float(ns),
        k0_mpc=float(k_pivot_mpc),
        k_pivot_mpc=float(k_pivot_mpc),
        omega_m0=float(omega_m0),
        h=float(h),
        Tk_func=Tk_func,
        D_func=D_func,
    )


def tophat_window(x: float) -> float:
    """Spherical top-hat Fourier window W(x) with stable small-x behavior."""
    xx = _finite(float(x), name="x")
    ax = abs(xx)
    if ax < 1.0e-4:
        x2 = xx * xx
        # W(x) = 1 - x^2/10 + x^4/280 - x^6/15120 + O(x^8)
        return float(1.0 - x2 / 10.0 + (x2 * x2) / 280.0 - (x2 * x2 * x2) / 15120.0)

    sinx = math.sin(xx)
    cosx = math.cos(xx)
    out = 3.0 * (sinx - xx * cosx) / (xx**3.0)
    if not math.isfinite(out):
        raise ValueError("non-finite tophat window")
    return float(out)


def sigma_R(
    R_mpc_over_h: float,
    z: float,
    *,
    As: float,
    ns: float,
    omega_m0: float,
    h: float,
    transfer_model: str = "bbks",
    transfer: Optional[str] = None,
    omega_b0: float = 0.049,
    Tcmb_K: float = 2.7255,
    N_eff: float = 3.046,
    k0_mpc: float = DEFAULT_K0_MPC,
    k_pivot_mpc: Optional[float] = None,
    kmin: float = 1.0e-4,
    kmax: float = 1.0e2,
    nk: int = 2048,
    E_of_z: Optional[Callable[[float], float]] = None,
    omega_lambda0: Optional[float] = None,
    z_start: float = 100.0,
    n_steps: int = 4000,
    eps_dlnH: float = 1.0e-5,
) -> float:
    """Return sigma_R(z) via deterministic ln(k) integration.

    R is interpreted in Mpc/h and the k-integral is performed in h/Mpc.
    """
    model_name = _canonical_transfer_model(transfer if transfer is not None else transfer_model)
    k_pivot = _resolve_k_pivot(k0_mpc=float(k0_mpc), k_pivot_mpc=k_pivot_mpc)

    R = _finite_positive(float(R_mpc_over_h), name="R_mpc_over_h")
    zz = _finite(float(z), name="z")
    if zz < 0.0:
        raise ValueError("z must be >= 0")

    _validate_k_bounds(float(kmin), float(kmax), int(nk))
    om0 = _finite_positive(float(omega_m0), name="omega_m0")
    ob0 = _finite(float(omega_b0), name="omega_b0")
    if not (0.0 <= ob0 <= om0):
        raise ValueError("omega_b0 must satisfy 0 <= omega_b0 <= omega_m0")
    hh = _finite_positive(float(h), name="h")
    neff = _finite(float(N_eff), name="N_eff")
    if neff < 0.0:
        raise ValueError("N_eff must be >= 0")

    obs = _solve_growth_obs(
        [zz],
        omega_m0=om0,
        z_start=float(z_start),
        n_steps=int(n_steps),
        eps_dlnH=float(eps_dlnH),
        E_of_z=E_of_z,
        omega_lambda0=omega_lambda0,
    )
    Dz = float(obs["D"][0])

    omega_m_h2 = om0 * hh * hh
    omega_b_h2 = ob0 * hh * hh
    omega_c_h2 = omega_m_h2 - omega_b_h2
    if omega_c_h2 < 0.0:
        if omega_c_h2 > -1.0e-14:
            omega_c_h2 = 0.0
        else:
            raise ValueError("computed omega_c_h2 < 0; check omega_m0 and omega_b0")

    def _Tk_func(k_mpc: float) -> float:
        if model_name == "bbks":
            return transfer_bbks(
                float(k_mpc),
                Omega_m0=om0,
                Omega_b0=ob0,
                h=hh,
                Tcmb_K=float(Tcmb_K),
            )
        return transfer_eh98_nowiggle(
            float(k_mpc),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            h=hh,
            Tcmb_K=float(Tcmb_K),
            N_eff=neff,
        )

    def _D_func(_z: float) -> float:
        return float(Dz)

    ln_kmin = math.log(float(kmin))
    ln_kmax = math.log(float(kmax))
    step = (ln_kmax - ln_kmin) / float(int(nk) - 1)

    sigma2 = 0.0
    prev_val: Optional[float] = None
    for i in range(int(nk)):
        ln_k = ln_kmin + float(i) * step
        k_h = math.exp(ln_k)
        p_h = P_mm_h_Mpch3(
            k_h,
            zz,
            As=float(As),
            ns=float(ns),
            k0_mpc=float(k0_mpc),
            k_pivot_mpc=float(k_pivot),
            omega_m0=om0,
            h=hh,
            Tk_func=_Tk_func,
            D_func=_D_func,
        )
        w = tophat_window(k_h * R)
        integrand = (k_h**3.0) * p_h / (2.0 * math.pi * math.pi)
        curr_val = float(integrand * w * w)
        if prev_val is not None:
            sigma2 += 0.5 * (prev_val + curr_val) * step
        prev_val = curr_val

    if not (math.isfinite(sigma2) and sigma2 >= 0.0):
        raise ValueError("non-finite sigma_R^2")
    return float(math.sqrt(sigma2))


def sigma8_0_from_As(
    *,
    As: float,
    ns: float,
    omega_m0: float,
    h: float,
    transfer_model: str = "bbks",
    transfer: Optional[str] = None,
    omega_b0: float = 0.049,
    Tcmb_K: float = 2.7255,
    N_eff: float = 3.046,
    k0_mpc: float = DEFAULT_K0_MPC,
    k_pivot_mpc: Optional[float] = None,
    kmin: float = 1.0e-4,
    kmax: float = 1.0e2,
    nk: int = 2048,
    E_of_z: Optional[Callable[[float], float]] = None,
    omega_lambda0: Optional[float] = None,
    z_start: float = 100.0,
    n_steps: int = 4000,
    eps_dlnH: float = 1.0e-5,
) -> float:
    """Return sigma8(z=0) derived from (As, ns) under baseline assumptions."""
    return sigma_R(
        8.0,
        0.0,
        As=float(As),
        ns=float(ns),
        omega_m0=float(omega_m0),
        h=float(h),
        transfer_model=str(transfer_model),
        transfer=str(transfer) if transfer is not None else None,
        omega_b0=float(omega_b0),
        Tcmb_K=float(Tcmb_K),
        N_eff=float(N_eff),
        k0_mpc=float(k0_mpc),
        k_pivot_mpc=(None if k_pivot_mpc is None else float(k_pivot_mpc)),
        kmin=float(kmin),
        kmax=float(kmax),
        nk=int(nk),
        E_of_z=E_of_z,
        omega_lambda0=omega_lambda0,
        z_start=float(z_start),
        n_steps=int(n_steps),
        eps_dlnH=float(eps_dlnH),
    )


def sigma8_z(
    z: float,
    *,
    As: float,
    ns: float,
    omega_m0: float,
    h: float,
    transfer_model: str = "bbks",
    transfer: Optional[str] = None,
    omega_b0: float = 0.049,
    Tcmb_K: float = 2.7255,
    N_eff: float = 3.046,
    k0_mpc: float = DEFAULT_K0_MPC,
    k_pivot_mpc: Optional[float] = None,
    kmin: float = 1.0e-4,
    kmax: float = 1.0e2,
    nk: int = 2048,
    E_of_z: Optional[Callable[[float], float]] = None,
    omega_lambda0: Optional[float] = None,
    z_start: float = 100.0,
    n_steps: int = 4000,
    eps_dlnH: float = 1.0e-5,
) -> float:
    """Return sigma8(z) using sigma8(0) from As and growth scaling D(z)."""
    zz = _finite(float(z), name="z")
    if zz < 0.0:
        raise ValueError("z must be >= 0")

    s8_0 = sigma8_0_from_As(
        As=float(As),
        ns=float(ns),
        omega_m0=float(omega_m0),
        h=float(h),
        transfer_model=str(transfer_model),
        transfer=str(transfer) if transfer is not None else None,
        omega_b0=float(omega_b0),
        Tcmb_K=float(Tcmb_K),
        N_eff=float(N_eff),
        k0_mpc=float(k0_mpc),
        k_pivot_mpc=(None if k_pivot_mpc is None else float(k_pivot_mpc)),
        kmin=float(kmin),
        kmax=float(kmax),
        nk=int(nk),
        E_of_z=E_of_z,
        omega_lambda0=omega_lambda0,
        z_start=float(z_start),
        n_steps=int(n_steps),
        eps_dlnH=float(eps_dlnH),
    )

    if zz == 0.0:
        return float(s8_0)

    obs = _solve_growth_obs(
        [zz],
        omega_m0=float(omega_m0),
        z_start=float(z_start),
        n_steps=int(n_steps),
        eps_dlnH=float(eps_dlnH),
        E_of_z=E_of_z,
        omega_lambda0=omega_lambda0,
    )
    Dz = float(obs["D"][0])
    return float(s8_0 * Dz)


def fsigma8(
    z: float,
    *,
    sigma8_0: float,
    omega_m0: float,
    E_of_z: Optional[Callable[[float], float]] = None,
    omega_lambda0: Optional[float] = None,
    z_start: float = 100.0,
    n_steps: int = 4000,
    eps_dlnH: float = 1.0e-5,
) -> float:
    """Return f*sigma8(z) from growth observables and sigma8(0)."""
    s8 = _finite_positive(float(sigma8_0), name="sigma8_0")
    zz = _finite(float(z), name="z")
    if zz < 0.0:
        raise ValueError("z must be >= 0")

    obs = _solve_growth_obs(
        [zz],
        omega_m0=float(omega_m0),
        z_start=float(z_start),
        n_steps=int(n_steps),
        eps_dlnH=float(eps_dlnH),
        E_of_z=E_of_z,
        omega_lambda0=omega_lambda0,
    )
    fz = float(obs["f"][0])
    Dz = float(obs["D"][0])
    return float(fz * Dz * s8)
