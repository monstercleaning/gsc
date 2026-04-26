#!/usr/bin/env python3
"""E2.5 diagnostic: correlate late-time redshift-drift amplitudes with required CMB closure.

Purpose
-------
This script joins two diagnostic quantities over a coarse family of late-time histories:

1) late-time Sandage-Loeb redshift drift amplitudes (reported as Delta v over N years),
2) the required E2.4 distance-closure knob (dm_fit) and its E2.3 effective mapping to a
   constant high-z H(z) boost A applied above z_boost_start = bridge_z_used.

This is diagnostic-only tooling. It is not a physics claim and must not be used in the
canonical late-time paper/submission pipelines.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))

import numpy as np  # noqa: E402

from gsc.early_time import compute_bridged_distance_priors  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    C_SI,
    MPC_SI,
    SEC_PER_YR,
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
    delta_v_cm_s,
)


def _np_trapezoid(y, x) -> float:
    trap = getattr(np, "trapezoid", None)
    if callable(trap):
        return float(trap(y, x))
    trapz = getattr(np, "trapz", None)
    if callable(trapz):
        return float(trapz(y, x))
    y_arr = np.asarray(y, dtype=float)
    x_arr = np.asarray(x, dtype=float)
    if y_arr.shape != x_arr.shape:
        raise ValueError("trapezoid fallback requires x and y with matching shape")
    if int(y_arr.size) < 2:
        return 0.0
    return float(0.5 * np.sum((y_arr[1:] + y_arr[:-1]) * (x_arr[1:] - x_arr[:-1])))


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def _run_git(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(list(args), stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:  # pragma: no cover
        return f"<error: {e}>"


def _load_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = [dict(row) for row in r]
    if not rows:
        raise ValueError(f"Empty CSV: {path}")
    return rows


def _parse_bool(s: str) -> bool:
    ss = str(s).strip().lower()
    if ss in ("true", "1", "yes", "y"):
        return True
    if ss in ("false", "0", "no", "n", ""):
        return False
    raise ValueError(f"Cannot parse bool: {s!r}")


def _parse_float(s: str) -> float:
    return float(str(s).strip())


def _comoving_distance_model_to_z_Mpc(*, z: float, model, n: int = 4096) -> float:
    """Return D_M(z) in Mpc from a model's H(z) by direct integration."""
    if not (z >= 0 and math.isfinite(z)):
        raise ValueError("z must be finite and >= 0")
    if z == 0.0:
        return 0.0
    if n < 512:
        raise ValueError("integration grid too small")
    zz = np.linspace(0.0, float(z), int(n), dtype=float)
    Hz = np.asarray([float(model.H(float(zi))) for zi in zz], dtype=float)
    if not (np.isfinite(Hz).all() and float(Hz.min()) > 0.0):
        raise ValueError("H(z) must be finite and strictly positive on [0,z]")
    integral = _np_trapezoid(1.0 / Hz, zz)
    D_m = float(C_SI) * integral
    return float(D_m / float(MPC_SI))


def _effective_A_required(
    *,
    dm_fit: float,
    D_M_0_to_bridge_Mpc: float,
    D_M_bridge_to_zstar_Mpc: float,
) -> Optional[float]:
    """E2.3 mapping at z_boost_start = bridge_z: solve for constant A on [bridge,z*]."""
    if not (dm_fit > 0 and math.isfinite(dm_fit)):
        return None
    if not (D_M_0_to_bridge_Mpc >= 0 and math.isfinite(D_M_0_to_bridge_Mpc)):
        return None
    if not (D_M_bridge_to_zstar_Mpc > 0 and math.isfinite(D_M_bridge_to_zstar_Mpc)):
        return None
    D_total = float(D_M_0_to_bridge_Mpc) + float(D_M_bridge_to_zstar_Mpc)
    D_target = float(dm_fit) * float(D_total)
    denom = float(D_target) - float(D_M_0_to_bridge_Mpc)
    if not (denom > 0 and math.isfinite(denom)):
        return None
    A = float(D_M_bridge_to_zstar_Mpc) / float(denom)
    if not (A > 0 and math.isfinite(A)):
        return None
    return float(A)


def _build_history(
    *,
    model: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    gsc_p: float,
    gsc_ztrans: float,
):
    H0_si = H0_to_SI(float(H0_km_s_Mpc))
    if model == "lcdm":
        return FlatLambdaCDMHistory(H0=float(H0_si), Omega_m=float(Omega_m), Omega_Lambda=float(Omega_L))
    if model == "gsc_powerlaw":
        return PowerLawHistory(H0=float(H0_si), p=float(gsc_p))
    if model == "gsc_transition":
        return GSCTransitionHistory(
            H0=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_Lambda=float(Omega_L),
            p=float(gsc_p),
            z_transition=float(gsc_ztrans),
        )
    raise ValueError(f"Unknown model: {model!r}")


def _bridge_constants_for_z(
    *,
    bridge_z: float,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
) -> Dict[str, float]:
    """Compute quantities that depend only on early params + bridge_z (not on late-time history)."""
    H0_si = H0_to_SI(float(H0_km_s_Mpc))
    hist = FlatLambdaCDMHistory(H0=float(H0_si), Omega_m=float(Omega_m), Omega_Lambda=float(Omega_L))
    pred = compute_bridged_distance_priors(
        model=hist,
        z_bridge=float(bridge_z),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(Neff),
        Tcmb_K=float(Tcmb_K),
        rs_star_calibration=1.0,
        dm_star_calibration=1.0,
    )
    return {
        "bridge_z_used": float(pred["bridge_z"]),
        "z_star": float(pred["z_star"]),
        "D_M_bridge_to_zstar_Mpc": float(pred["D_M_bridge_to_zstar_Mpc"]),
        "Omega_m_early": float(pred["Omega_m_early"]),
        "Omega_r": float(pred["Omega_r"]),
    }


