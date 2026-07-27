#!/usr/bin/env python3
"""analysis_w0wa_rd_shift_diagnostic.py — DIAGNOSTIC (not a registered prediction).

Question (frontier doc §5 M-task)
---------------------------------
If the universe follows GSC's canonical T2 ansatz — so the *apparent* BAO
standard ruler in today's atomic units is larger than the LCDM expectation by
delta = +0.417% (P1, single source of truth read from the P1 register
artifact) — and an analyst fits w0waCDM to the BAO data using the STANDARD
(unshifted) r_d calibration plus Planck-like CMB anchors, where does the
best-fit (w0, wa) land?  Toward the DESI DR2 preference (w0 > -1, wa < 0), or
away from it?  Adi (JCAP 03 (2026) 015, arXiv:2509.12331) showed r_d
calibration shifts and the w0-wa evidence are degenerate; this script asks
what GSC's *specific, registered* shift does in that degeneracy, at DESI DR1
per-tracer precision.

Setup (all deliberately minimal and self-contained)
---------------------------------------------------
* Mock "GSC truth": flat LCDM background at the P1 fiducial cosmology
  (h = 0.6736, omega_m_h2 = 0.1430, Tcmb = 2.7255 K, Neff = 3.046) — T1 is
  conformally LCDM-equivalent and the T2 background deviation at p = 6e-4 is
  second-order for this purpose.  The GSC effect enters ONLY as the apparent
  ruler: measured y = D/r_d values are LOWER than the standard-calibration
  expectation by the factor 1/(1+delta).  The CMB acoustic angle is a
  dimensionless observable and is invariant under the coherent relabeling, so
  the mock CMB anchors equal the fiducial predictions exactly (same convention
  as the registered P1 pipeline: the shift lives in the late-time BAO
  comparison).
* Data model: DESI DR1 per-tracer central values REPLACED by the noiseless
  mock, with the REAL DESI DR1 uncertainties and DM-DH correlations retained
  (data/bao/desi/desi_dr1_bao_baseline.csv).
* CMB anchors (Planck-like, Gaussian):
    omega_m_h2 = 0.1430 +/- 0.0011
    D_M(z*=1089.92)/r_d_std anchored at the fiducial value with fractional
    sigma 3.1e-4 (the ~0.03% theta* precision).
* Fit models: flat LCDM and flat w0waCDM (CPL), radiation included; r_d fixed
  to the standard calibration (the analyst does not know about the shift).
* Controls: (C0) unshifted mock must recover the fiducial with chi2 ~ 0;
  (D) LCDM with a free ruler-scale must absorb the shift exactly.

What this is NOT
----------------
Not a DESI likelihood reproduction (no SNe, no full covariances, no
recombination modeling — both sides use the same quadrature and the same r_d
constant, so only the differential matters).  Direction and order of
magnitude are the deliverables.  Output is deterministic: no timestamps.

Usage:
    python3 scripts/analysis_w0wa_rd_shift_diagnostic.py [--fast] [--output PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TOOL = "analysis_w0wa_rd_shift_diagnostic.py"
TOOL_VERSION = "0.1"

# --- fiducial cosmology (matches the P1 register artifact's cosmology_inputs) ---
H_FID = 0.6736
OMEGA_M_H2_FID = 0.1430
TCMB_K = 2.7255
NEFF = 3.046
Z_STAR = 1089.92
R_D_STD_MPC = 147.09          # registered DESI-era standard calibration (P1 observed_data)
C_KM_S = 299792.458

SIGMA_OMEGA_M_H2 = 0.0011     # Planck-like
SIGMA_FRAC_THETA = 3.1e-4     # ~0.03% on D_M(z*)/r_d

# DESI DR1 per-tracer blocks (z, values replaced by mock; sigmas/correlations real).
# Source: data/bao/desi/desi_dr1_bao_baseline.csv (DESI DR1 compact set).
DESI_DR1_BLOCKS = [
    {"kind": "DV", "label": "BGS",  "z": 0.295, "sigma_dv": 0.123},
    {"kind": "DMDH", "label": "LRG", "z": 0.51, "sigma_dm": 0.25, "sigma_dh": 0.61, "rho": -0.39},
    {"kind": "DMDH", "label": "ELG", "z": 0.93, "sigma_dm": 0.28, "sigma_dh": 0.35, "rho": 0.15},
    {"kind": "DMDH", "label": "QSO", "z": 1.49, "sigma_dm": 0.67, "sigma_dh": 0.55, "rho": 0.20},
    {"kind": "DMDH", "label": "LyA", "z": 2.33, "sigma_dm": 0.95, "sigma_dh": 0.17, "rho": 0.36},
]


def omega_r_h2() -> float:
    """Photon + massless-neutrino radiation density (standard formulas)."""
    omega_gamma_h2 = 2.469e-5 * (TCMB_K / 2.725) ** 4
    return omega_gamma_h2 * (1.0 + 0.2271 * NEFF)


def de_density_factor(z: float, w0: float, wa: float) -> float:
    """CPL dark-energy density: rho_DE(z)/rho_DE(0), closed form."""
    zp1 = 1.0 + z
    return zp1 ** (3.0 * (1.0 + w0 + wa)) * math.exp(-3.0 * wa * z / zp1)


class Background:
    """Flat w0waCDM with radiation.  Parameters: omega_m_h2, h, w0, wa."""

    def __init__(self, omega_m_h2: float, h: float, w0: float = -1.0, wa: float = 0.0):
        self.h = h
        self.omega_m = omega_m_h2 / (h * h)
        self.omega_r = omega_r_h2() / (h * h)
        self.omega_de = 1.0 - self.omega_m - self.omega_r
        self.w0, self.wa = w0, wa
        if self.omega_de <= 0.0:
            raise ValueError("Omega_DE <= 0")

    def E(self, z: float) -> float:
        zp1 = 1.0 + z
        e2 = (self.omega_r * zp1 ** 4 + self.omega_m * zp1 ** 3
              + self.omega_de * de_density_factor(z, self.w0, self.wa))
        if e2 <= 0.0:
            raise ValueError("E^2 <= 0")
        return math.sqrt(e2)

    def D_H_mpc(self, z: float) -> float:
        return C_KM_S / (100.0 * self.h * self.E(z))

    def D_M_mpc(self, z: float, n: int = 400) -> float:
        """Comoving distance via Simpson in u = ln(1+z) (deterministic, fixed n).

        Quadrature error cancels in the differential: mock and model use the
        same integrator at the same n.
        """
        if z <= 0.0:
            return 0.0
        umax = math.log1p(z)
        if n % 2:
            n += 1
        hstep = umax / n
        total = 0.0
        for i in range(n + 1):
            u = i * hstep
            zz = math.expm1(u)
            f = (1.0 + zz) / self.E(zz)   # dz/E = (1+z) du / E
            w = 1.0 if i in (0, n) else (4.0 if i % 2 else 2.0)
            total += w * f
        return (C_KM_S / (100.0 * self.h)) * total * hstep / 3.0

    def D_V_mpc(self, z: float) -> float:
        dm = self.D_M_mpc(z)
        dh = self.D_H_mpc(z)
        return (z * dh * dm * dm) ** (1.0 / 3.0)


def registered_shift() -> float:
    """Read delta_rs_relative for the canonical powerlaw ansatz from the P1 artifact."""
    p1 = json.loads((REPO_ROOT / "predictions_register" / "P1_bao_ruler_shift"
                     / "pipeline_output.json").read_text(encoding="utf-8"))
    for sub in p1["sub_predictions"]:
        if sub.get("ansatz") == "powerlaw":
            return float(sub["delta_rs_relative"])
    raise RuntimeError("powerlaw sub-prediction not found in P1 artifact")


def make_mock(bg: Background, ruler_shift: float) -> dict:
    """Noiseless mock BAO observables under 'GSC truth'.

    Apparent ruler is larger by (1+delta) => measured D/r_d lower by /(1+delta).
    CMB anchors are invariant (dimensionless acoustic angle).
    """
    scale = 1.0 / (1.0 + ruler_shift)
    mock = {"bao": [], "omega_m_h2": OMEGA_M_H2_FID,
            "dmstar_over_rd": bg.D_M_mpc(Z_STAR) / R_D_STD_MPC}
    for blk in DESI_DR1_BLOCKS:
        if blk["kind"] == "DV":
            mock["bao"].append({"y_dv": bg.D_V_mpc(blk["z"]) / R_D_STD_MPC * scale})
        else:
            mock["bao"].append({
                "y_dm": bg.D_M_mpc(blk["z"]) / R_D_STD_MPC * scale,
                "y_dh": bg.D_H_mpc(blk["z"]) / R_D_STD_MPC * scale,
            })
    return mock


def chi2(params: dict, mock: dict, bao_ruler_scale_free: float = 1.0,
         sigma_scale: float = 1.0) -> float:
    """Total chi2: DESI DR1 blocks + omega_m_h2 prior + theta*-like anchor.

    bao_ruler_scale_free multiplies the effective ruler in the BAO blocks ONLY
    (control D): GSC's shift is a late-time BAO-comparison effect, while the
    CMB acoustic angle is dimensionless and stays standard — a recalibration
    parameter that touched the theta* anchor too would conflate the two.
    sigma_scale rescales the BAO uncertainties (precision scenarios).
    """
    bg = Background(params["omega_m_h2"], params["h"],
                    params.get("w0", -1.0), params.get("wa", 0.0))
    rd_bao = R_D_STD_MPC * bao_ruler_scale_free
    total = 0.0
    for blk, m in zip(DESI_DR1_BLOCKS, mock["bao"]):
        if blk["kind"] == "DV":
            r = bg.D_V_mpc(blk["z"]) / rd_bao - m["y_dv"]
            total += (r / (blk["sigma_dv"] * sigma_scale)) ** 2
        else:
            rdm = bg.D_M_mpc(blk["z"]) / rd_bao - m["y_dm"]
            rdh = bg.D_H_mpc(blk["z"]) / rd_bao - m["y_dh"]
            sm = blk["sigma_dm"] * sigma_scale
            sh = blk["sigma_dh"] * sigma_scale
            rho = blk["rho"]
            det = 1.0 - rho * rho
            total += ((rdm / sm) ** 2 - 2.0 * rho * (rdm / sm) * (rdh / sh)
                      + (rdh / sh) ** 2) / det
    total += ((params["omega_m_h2"] - mock["omega_m_h2"]) / SIGMA_OMEGA_M_H2) ** 2
    dmstar = bg.D_M_mpc(Z_STAR) / R_D_STD_MPC
    total += ((dmstar - mock["dmstar_over_rd"])
              / (SIGMA_FRAC_THETA * mock["dmstar_over_rd"])) ** 2
    return total


def nelder_mead(f, x0, steps, iters=400, tol=1e-10):
    """Small deterministic Nelder-Mead (standard coefficients)."""
    n = len(x0)
    simplex = [list(x0)]
    for i in range(n):
        v = list(x0)
        v[i] += steps[i]
        simplex.append(v)
    fv = [f(v) for v in simplex]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: fv[i])
        simplex = [simplex[i] for i in order]
        fv = [fv[i] for i in order]
        if abs(fv[-1] - fv[0]) < tol:
            break
        cen = [sum(simplex[i][j] for i in range(n)) / n for j in range(n)]
        xr = [cen[j] + (cen[j] - simplex[-1][j]) for j in range(n)]
        fr = f(xr)
        if fr < fv[0]:
            xe = [cen[j] + 2.0 * (cen[j] - simplex[-1][j]) for j in range(n)]
            fe = f(xe)
            simplex[-1], fv[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < fv[-2]:
            simplex[-1], fv[-1] = xr, fr
        else:
            xc = [cen[j] + 0.5 * (simplex[-1][j] - cen[j]) for j in range(n)]
            fc = f(xc)
            if fc < fv[-1]:
                simplex[-1], fv[-1] = xc, fc
            else:
                for i in range(1, n + 1):
                    simplex[i] = [simplex[0][j] + 0.5 * (simplex[i][j] - simplex[0][j])
                                  for j in range(n)]
                    fv[i] = f(simplex[i])
    best = min(range(n + 1), key=lambda i: fv[i])
    return simplex[best], fv[best]


def fit_lcdm(mock, ruler_free=False, sigma_scale=1.0):
    if ruler_free:
        def f(x):
            try:
                return chi2({"omega_m_h2": x[0], "h": x[1]}, mock,
                            bao_ruler_scale_free=x[2], sigma_scale=sigma_scale)
            except ValueError:
                return 1e30
        x, c = nelder_mead(f, [OMEGA_M_H2_FID, H_FID, 1.0], [0.002, 0.005, 0.002])
        return {"omega_m_h2": x[0], "h": x[1], "ruler_scale": x[2], "chi2": c}
    def f(x):
        try:
            return chi2({"omega_m_h2": x[0], "h": x[1]}, mock, sigma_scale=sigma_scale)
        except ValueError:
            return 1e30
    x, c = nelder_mead(f, [OMEGA_M_H2_FID, H_FID], [0.002, 0.005])
    return {"omega_m_h2": x[0], "h": x[1], "chi2": c}


def fit_w0wa(mock, sigma_scale=1.0):
    def f(x):
        try:
            return chi2({"omega_m_h2": x[0], "h": x[1], "w0": x[2], "wa": x[3]}, mock,
                        sigma_scale=sigma_scale)
        except ValueError:
            return 1e30
    x, c = nelder_mead(f, [OMEGA_M_H2_FID, H_FID, -1.0, 0.0],
                       [0.002, 0.005, 0.05, 0.2], iters=800)
    return {"omega_m_h2": x[0], "h": x[1], "w0": x[2], "wa": x[3], "chi2": c}


def profile_map(mock, w0_grid, wa_grid, sigma_scale=1.0):
    """Delta-chi2 landscape over (w0, wa), profiled over (omega_m_h2, h)."""
    rows = []
    for w0 in w0_grid:
        for wa in wa_grid:
            def f(x):
                try:
                    return chi2({"omega_m_h2": x[0], "h": x[1], "w0": w0, "wa": wa}, mock,
                                sigma_scale=sigma_scale)
                except ValueError:
                    return 1e30
            _, c = nelder_mead(f, [OMEGA_M_H2_FID, H_FID], [0.002, 0.005], iters=200)
            rows.append({"w0": round(w0, 4), "wa": round(wa, 4), "chi2": c})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fast", action="store_true", help="skip the (w0,wa) landscape map")
    ap.add_argument("--output", default=str(REPO_ROOT / "data" / "analysis"
                                            / "w0wa_rd_shift_diagnostic.json"))
    args = ap.parse_args(argv)

    delta = registered_shift()
    fid = Background(OMEGA_M_H2_FID, H_FID)

    mock_shifted = make_mock(fid, delta)
    mock_null = make_mock(fid, 0.0)

    # Controls first.
    c0 = fit_lcdm(mock_null)                      # must recover fiducial, chi2 ~ 0
    d = fit_lcdm(mock_shifted, ruler_free=True)   # must absorb: ruler_scale -> 1+delta
    # The question.
    a = fit_lcdm(mock_shifted)
    b = fit_w0wa(mock_shifted)
    # Precision scenario: DESI DR2-era BAO errors (aggregate ~0.24% vs DR1 ~0.52%
    # — arXiv:2503.14742 / 2404.03000), approximated as all per-tracer sigmas / 2.
    a2 = fit_lcdm(mock_shifted, sigma_scale=0.5)
    b2 = fit_w0wa(mock_shifted, sigma_scale=0.5)

    result = {
        "tool": TOOL, "tool_version": TOOL_VERSION,
        "status": "DIAGNOSTIC — not a registered prediction; direction and order of magnitude only",
        "determinism_note": "No timestamps; fixed grids and quadrature; SHA-256 is a function of registered inputs only.",
        "inputs": {
            "ruler_shift_delta": delta,
            "delta_source": "predictions_register/P1_bao_ruler_shift/pipeline_output.json (powerlaw delta_rs_relative)",
            "fiducial": {"h": H_FID, "omega_m_h2": OMEGA_M_H2_FID, "z_star": Z_STAR,
                         "r_d_std_mpc": R_D_STD_MPC},
            "anchors": {"sigma_omega_m_h2": SIGMA_OMEGA_M_H2,
                        "sigma_frac_dmstar_over_rd": SIGMA_FRAC_THETA},
            "bao_blocks": "DESI DR1 per-tracer sigmas and DM-DH correlations (values mocked)",
        },
        "controls": {
            "C0_unshifted_lcdm": c0,
            "D_shifted_lcdm_free_ruler": d,
            "C0_pass": bool(c0["chi2"] < 1e-4),
            "D_pass": bool(abs(d["ruler_scale"] - (1.0 + delta)) < 5e-4 and d["chi2"] < 1e-4),
        },
        "fits_on_shifted_mock": {
            "A_lcdm_std_ruler": a,
            "B_w0wa_std_ruler": b,
            "delta_chi2_lcdm_minus_w0wa": a["chi2"] - b["chi2"],
            "h_bias_lcdm_vs_fiducial_percent": 100.0 * (a["h"] - H_FID) / H_FID,
        },
        "fits_on_shifted_mock_dr2_precision": {
            "sigma_scale": 0.5,
            "A_lcdm_std_ruler": a2,
            "B_w0wa_std_ruler": b2,
            "delta_chi2_lcdm_minus_w0wa": a2["chi2"] - b2["chi2"],
        },
        "comparison_context": {
            "desi_dr2_preference_direction": "w0 > -1, wa < 0 (arXiv:2503.14738; 3.1 sigma BAO+CMB)",
            "dovekie_w0_wa": {"w0": -0.803, "w0_sigma": 0.054, "wa": -0.72, "wa_sigma": 0.21,
                              "source": "arXiv:2511.07517 (CMB+DESI DR2+recalibrated SNe)"},
            "note": ("Same-direction displacement would mean the GSC metrology shift mimics part of "
                     "the dynamical-DE signal; opposite-direction would count against that reading."),
        },
        "limitations": [
            "No SNe; compressed CMB anchors only (omega_m_h2 + theta*-like distance ratio).",
            "DESI DR1 per-tracer errors; no cross-tracer covariance.",
            "Mock background is exact LCDM (T2 background deviation at p=6e-4 neglected; the ruler shift is the leading GSC observable).",
            "theta* treated as exactly invariant under the coherent relabeling (P1 convention).",
            "Quadrature and r_d constants shared between mock and fit: differential-only validity.",
        ],
    }
    if not args.fast:
        w0_grid = [round(-1.3 + 0.04 * i, 4) for i in range(21)]   # -1.3 .. -0.5
        wa_grid = [round(-2.0 + 0.15 * i, 4) for i in range(21)]   # -2.0 .. +1.0
        result["landscape_w0_wa_profiled"] = profile_map(mock_shifted, w0_grid, wa_grid)

    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    print(f"wrote {out}")
    print(f"SHA-256: {hashlib.sha256(payload.encode()).hexdigest()}")
    print(json.dumps({k: result[k] for k in ("controls", "fits_on_shifted_mock")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