def _E_lcdm_radiation(z: np.ndarray, *, Omega_m: float, Omega_r: float, Omega_lambda: float) -> np.ndarray:
    """Return E(z) = H(z)/H0 for LCDM + radiation, vectorized."""
    one_p_z = 1.0 + np.asarray(z, dtype=float)
    return np.sqrt(float(Omega_r) * one_p_z**4 + float(Omega_m) * one_p_z**3 + float(Omega_lambda))


def _early_integral_grid(
    *,
    z0: float,
    z1: float,
    Omega_m: float,
    Omega_r: float,
    n: int = 8192,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Precompute z-grid and weights w=1/E(z) for the early-time bridge integrals."""
    if not (z1 > z0 and math.isfinite(z0) and math.isfinite(z1)):
        raise ValueError("Require z1>z0 and finite")
    if n < 512:
        raise ValueError("integration grid too small")

    z = np.linspace(float(z0), float(z1), int(n), dtype=float)
    Omega_lambda = 1.0 - float(Omega_m) - float(Omega_r)
    E = _E_lcdm_radiation(z, Omega_m=float(Omega_m), Omega_r=float(Omega_r), Omega_lambda=float(Omega_lambda))
    if not (np.isfinite(E).all() and float(E.min()) > 0.0):
        raise ValueError("Non-finite E(z) on [z0,z1]")
    w = 1.0 / E
    I0 = _np_trapezoid(w, z)
    if not (I0 > 0.0 and math.isfinite(I0)):
        raise ValueError("Non-physical early integral I0")
    return z, w, float(I0)


def _required_high_distance_ratio(*, dm_fit: float, D_low: float, D_high: float) -> Optional[float]:
    """Return r_target = D_high_target / D_high implied by dm_fit, or None if impossible."""
    if not (dm_fit > 0 and math.isfinite(dm_fit)):
        return None
    if not (D_low >= 0 and math.isfinite(D_low)):
        return None
    if not (D_high > 0 and math.isfinite(D_high)):
        return None
    D_total = float(D_low) + float(D_high)
    D_target = float(dm_fit) * float(D_total)
    D_high_target = float(D_target) - float(D_low)
    if not (D_high_target > 0 and math.isfinite(D_high_target)):
        return None
    r = float(D_high_target) / float(D_high)
    if not (r > 0 and r <= 1.0 and math.isfinite(r)):
        return None
    return float(r)


def _ratio_for_A_values(*, z: np.ndarray, w: np.ndarray, I0: float, A: np.ndarray) -> float:
    """Return I(A)/I0 where I(A)=∫ w/A dz (early part only)."""
    if not (np.isfinite(A).all() and float(np.min(A)) > 0.0):
        return float("nan")
    I = _np_trapezoid(w / A, z)
    return float(I / float(I0))


def solve_powerlaw_B_for_ratio(
    *,
    r_target: float,
    bridge_z: float,
    z: np.ndarray,
    w: np.ndarray,
    I0: float,
    n_power: float,
    B_max: float = 1.0e9,
    iters: int = 80,
) -> Optional[float]:
    """Solve for B>=0 in A(z)=1+B*((1+z)/(1+bridge_z))^n such that I(A)/I0=r_target."""
    if not (0.0 < r_target < 1.0 and math.isfinite(r_target)):
        return None
    if not (n_power >= 0.0 and math.isfinite(n_power)):
        return None

    one_p = 1.0 + z
    scale = (one_p / (1.0 + float(bridge_z))) ** float(n_power)

    def ratio_for_B(B: float) -> float:
        A = 1.0 + float(B) * scale
        return _ratio_for_A_values(z=z, w=w, I0=I0, A=A)

    r0 = ratio_for_B(0.0)
    if not math.isfinite(r0):
        return None
    if r_target >= r0 - 1e-15:
        return 0.0

    B_lo = 0.0
    B_hi = 1.0
    r_hi = ratio_for_B(B_hi)
    while math.isfinite(r_hi) and r_hi > r_target and B_hi < float(B_max):
        B_hi *= 2.0
        r_hi = ratio_for_B(B_hi)
    if not (math.isfinite(r_hi) and r_hi <= r_target):
        return None

    for _ in range(int(iters)):
        B_mid = 0.5 * (B_lo + B_hi)
        r_mid = ratio_for_B(B_mid)
        if not math.isfinite(r_mid):
            return None
        if r_mid > r_target:
            B_lo = B_mid
        else:
            B_hi = B_mid
    return float(B_hi)


def solve_logistic_Amax_for_ratio(
    *,
    r_target: float,
    z: np.ndarray,
    w: np.ndarray,
    I0: float,
    zc: float,
    s: float,
    Amax_max: float = 1.0e9,
    iters: int = 80,
) -> Optional[float]:
    """Solve for Amax>=1 in A(z)=1+(Amax-1)/(1+exp((z-zc)/s)) such that I(A)/I0=r_target."""
    if not (0.0 < r_target < 1.0 and math.isfinite(r_target)):
        return None
    if not (s > 0.0 and math.isfinite(s)):
        return None
    if not math.isfinite(float(zc)):
        return None

    x = (z - float(zc)) / float(s)
    # A(z) = 1 + (Amax-1) * wlog(z), where wlog in (0,1).
    wlog = 1.0 / (1.0 + np.exp(x))

    def ratio_for_Amax(Amax: float) -> float:
        A = 1.0 + (float(Amax) - 1.0) * wlog
        return _ratio_for_A_values(z=z, w=w, I0=I0, A=A)

    r1 = ratio_for_Amax(1.0)
    if not math.isfinite(r1):
        return None
    if r_target >= r1 - 1e-15:
        return 1.0

    # Bracket.
    A_lo = 1.0
    A_hi = 2.0
    r_hi = ratio_for_Amax(A_hi)
    while math.isfinite(r_hi) and r_hi > r_target and A_hi < float(Amax_max):
        A_hi *= 2.0
        r_hi = ratio_for_Amax(A_hi)
    if not (math.isfinite(r_hi) and r_hi <= r_target):
        return None

    for _ in range(int(iters)):
        A_mid = 0.5 * (A_lo + A_hi)
        r_mid = ratio_for_Amax(A_mid)
        if not math.isfinite(r_mid):
            return None
        if r_mid > r_target:
            A_lo = A_mid
        else:
            A_hi = A_mid
    return float(A_hi)


def solve_bump_A_for_ratio(
    *,
    r_target: float,
    z: np.ndarray,
    w: np.ndarray,
    I0: float,
    z1: float,
    z2: float,
) -> Optional[float]:
    """Solve analytic A>=1 for a piecewise-constant bump on [z1,z2].

    Family:
      A(z) = A_bump  for z in [z1, z2]
             1       otherwise

    In the A->inf limit, the minimum achievable ratio is 1 - I_bump/I0 (turning
    off the bump interval contribution). If r_target is below that, the family
    cannot match the required closure.
    """
    if not (0.0 < r_target < 1.0 and math.isfinite(r_target)):
        return None
    if not (math.isfinite(float(z1)) and math.isfinite(float(z2)) and float(z2) > float(z1)):
        return None
    if not (I0 > 0.0 and math.isfinite(I0)):
        return None

    z1c = float(z1)
    z2c = float(z2)
    m = (z >= z1c) & (z <= z2c)
    if not bool(np.any(m)):
        return None
    z_b = z[m]
    w_b = w[m]
    if z_b.size < 2:
        return None

    I_bump = _np_trapezoid(w_b, z_b)
    if not (I_bump > 0.0 and math.isfinite(I_bump)):
        return None
    I_rest = float(I0) - float(I_bump)
    if not (I_rest >= 0.0 and math.isfinite(I_rest)):
        return None

    denom = float(r_target) * float(I0) - float(I_rest)
    if not (denom > 0.0 and math.isfinite(denom)):
        return None
    A = float(I_bump) / float(denom)
    if not (A >= 1.0 and math.isfinite(A)):
        return None
    return float(A)


@dataclass(frozen=True)
class CorrelationRow:
    model: str
    p: float
    z_transition: float
    bridge_z_used: float
    is_degenerate: bool
    dm_fit: float
    rs_fit: float
    chi2_min: float
    chi2_base: float
    A_required: Optional[float]
    deltaH_over_H: Optional[float]
    # Extended closure deformation families (diagnostic-only).
    B_required_powerlaw: Optional[float]
    Amax_required_powerlaw: Optional[float]
    Amax_required_logistic: Optional[float]
    Amax_required_bump: Optional[float]
    implausible_powerlaw: bool
    implausible_logistic: bool
    implausible_bump: bool
    D_M_0_to_bridge_Mpc: float
    D_M_bridge_to_zstar_Mpc: float
    D_M_total_Mpc: float
    delta_v_cm_s_10y_z2: float
    delta_v_cm_s_10y_z3: float
    delta_v_cm_s_10y_z4: float
    delta_v_cm_s_10y_z5: float

    def as_csv_dict(self) -> Dict[str, str]:
        def fmt(x: Optional[float], *, p: int = 16) -> str:
            if x is None:
                return ""
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.{p}g}"

        return {
            "model": str(self.model),
            "p": fmt(self.p, p=12),
            "z_transition": fmt(self.z_transition, p=12),
            "bridge_z_used": fmt(self.bridge_z_used, p=12),
            "is_degenerate": str(bool(self.is_degenerate)),
            "dm_fit": fmt(self.dm_fit),
            "rs_fit": fmt(self.rs_fit),
            "chi2_min": fmt(self.chi2_min),
            "chi2_base": fmt(self.chi2_base),
            "A_required": fmt(self.A_required),
            "deltaH_over_H": fmt(self.deltaH_over_H),
            "B_required_powerlaw": fmt(self.B_required_powerlaw),
            "Amax_required_powerlaw": fmt(self.Amax_required_powerlaw),
            "Amax_required_logistic": fmt(self.Amax_required_logistic),
            "Amax_required_bump": fmt(self.Amax_required_bump),
            "implausible_powerlaw": str(bool(self.implausible_powerlaw)),
            "implausible_logistic": str(bool(self.implausible_logistic)),
            "implausible_bump": str(bool(self.implausible_bump)),
            "D_M_0_to_bridge_Mpc": fmt(self.D_M_0_to_bridge_Mpc, p=12),
            "D_M_bridge_to_zstar_Mpc": fmt(self.D_M_bridge_to_zstar_Mpc, p=12),
            "D_M_total_Mpc": fmt(self.D_M_total_Mpc, p=12),
            "delta_v_cm_s_10y_z2": fmt(self.delta_v_cm_s_10y_z2),
            "delta_v_cm_s_10y_z3": fmt(self.delta_v_cm_s_10y_z3),
            "delta_v_cm_s_10y_z4": fmt(self.delta_v_cm_s_10y_z4),
            "delta_v_cm_s_10y_z5": fmt(self.delta_v_cm_s_10y_z5),
        }


def _plot_scatter(
    *,
    rows: Sequence[CorrelationRow],
    out_path: Path,
    x_key: str,
    y_key: str,
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    xs: List[float] = []
    ys: List[float] = []
    colors: List[str] = []
    for r in rows:
        x = float(getattr(r, x_key))
        y = getattr(r, y_key)
        if y is None:
            continue
        yv = float(y)
        if not (math.isfinite(x) and math.isfinite(yv)):
            continue
        xs.append(x)
        ys.append(yv)
        # Color by bridge_z (coarse).
        bz = float(r.bridge_z_used)
        colors.append("#1f77b4" if abs(bz - 5.0) < 1e-6 else "#ff7f0e")

    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    ax.scatter(xs, ys, s=30, c=colors, alpha=0.85, edgecolors="none")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _plot_scatter_logy(
    *,
    rows: Sequence[CorrelationRow],
    out_path: Path,
    x_fn,
    y_fn,
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    xs: List[float] = []
    ys: List[float] = []
    colors: List[str] = []
    for r in rows:
        x = float(x_fn(r))
        y = y_fn(r)
        if y is None:
            continue
        yv = float(y)
        if not (math.isfinite(x) and math.isfinite(yv) and yv > 0.0):
            continue
        xs.append(x)
        ys.append(yv)
        bz = float(r.bridge_z_used)
        colors.append("#1f77b4" if abs(bz - 5.0) < 1e-6 else "#ff7f0e")

    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    ax.scatter(xs, ys, s=30, c=colors, alpha=0.85, edgecolors="none")
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", alpha=0.25)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def run(
    *,
    scan_csv: Path,
    scan_manifest: Optional[Path],
    out_dir: Path,
    years: float,
    zs: Sequence[float],
    top_n: int,
    powerlaw_n: float,
    logistic_zc: float,
    logistic_s: float,
    bump_z1: float = 5.0,
    bump_z2: float = 20.0,
    implausible_Amax_threshold: float = 10.0,
) -> Dict[str, Any]:
    rows_in = _load_csv_rows(scan_csv)

    fixed: Dict[str, Any] = {
        "H0_km_s_Mpc": 67.4,
        "Omega_m": 0.315,
        "Omega_L": 0.685,
        "omega_b_h2": 0.02237,
        "omega_c_h2": 0.1200,
        "Neff": 3.046,
        "Tcmb_K": 2.7255,
    }
    grid_spec: Dict[str, Any] = {}
    if scan_manifest is not None and scan_manifest.is_file():
        m = json.loads(scan_manifest.read_text(encoding="utf-8"))
        fixed_params = dict(m.get("fixed_params") or {})
        # Normalize key spelling from older manifests if needed.
        fixed["H0_km_s_Mpc"] = float(fixed_params.get("H0_km_s_Mpc", fixed["H0_km_s_Mpc"]))
        fixed["Omega_m"] = float(fixed_params.get("Omega_m", fixed["Omega_m"]))
        fixed["Omega_L"] = float(fixed_params.get("Omega_L", fixed["Omega_L"]))
        fixed["omega_b_h2"] = float(fixed_params.get("omega_b_h2", fixed["omega_b_h2"]))
        fixed["omega_c_h2"] = float(fixed_params.get("omega_c_h2", fixed["omega_c_h2"]))
        fixed["Neff"] = float(fixed_params.get("Neff", fixed["Neff"]))
        fixed["Tcmb_K"] = float(fixed_params.get("Tcmb_K", fixed["Tcmb_K"]))
        grid_spec = dict(m.get("grid") or {})

    # Pre-compute early-time bridge constants for each bridge_z in the scan.
    bridge_zs = sorted({float(_parse_float(r.get("bridge_z_used", "nan"))) for r in rows_in})
    bridge_consts: Dict[float, Dict[str, float]] = {}
    for bz in bridge_zs:
        if not math.isfinite(float(bz)) or bz <= 0:
            continue
        bridge_consts[float(bz)] = _bridge_constants_for_z(
            bridge_z=float(bz),
            H0_km_s_Mpc=float(fixed["H0_km_s_Mpc"]),
            Omega_m=float(fixed["Omega_m"]),
            Omega_L=float(fixed["Omega_L"]),
            omega_b_h2=float(fixed["omega_b_h2"]),
            omega_c_h2=float(fixed["omega_c_h2"]),
            Neff=float(fixed["Neff"]),
            Tcmb_K=float(fixed["Tcmb_K"]),
        )

    # Precompute early-time integral grids on [bridge_z, z*] for each bridge_z.
    early_cache: Dict[float, Dict[str, Any]] = {}
    for bz, bc in bridge_consts.items():
        z0 = float(bc["bridge_z_used"])
        z1 = float(bc["z_star"])
        z_grid, w_grid, I0 = _early_integral_grid(
            z0=float(z0),
            z1=float(z1),
            Omega_m=float(bc["Omega_m_early"]),
            Omega_r=float(bc["Omega_r"]),
            n=8192,
        )
        early_cache[float(bz)] = {"z": z_grid, "w": w_grid, "I0": float(I0), "z_star": float(z1)}

    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    years = float(years)
    zs_use = [float(z) for z in zs]
    bump_z1 = float(bump_z1)
    bump_z2 = float(bump_z2)

    rows_out: List[CorrelationRow] = []
    for row in rows_in:
        model_name = str(row.get("model", "gsc_transition")).strip()
        p = float(_parse_float(row.get("p", "nan")))
        z_t = float(_parse_float(row.get("z_transition", "nan")))
        bz = float(_parse_float(row.get("bridge_z_used", "nan")))
        if "is_degenerate" in row:
            is_deg = bool(_parse_bool(row.get("is_degenerate", "false")))
        else:
            is_deg = bool(bz <= z_t)

        dm_fit = float(_parse_float(row.get("dm_fit", "nan")))
        rs_fit = float(_parse_float(row.get("rs_fit", "nan")))
        chi2_min = float(_parse_float(row.get("chi2_min", "nan")))
        chi2_base = float(_parse_float(row.get("chi2_base", "nan")))

        hist = _build_history(
            model=model_name,
            H0_km_s_Mpc=float(fixed["H0_km_s_Mpc"]),
            Omega_m=float(fixed["Omega_m"]),
            Omega_L=float(fixed["Omega_L"]),
            gsc_p=float(p),
            gsc_ztrans=float(z_t),
        )

        # Drift amplitudes (Delta v over N years), in cm/s.
        H0_si = float(hist.H(0.0))
        dv = {float(zv): float(delta_v_cm_s(z=float(zv), years=float(years), H0=float(H0_si), H_of_z=hist.H)) for zv in zs_use}

        # Distances to compute A_required at z_boost_start=bridge_z_used.
        bc = bridge_consts.get(float(bz))
        if bc is None:
            raise RuntimeError(f"Missing bridge constants for bridge_z_used={bz}")
        D_bridge_star = float(bc["D_M_bridge_to_zstar_Mpc"])
        D0_bridge = float(_comoving_distance_model_to_z_Mpc(z=float(bz), model=hist, n=4096))
        D_total = float(D0_bridge) + float(D_bridge_star)
        r_target = _required_high_distance_ratio(dm_fit=float(dm_fit), D_low=float(D0_bridge), D_high=float(D_bridge_star))
        A = _effective_A_required(dm_fit=float(dm_fit), D_M_0_to_bridge_Mpc=float(D0_bridge), D_M_bridge_to_zstar_Mpc=float(D_bridge_star))
        dH = float(A - 1.0) if (A is not None and math.isfinite(float(A))) else None

        # Extended deformation families (E2.5+): find minimal-amplitude knobs
        # within two toy families that achieve the same distance closure r_target.
        cache = early_cache.get(float(bz))
        if cache is None:
            raise RuntimeError(f"Missing early cache for bridge_z_used={bz}")
        z_grid = cache["z"]
        w_grid = cache["w"]
        I0 = float(cache["I0"])
        z_star = float(cache["z_star"])

        B_pw: Optional[float] = None
        Amax_pw: Optional[float] = None
        Amax_log: Optional[float] = None
        Amax_bump: Optional[float] = None

        if r_target is not None and 0.0 < float(r_target) < 1.0:
            B_pw = solve_powerlaw_B_for_ratio(
                r_target=float(r_target),
                bridge_z=float(bz),
                z=z_grid,
                w=w_grid,
                I0=float(I0),
                n_power=float(powerlaw_n),
            )
            if B_pw is not None and math.isfinite(float(B_pw)):
                Amax_pw = 1.0 + float(B_pw) * ((1.0 + float(z_star)) / (1.0 + float(bz))) ** float(powerlaw_n)

            Amax_log = solve_logistic_Amax_for_ratio(
                r_target=float(r_target),
                z=z_grid,
                w=w_grid,
                I0=float(I0),
                zc=float(logistic_zc),
                s=float(logistic_s),
            )

            # Localized bump on [z1,z2], clamped to [bridge_z_used, z_star].
            z1c = max(float(bz), float(bump_z1))
            z2c = min(float(z_star), float(bump_z2))
            if z2c > z1c:
                Amax_bump = solve_bump_A_for_ratio(
                    r_target=float(r_target),
                    z=z_grid,
                    w=w_grid,
                    I0=float(I0),
                    z1=float(z1c),
                    z2=float(z2c),
                )

        implausible_pw = (Amax_pw is None) or (not math.isfinite(float(Amax_pw))) or (float(Amax_pw) > float(implausible_Amax_threshold))
        implausible_log = (Amax_log is None) or (not math.isfinite(float(Amax_log))) or (float(Amax_log) > float(implausible_Amax_threshold))
        implausible_bump = (Amax_bump is None) or (not math.isfinite(float(Amax_bump))) or (float(Amax_bump) > float(implausible_Amax_threshold))

        rows_out.append(
            CorrelationRow(
                model=str(model_name),
                p=float(p),
                z_transition=float(z_t),
                bridge_z_used=float(bz),
                is_degenerate=bool(is_deg),
                dm_fit=float(dm_fit),
                rs_fit=float(rs_fit),
                chi2_min=float(chi2_min),
                chi2_base=float(chi2_base),
                A_required=float(A) if A is not None else None,
                deltaH_over_H=float(dH) if dH is not None else None,
                B_required_powerlaw=float(B_pw) if B_pw is not None else None,
                Amax_required_powerlaw=float(Amax_pw) if Amax_pw is not None else None,
                Amax_required_logistic=float(Amax_log) if Amax_log is not None else None,
                Amax_required_bump=float(Amax_bump) if Amax_bump is not None else None,
                implausible_powerlaw=bool(implausible_pw),
                implausible_logistic=bool(implausible_log),
                implausible_bump=bool(implausible_bump),
                D_M_0_to_bridge_Mpc=float(D0_bridge),
                D_M_bridge_to_zstar_Mpc=float(D_bridge_star),
                D_M_total_Mpc=float(D_total),
                delta_v_cm_s_10y_z2=float(dv.get(2.0, float("nan"))),
                delta_v_cm_s_10y_z3=float(dv.get(3.0, float("nan"))),
                delta_v_cm_s_10y_z4=float(dv.get(4.0, float("nan"))),
                delta_v_cm_s_10y_z5=float(dv.get(5.0, float("nan"))),
            )
        )

    # Write full CSV.
    out_csv = tables_dir / "e2_drift_cmb_correlation.csv"
    fieldnames = list(rows_out[0].as_csv_dict().keys())
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows_out:
            w.writerow(r.as_csv_dict())

    # Top-N subset (non-degenerate, with defined A).
    nondeg = [r for r in rows_out if (not r.is_degenerate) and (r.A_required is not None)]
    nondeg_sorted = sorted(nondeg, key=lambda r: float(r.A_required) if r.A_required is not None else float("inf"))
    top = nondeg_sorted[: max(0, int(top_n))]
    top_csv = tables_dir / "e2_drift_cmb_correlation_topN.csv"
    with top_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in top:
            w.writerow(r.as_csv_dict())

    # Compact summary table (referee-readable).
    summary_csv = tables_dir / "drift_cmb_closure_summary.csv"
    summary_fields = [
        "model",
        "p",
        "z_transition",
        "bridge_z_used",
        "delta_v_cm_s_10y_z4",
        "dm_fit",
        "A_required_const",
        "Amax_required_logistic",
        "Amax_required_bump",
        "B_required_powerlaw",
        "Amax_required_powerlaw",
        "implausible_logistic",
        "implausible_bump",
        "implausible_powerlaw",
    ]
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=summary_fields)
        w.writeheader()
        for r in [rr for rr in rows_out if not rr.is_degenerate]:
            w.writerow(
                {
                    "model": r.model,
                    "p": f"{float(r.p):.12g}",
                    "z_transition": f"{float(r.z_transition):.12g}",
                    "bridge_z_used": f"{float(r.bridge_z_used):.12g}",
                    "delta_v_cm_s_10y_z4": f"{float(r.delta_v_cm_s_10y_z4):.16g}",
                    "dm_fit": f"{float(r.dm_fit):.16g}",
                    "A_required_const": f"{float(r.A_required):.16g}" if r.A_required is not None else "",
                    "Amax_required_logistic": f"{float(r.Amax_required_logistic):.16g}" if r.Amax_required_logistic is not None else "",
                    "Amax_required_bump": f"{float(r.Amax_required_bump):.16g}" if r.Amax_required_bump is not None else "",
                    "B_required_powerlaw": f"{float(r.B_required_powerlaw):.16g}" if r.B_required_powerlaw is not None else "",
                    "Amax_required_powerlaw": f"{float(r.Amax_required_powerlaw):.16g}" if r.Amax_required_powerlaw is not None else "",
                    "implausible_logistic": str(bool(r.implausible_logistic)),
                    "implausible_bump": str(bool(r.implausible_bump)),
                    "implausible_powerlaw": str(bool(r.implausible_powerlaw)),
                }
            )

    # Shape-focused summary table (constant vs logistic vs bump).
    shapes_csv = tables_dir / "cmb_drift_cmb_correlation_shapes.csv"
    shapes_fields = [
        "model",
        "p",
        "z_transition",
        "bridge_z_used",
        "is_degenerate",
        "delta_v_cm_s_10y_z4",
        "dm_fit",
        "A_required_const",
        "Amax_required_logistic",
        "Amax_required_bump",
        "implausible_logistic",
        "implausible_bump",
    ]
    with shapes_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=shapes_fields)
        w.writeheader()
        for r in rows_out:
            w.writerow(
                {
                    "model": r.model,
                    "p": f"{float(r.p):.12g}",
                    "z_transition": f"{float(r.z_transition):.12g}",
                    "bridge_z_used": f"{float(r.bridge_z_used):.12g}",
                    "is_degenerate": str(bool(r.is_degenerate)),
                    "delta_v_cm_s_10y_z4": f"{float(r.delta_v_cm_s_10y_z4):.16g}",
                    "dm_fit": f"{float(r.dm_fit):.16g}",
                    "A_required_const": f"{float(r.A_required):.16g}" if r.A_required is not None else "",
                    "Amax_required_logistic": f"{float(r.Amax_required_logistic):.16g}" if r.Amax_required_logistic is not None else "",
                    "Amax_required_bump": f"{float(r.Amax_required_bump):.16g}" if r.Amax_required_bump is not None else "",
                    "implausible_logistic": str(bool(r.implausible_logistic)),
                    "implausible_bump": str(bool(r.implausible_bump)),
                }
            )

    # Figures: focus on z=4 as a representative ANDES bin.
    fig_A = figs_dir / "A_required_vs_drift_z4.png"
    _plot_scatter(
        rows=[r for r in rows_out if not r.is_degenerate],
        out_path=fig_A,
        x_key="delta_v_cm_s_10y_z4",
        y_key="A_required",
        title="E2.5 diagnostic: effective H-boost A required vs drift amplitude at z=4",
        xlabel=f"Delta v(z=4)  [cm/s over {years:g} yr]",
        ylabel="A required (effective H boost above bridge_z)",
    )

    fig_dm = figs_dir / "dm_fit_vs_drift_z4.png"
    _plot_scatter(
        rows=[r for r in rows_out if not r.is_degenerate],
        out_path=fig_dm,
        x_key="delta_v_cm_s_10y_z4",
        y_key="dm_fit",
        title="E2.5 diagnostic: dm_fit required vs drift amplitude at z=4",
        xlabel=f"Delta v(z=4)  [cm/s over {years:g} yr]",
        ylabel="dm_fit (diagnostic D_M(z*) multiplier)",
    )

    fig_Amax_bridge = figs_dir / "Amax_required_logistic_vs_bridge_z.png"
    _plot_scatter_logy(
        rows=[r for r in rows_out if not r.is_degenerate],
        out_path=fig_Amax_bridge,
        x_fn=lambda r: float(r.bridge_z_used) + 0.03 * (float(r.p) - 0.7),  # deterministic jitter for readability
        y_fn=lambda r: r.Amax_required_logistic,
        title="E2.5 diagnostic: logistic Amax required vs bridge_z (log scale)",
        xlabel="bridge_z_used (jittered by p)",
        ylabel="Amax_required_logistic  (log)",
    )

    fig_Amax_drift = figs_dir / "Amax_required_logistic_vs_drift_z4.png"
    _plot_scatter_logy(
        rows=[r for r in rows_out if not r.is_degenerate],
        out_path=fig_Amax_drift,
        x_fn=lambda r: float(r.delta_v_cm_s_10y_z4),
        y_fn=lambda r: r.Amax_required_logistic,
        title="E2.5 diagnostic: logistic Amax required vs drift amplitude at z=4 (log scale)",
        xlabel=f"Delta v(z=4)  [cm/s over {years:g} yr]",
        ylabel="Amax_required_logistic  (log)",
    )

    # Figure: quantify how much "shape freedom" reduces required amplitudes.
    def _plot_A_required_by_shape(*, rows: Sequence[CorrelationRow], out_path: Path) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: E402

        def collect(bz_target: float):
            const = []
            logistic = []
            bump = []
            for r in rows:
                if r.is_degenerate:
                    continue
                if abs(float(r.bridge_z_used) - float(bz_target)) > 1e-6:
                    continue
                if r.A_required is not None and math.isfinite(float(r.A_required)) and float(r.A_required) > 0.0:
                    const.append(float(r.A_required))
                if (
                    r.Amax_required_logistic is not None
                    and math.isfinite(float(r.Amax_required_logistic))
                    and float(r.Amax_required_logistic) > 0.0
                ):
                    logistic.append(float(r.Amax_required_logistic))
                if r.Amax_required_bump is not None and math.isfinite(float(r.Amax_required_bump)) and float(r.Amax_required_bump) > 0.0:
                    bump.append(float(r.Amax_required_bump))
            return {"constant": const, "logistic": logistic, "bump": bump}

        # Most of the grids use bridge_z in {5,10}; plot both panels for readability.
        data5 = collect(5.0)
        data10 = collect(10.0)

        fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.5), constrained_layout=True)
        for ax, bz, data in [(axs[0], 5.0, data5), (axs[1], 10.0, data10)]:
            labels = ["const A", "logistic Amax", "bump A"]
            series = [data["constant"], data["logistic"], data["bump"]]
            ax.axhline(1.0, color="#444444", linestyle=":", linewidth=1.5)
            if all(len(s) == 0 for s in series):
                ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
            else:
                ax.boxplot(series, showfliers=False)
                ax.set_xticks(list(range(1, len(labels) + 1)))
                ax.set_xticklabels(labels)
                ax.set_yscale("log")
            ax.set_title(f"bridge_z_used ≈ {bz:g}")
            ax.set_ylabel("Required amplitude (A or Amax)")
            ax.grid(True, which="both", alpha=0.2)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=160)
        plt.close(fig)

    fig_A_shapes = figs_dir / "A_required_by_shape.png"
    _plot_A_required_by_shape(rows=rows_out, out_path=fig_A_shapes)

    # Summary stats (finite values only).
    A_vals = [float(r.A_required) for r in nondeg if (r.A_required is not None and math.isfinite(float(r.A_required)))]
    Amax_log_vals = [
        float(r.Amax_required_logistic)
        for r in nondeg
        if (r.Amax_required_logistic is not None and math.isfinite(float(r.Amax_required_logistic)) and float(r.Amax_required_logistic) > 0.0)
    ]
    Amax_bump_vals = [
        float(r.Amax_required_bump)
        for r in nondeg
        if (r.Amax_required_bump is not None and math.isfinite(float(r.Amax_required_bump)) and float(r.Amax_required_bump) > 0.0)
    ]
    dv4_vals = [float(r.delta_v_cm_s_10y_z4) for r in nondeg if math.isfinite(float(r.delta_v_cm_s_10y_z4))]
    summary = {
        "num_points_total": int(len(rows_out)),
        "num_points_non_degenerate": int(len([r for r in rows_out if not r.is_degenerate])),
        "num_points_non_degenerate_with_A": int(len(nondeg)),
        "A_required_min": float(min(A_vals)) if A_vals else None,
        "A_required_max": float(max(A_vals)) if A_vals else None,
        "Amax_required_logistic_min": float(min(Amax_log_vals)) if Amax_log_vals else None,
        "Amax_required_logistic_max": float(max(Amax_log_vals)) if Amax_log_vals else None,
        "Amax_required_bump_min": float(min(Amax_bump_vals)) if Amax_bump_vals else None,
        "Amax_required_bump_max": float(max(Amax_bump_vals)) if Amax_bump_vals else None,
        "drift_z4_cm_s_10y_min": float(min(dv4_vals)) if dv4_vals else None,
        "drift_z4_cm_s_10y_max": float(max(dv4_vals)) if dv4_vals else None,
    }

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_drift_cmb_correlation",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "scan_csv": _relpath(scan_csv),
            "scan_manifest": _relpath(scan_manifest) if scan_manifest is not None else None,
        },
        "fixed_params": dict(fixed),
        "grid_spec": grid_spec,
        "drift_eval": {
            "years": float(years),
            "zs": [float(z) for z in zs_use],
            "quantity": "Delta v (cm/s) over years",
        },
        "closure_deformation_families": {
            "constant_A": {"z_start": "bridge_z_used"},
            "powerlaw_boost": {
                "A_of_z": "A(z)=1 + B*((1+z)/(1+bridge_z))^n",
                "n": float(powerlaw_n),
            },
            "logistic_crossover": {
                "A_of_z": "A(z)=1 + (Amax-1)/(1+exp((z-zc)/s))",
                "zc": float(logistic_zc),
                "s": float(logistic_s),
            },
            "bump_interval": {
                "A_of_z": "A(z)=A_bump on [z1,z2], 1 otherwise",
                "z1": float(bump_z1),
                "z2": float(bump_z2),
                "clamp": "[bridge_z_used, z_star]",
            },
            "implausible_Amax_threshold": float(implausible_Amax_threshold),
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "csv": _relpath(out_csv),
            "csv_topN": _relpath(top_csv),
            "csv_summary": _relpath(summary_csv),
            "csv_shapes": _relpath(shapes_csv),
            "fig_A_required_vs_drift_z4": _relpath(fig_A),
            "fig_dm_fit_vs_drift_z4": _relpath(fig_dm),
            "fig_Amax_required_logistic_vs_bridge_z": _relpath(fig_Amax_bridge),
            "fig_Amax_required_logistic_vs_drift_z4": _relpath(fig_Amax_drift),
            "fig_A_required_by_shape": _relpath(fig_A_shapes),
        },
        "summary": summary,
        "notes": [
            "Diagnostic-only: correlates late-time drift amplitudes with required CMB distance closure (dm_fit) and its effective A mapping.",
            "This is a planning/roadmap tool and is out of scope for submission-grade claims.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--scan-csv",
        type=Path,
        default=V101_DIR / "results/late_time_fit_cmb_e2_closure_diagnostic/scan/tables/cmb_e2_dm_rs_fit_scan.csv",
        help="Path to an E2.4 scan CSV (dm_fit/rs_fit grid output).",
    )
    ap.add_argument(
        "--scan-manifest",
        type=Path,
        default=V101_DIR / "results/late_time_fit_cmb_e2_closure_diagnostic/scan/manifest.json",
        help="Optional: path to the E2.4 scan manifest.json (used for fixed params + grid spec).",
    )
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_drift_cmb_correlation"))
    ap.add_argument("--years", type=float, default=10.0)
    ap.add_argument("--zs", type=str, default="2,3,4,5", help="CSV list of redshifts where drift is evaluated.")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--powerlaw-n", type=float, default=2.0, help="n exponent in power-law boost family A(z)=1+B*((1+z)/(1+bridge))^n.")
    ap.add_argument(
        "--logistic-zc",
        type=float,
        default=20.0,
        help="zc in logistic crossover family A(z)=1+(Amax-1)/(1+exp((z-zc)/s)).",
    )
    ap.add_argument("--logistic-s", type=float, default=2.0, help="s in logistic crossover family.")
    ap.add_argument(
        "--bump-z1",
        type=float,
        default=5.0,
        help="z1 lower bound for the localized bump family A(z)=A_bump on [z1,z2] (clamped to [bridge_z_used,z*]).",
    )
    ap.add_argument(
        "--bump-z2",
        type=float,
        default=20.0,
        help="z2 upper bound for the localized bump family A(z)=A_bump on [z1,z2] (clamped to [bridge_z_used,z*]).",
    )
    ap.add_argument("--implausible-Amax-threshold", type=float, default=10.0, help="Mark fits implausible if Amax > threshold.")
    args = ap.parse_args(argv)

    zs = [float(tok) for tok in str(args.zs).split(",") if str(tok).strip()]
    scan_manifest = args.scan_manifest if args.scan_manifest and args.scan_manifest.is_file() else None
    run(
        scan_csv=args.scan_csv,
        scan_manifest=scan_manifest,
        out_dir=args.outdir,
        years=float(args.years),
        zs=zs,
        top_n=int(args.top_n),
        powerlaw_n=float(args.powerlaw_n),
        logistic_zc=float(args.logistic_zc),
        logistic_s=float(args.logistic_s),
        bump_z1=float(args.bump_z1),
        bump_z2=float(args.bump_z2),
        implausible_Amax_threshold=float(args.implausible_Amax_threshold),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
