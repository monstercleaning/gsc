#!/usr/bin/env python3
"""timescape_fit.py — DIAGNOSTIC: the timescape cosmology against DESI DR2 BAO (not a registered prediction).

Why this is here. GSC's intuition is that what changes is not space but the
standards measured with matter. In its universal form that is a change of units
(OPEN_PROBLEMS.md, problem 1). Wiltshire's timescape cosmology is the published
theory in which the change is not universal and has a known cause, ordinary
general relativity: in a lumpy universe, clocks and rulers in bound regions
("walls", where galaxies and observers live) are calibrated differently from
the volume average, which fast-expanding voids dominate. Reading the data with
our local clocks as if they held everywhere mimics cosmic acceleration, with no
dark energy. The model has one parameter besides the Hubble constant: today's
void volume fraction f_v0.

Formulas: the tracker solution of D. L. Wiltshire, Phys. Rev. D 80, 123512
(2009), arXiv:0909.0749, with t the volume-average time and Hbar0 the bare
(volume-average) Hubble constant:

  b = 2 (1-f)(2+f) / (9 f Hbar0),   t0 = (2+f) / (3 Hbar0)                    eq. 38
      (appendix B prints b without the factor 2; eq. 77 fixes it, and
       validate() checks the lapse function both ways)
  1 + z = 2^(4/3) t^(1/3) (t+b) / (f^(1/3) Hbar0 t (2t+3b)^(4/3))              eq. 37
  D = c (1+z) t^(2/3) [F(t0) - F(t)]      dressed comoving distance             eqs. 39-40
  H = 3 (2t^2 + 3bt + 2b^2) / (t (2t+3b)^2)   dressed Hubble parameter          eq. 78
  H0 = (4f^2 + f + 4) Hbar0 / (2 (2+f))                                         eq. 79
  dz/dtau = H0 (1+z) - H(z)               redshift drift in wall time           eq. 59
BAO observables take the FLRW form in the dressed quantities: D_M = D,
D_H = c/H, D_V = (z D^2 c/H)^(1/3) (eqs. 50-51).

Tests. (1) Validation against numbers published in the same paper. (2) DESI DR2
BAO shape with the BAO scale r_d free: its timescape calibration needs an early
universe recalibrated to timescape (Nazer & Wiltshire, PRD 91, 063519, 2015),
which this package does not implement, so only the shape of D_M(z) and D_H(z) is
tested. (3) The calibration-free Alcock-Paczynski ratio D_M/D_H. Flat ΛCDM is
fitted the same way, with the same number of free parameters.

Limits. DESI compresses its clustering data assuming a fiducial ΛCDM
cosmology; the compressed ratios are the standard way to test smooth
alternatives, but a model far from the fiducial may need a dedicated
reanalysis (Heinesen et al. 2019, arXiv:1811.11963). The tracker solution holds
from z ~ 37 onwards, which covers every redshift used here.

Deterministic, standard library only. Writes analyses/timescape_fit.json and
analyses/timescape_fit.md; `--check` recomputes and compares with tolerance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
OUT_JSON = REPO_ROOT / "analyses" / "timescape_fit.json"
OUT_MD = REPO_ROOT / "analyses" / "timescape_fit.md"
KM_S_MPC_TO_PER_YEAR = 1.0 / 3.0856775814913673e19 * 3.15576e7
C_KM_S = 299792.458

# Published values used for validation and comparison.
WILTSHIRE_2009 = {"f_v0": 0.762, "H0": 61.7, "drift_z4_10yr": -3.3e-10,
                  "Om0_minimum": 0.638, "Om0_minimum_at_f": 0.774}
SUPERNOVAE_2025 = {"f_v0": 0.737, "sigma": 0.029,
                   "source": "Seifert et al., MNRAS Letters 537, L55 (2025), Pantheon+"}
CMB_2015 = {"f_v0": 0.627, "sigma_stat_fraction": 0.023, "sigma_sys_fraction": 0.13, "H0": 61.0,
            "source": "Nazer & Wiltshire, PRD 91, 063519 (2015), Planck multipoles 50-2500"}
DESI_DR2_LCDM_BAO_ONLY = (0.2975, 0.0086)            # arXiv:2503.14738 v3, Table V


# --------------------------------------------------------------------------
# Timescape tracker solution (units: Hbar0 = 1)
# --------------------------------------------------------------------------

class Timescape:
    def __init__(self, f_v0):
        self.f = f = f_v0
        self.b = 2.0 * (1.0 - f) * (2.0 + f) / (9.0 * f)
        self.t0 = (2.0 + f) / 3.0
        self.H0 = (4.0 * f * f + f + 4.0) / (2.0 * (2.0 + f))      # dressed, in units of Hbar0
        self._F0 = self.F(self.t0)

    def one_plus_z(self, t):
        b = self.b
        return 2.0 ** (4.0 / 3.0) * t ** (1.0 / 3.0) * (t + b) / (self.f ** (1.0 / 3.0) * t * (2.0 * t + 3.0 * b) ** (4.0 / 3.0))

    def t_of_z(self, z):
        """Volume-average time at redshift z (1 + z decreases monotonically with t)."""
        lo, hi = math.log(self.t0) - 40.0, math.log(self.t0)
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if self.one_plus_z(math.exp(mid)) > 1.0 + z:
                lo = mid
            else:
                hi = mid
        return math.exp(0.5 * (lo + hi))

    def f_v(self, t):
        return 2.0 * t / (2.0 * t + 3.0 * self.b)

    def F(self, t):
        b3, t3 = self.b ** (1.0 / 3.0), t ** (1.0 / 3.0)
        return (2.0 * t3 + b3 / 6.0 * math.log((t3 + b3) ** 2 / (t3 * t3 - b3 * t3 + b3 * b3))
                + b3 / math.sqrt(3.0) * math.atan((2.0 * t3 - b3) / (math.sqrt(3.0) * b3)))

    def H(self, t):
        b = self.b
        return 3.0 * (2.0 * t * t + 3.0 * b * t + 2.0 * b * b) / (t * (2.0 * t + 3.0 * b) ** 2)

    # Dimensionless observables relative to the dressed Hubble constant.
    def h0_dm(self, z):
        """H0 D_M / c."""
        t = self.t_of_z(z)
        return self.H0 * (1.0 + z) * t ** (2.0 / 3.0) * (self._F0 - self.F(t))

    def e(self, z):
        """H(z) / H0 (dressed)."""
        return self.H(self.t_of_z(z)) / self.H0

    def drift(self, z):
        """(1/H0) dz/dtau, wall time."""
        return 1.0 + z - self.e(z)


class FlatLCDM:
    def __init__(self, omega_m):
        self.om = omega_m

    def e(self, z):
        return math.sqrt(self.om * (1.0 + z) ** 3 + 1.0 - self.om)

    def h0_dm(self, z, n=400):
        n += n % 2
        h = z / n
        s = 1.0 / self.e(0.0) + 1.0 / self.e(z)
        for i in range(1, n):
            s += (4.0 if i % 2 else 2.0) / self.e(i * h)
        return s * h / 3.0

    def drift(self, z):
        return 1.0 + z - self.e(z)


# --------------------------------------------------------------------------
# Data and likelihood (BAO scale free: model = A * shape, A = c/(H0 r_d))
# --------------------------------------------------------------------------

def load_bao():
    rows = []
    with open(DATA / "desi_dr2_bao.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            row = {"tracer": r["tracer"], "z": float(r["z_eff"])}
            if r["dv_over_rd"]:
                row.update(kind="DV", dv=float(r["dv_over_rd"]), sdv=float(r["sigma_dv_over_rd"]))
            else:
                row.update(kind="DMDH", dm=float(r["dm_over_rd"]), sdm=float(r["sigma_dm_over_rd"]),
                           dh=float(r["dh_over_rd"]), sdh=float(r["sigma_dh_over_rd"]), rho=float(r["rho_dm_dh"]))
            rows.append(row)
    return rows


def load_ap():
    with open(DATA / "desi_dr2_bao_dv_ap.csv", newline="", encoding="utf-8") as fh:
        return [{"tracer": r["tracer"], "z": float(r["z_eff"]), "ap": float(r["dm_over_dh"]),
                 "sap": float(r["sigma_dm_over_dh"])} for r in csv.DictReader(fh) if r["dm_over_dh"]]


def shape_blocks(model, rows):
    """Per-row model shape (without the scale A) and data, with inverse covariance blocks."""
    blocks = []
    for r in rows:
        z = r["z"]
        m_dm, m_dh = model.h0_dm(z), 1.0 / model.e(z)
        if r["kind"] == "DV":
            blocks.append(([(z * m_dm * m_dm * m_dh) ** (1.0 / 3.0)], [r["dv"]], [[1.0 / r["sdv"] ** 2]]))
        else:
            s1, s2, rho = r["sdm"], r["sdh"], r["rho"]
            det = s1 * s1 * s2 * s2 * (1.0 - rho * rho)
            icov = [[s2 * s2 / det, -rho * s1 * s2 / det], [-rho * s1 * s2 / det, s1 * s1 / det]]
            blocks.append(([m_dm, m_dh], [r["dm"], r["dh"]], icov))
    return blocks


def chi2_bao_scale_free(model, rows):
    """chi^2 minimized analytically over the scale A = c/(H0 r_d); returns (chi2, A)."""
    mcm = mcd = dcd = 0.0
    for m, d, ic in shape_blocks(model, rows):
        for i in range(len(m)):
            for j in range(len(m)):
                mcm += m[i] * ic[i][j] * m[j]
                mcd += m[i] * ic[i][j] * d[j]
                dcd += d[i] * ic[i][j] * d[j]
    a = mcd / mcm
    return dcd - mcd * mcd / mcm, a


def chi2_ap(model, ap_rows):
    return sum(((model.h0_dm(r["z"]) * model.e(r["z"]) - r["ap"]) / r["sap"]) ** 2 for r in ap_rows)


def chi2_dv_ap(model):
    """The alternative DESI compression: D_V/r_d (scale free) with D_M/D_H, correlated per tracer."""
    blocks = []
    with open(DATA / "desi_dr2_bao_dv_ap.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            z = float(r["z_eff"])
            dvm = (z * model.h0_dm(z) ** 2 / model.e(z)) ** (1.0 / 3.0)
            ap = None
            if r["dm_over_dh"]:
                ap = (model.h0_dm(z) * model.e(z), float(r["dm_over_dh"]), float(r["sigma_dm_over_dh"]),
                      float(r["rho_dv_ap"]))
            blocks.append((dvm, float(r["dv_over_rd"]), float(r["sigma_dv_over_rd"]), ap))

    def total(a):
        s = 0.0
        for dvm, dv, sdv, ap in blocks:
            x = (a * dvm - dv) / sdv
            if ap is None:
                s += x * x
            else:
                y = (ap[0] - ap[1]) / ap[2]
                s += (x * x - 2.0 * ap[3] * x * y + y * y) / (1.0 - ap[3] ** 2)
        return s
    lo, hi = 10.0, 60.0
    for _ in range(200):                       # golden-section style search on the scale
        m1, m2 = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
        if total(m1) < total(m2):
            hi = m2
        else:
            lo = m1
    return total(0.5 * (lo + hi))


def profile(make, grid, fn):
    return [{"param": p, "chi2": fn(make(p))} for p in grid]


def best_and_interval(curve, level):
    best = min(curve, key=lambda c: c["chi2"])
    inside = [c for c in curve if c["chi2"] - best["chi2"] <= level]
    edge = inside[0] is curve[0] or inside[-1] is curve[-1]
    return best, (inside[0]["param"], inside[-1]["param"]), edge


def grid(lo, hi, step):
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 6) for i in range(n + 1)]


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate():
    out = {}
    ts = Timescape(WILTSHIRE_2009["f_v0"])
    # (a) the redshift drift of a z = 4 source over ten years (Wiltshire 2009, sec. VII)
    dz = ts.drift(4.0) * WILTSHIRE_2009["H0"] * KM_S_MPC_TO_PER_YEAR * 10.0
    out["drift_z4_10yr"] = {"this_code": dz, "published": WILTSHIRE_2009["drift_z4_10yr"]}
    # (b) the Om(0) diagnostic, eq. 48, and its minimum near f = 0.774
    om0 = lambda f: 2.0 * (8 * f ** 3 - 3 * f ** 2 + 4) * (2 + f) / (4 * f * f + f + 4) ** 2
    tsm = Timescape(WILTSHIRE_2009["Om0_minimum_at_f"])
    z = 1e-4
    numeric = (tsm.e(z) ** 2 - 1.0) / ((1.0 + z) ** 3 - 1.0)
    out["Om0_at_f_0.774"] = {"numerical_from_H": numeric, "eq_48": om0(0.774),
                             "published_minimum": WILTSHIRE_2009["Om0_minimum"]}
    # (c) the closed-form distance equals the integral it came from (eq. 39)
    t = ts.t_of_z(1.0)
    n, a, bnd = 4000, t, ts.t0
    h = (bnd - a) / n
    g = lambda x: 2.0 / ((2.0 + ts.f_v(x)) * x ** (2.0 / 3.0))
    integral = (g(a) + g(bnd) + sum((4.0 if i % 2 else 2.0) * g(a + i * h) for i in range(1, n))) * h / 3.0
    out["distance_closed_form_vs_integral_z1"] = {"closed_form": ts._F0 - ts.F(t), "integral": integral}
    # (d) the lapse function both ways: (2 + f_v)/2 with f_v from eq. 72 equals 3(t+b)/(2t+3b) (eq. 77)
    fv72 = 3 * ts.f * t / (3 * ts.f * t + (1 - ts.f) * (2 + ts.f))        # eq. 72, Hbar0 = 1
    out["lapse_consistency_z1"] = {"from_eq72": (2.0 + fv72) / 2.0, "eq77_with_b_eq38": 3 * (t + ts.b) / (2 * t + 3 * ts.b)}
    # (e) the redshift map returns z = 0 today and inverts
    out["z_at_t0"] = ts.one_plus_z(ts.t0) - 1.0
    out["redshift_map_inverts_z2"] = ts.one_plus_z(ts.t_of_z(2.0)) - 3.0
    return out


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

DRIFT_Z = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)


def zero_crossing(model):
    lo, hi = 0.1, 6.0
    if model.drift(lo) * model.drift(hi) > 0:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if model.drift(lo) * model.drift(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def analyse():
    rows, ap_rows = load_bao(), load_ap()
    f_grid, om_grid = grid(0.30, 0.95, 0.005), grid(0.20, 0.45, 0.001)

    ts_bao = profile(Timescape, f_grid, lambda m: chi2_bao_scale_free(m, rows)[0])
    lc_bao = profile(FlatLCDM, om_grid, lambda m: chi2_bao_scale_free(m, rows)[0])
    ts_ap = profile(Timescape, f_grid, lambda m: chi2_ap(m, ap_rows))
    lc_ap = profile(FlatLCDM, om_grid, lambda m: chi2_ap(m, ap_rows))

    def summary(curve):
        best, one, edge1 = best_and_interval(curve, 1.0)
        _, two, edge2 = best_and_interval(curve, 4.0)
        return {"best": best["param"], "chi2_min": best["chi2"], "interval_1sigma": list(one),
                "interval_2sigma": list(two), "interval_reaches_scan_edge": edge1 or edge2}

    s = {"timescape_bao": summary(ts_bao), "lcdm_bao": summary(lc_bao),
         "timescape_ap": summary(ts_ap), "lcdm_ap": summary(lc_ap)}
    n_bao = sum(1 if r["kind"] == "DV" else 2 for r in rows)

    # Residuals at the best fits
    ts_best, lc_best = Timescape(s["timescape_bao"]["best"]), FlatLCDM(s["lcdm_bao"]["best"])
    _, a_ts = chi2_bao_scale_free(ts_best, rows)
    _, a_lc = chi2_bao_scale_free(lc_best, rows)
    residuals = []
    for r in rows:
        z = r["z"]
        item = {"tracer": r["tracer"], "z": z}
        for label, m, a in (("timescape", ts_best, a_ts), ("lcdm", lc_best, a_lc)):
            dm, dh = a * m.h0_dm(z), a / m.e(z)
            if r["kind"] == "DV":
                item[label] = {"DV_pull": ((z * dm * dm * dh) ** (1 / 3) - r["dv"]) / r["sdv"]}
            else:
                item[label] = {"DM_pull": (dm - r["dm"]) / r["sdm"], "DH_pull": (dh - r["dh"]) / r["sdh"]}
        residuals.append(item)

    # Robustness: another DESI compression, the fit without its worst bin, the published void fractions
    def best_of(make, g, fn):
        return min((fn(make(p)), p) for p in g)
    ts_dvap, lc_dvap = best_of(Timescape, f_grid, chi2_dv_ap), best_of(FlatLCDM, om_grid, chi2_dv_ap)
    worst = max(residuals, key=lambda r: max(abs(v) for v in r["timescape"].values()))["tracer"]
    rows_wo = [r for r in rows if r["tracer"] != worst]
    ts_wo = best_of(Timescape, f_grid, lambda m: chi2_bao_scale_free(m, rows_wo)[0])
    lc_wo = best_of(FlatLCDM, om_grid, lambda m: chi2_bao_scale_free(m, rows_wo)[0])
    z_ap = 0.934
    ap_scan = [(k / 100.0, Timescape(k / 100.0).h0_dm(z_ap) * Timescape(k / 100.0).e(z_ap)) for k in range(2, 99)]
    ap_min = min(ap_scan, key=lambda fa: fa[1])
    robustness = {
        "dv_ap_compression": {"timescape_chi2": ts_dvap[0], "timescape_f_v0": ts_dvap[1],
                              "lcdm_chi2": lc_dvap[0], "lcdm_Omega_m": lc_dvap[1], "delta_chi2": ts_dvap[0] - lc_dvap[0]},
        "without_worst_bin": {"dropped": worst, "timescape_chi2": ts_wo[0], "lcdm_chi2": lc_wo[0],
                              "delta_chi2": ts_wo[0] - lc_wo[0]},
        "bao_chi2_at_published_void_fractions": {
            "supernovae_f_0.737": chi2_bao_scale_free(Timescape(SUPERNOVAE_2025["f_v0"]), rows)[0],
            "cmb_f_0.627": chi2_bao_scale_free(Timescape(CMB_2015["f_v0"]), rows)[0]},
        "ap_ratio_at_z_0.934": {"desi": 1.223, "desi_sigma": 0.019,
                                "timescape_f_0.60": Timescape(0.60).h0_dm(z_ap) * Timescape(0.60).e(z_ap),
                                "timescape_f_0.75": Timescape(0.75).h0_dm(z_ap) * Timescape(0.75).e(z_ap),
                                "timescape_f_0.90": Timescape(0.90).h0_dm(z_ap) * Timescape(0.90).e(z_ap),
                                "lcdm_best": lc_best.h0_dm(z_ap) * lc_best.e(z_ap),
                                "timescape_min_over_f_v0_0.02_to_0.98": ap_min[1],
                                "timescape_min_at_f_v0": ap_min[0]},
    }

    # The void fraction from three probes
    cmb_sigma = CMB_2015["f_v0"] * math.hypot(CMB_2015["sigma_stat_fraction"], CMB_2015["sigma_sys_fraction"])
    probes = {"bao_shape_this_analysis": {"f_v0": s["timescape_bao"]["best"], "interval_1sigma": s["timescape_bao"]["interval_1sigma"]},
              "supernovae_2025": {"f_v0": SUPERNOVAE_2025["f_v0"], "sigma": SUPERNOVAE_2025["sigma"], "source": SUPERNOVAE_2025["source"]},
              "cmb_2015": {"f_v0": CMB_2015["f_v0"], "sigma_total": cmb_sigma, "source": CMB_2015["source"]}}

    # Redshift drift: the distinguishing forward observable
    def drift_table(model):
        return [{"z": z, "drift_over_H0": model.drift(z)} for z in DRIFT_Z]
    drift = {"timescape_bao_best": {"f_v0": ts_best.f, "zero_crossing_z": zero_crossing(ts_best), "curve": drift_table(ts_best)},
             "timescape_supernovae": {"f_v0": SUPERNOVAE_2025["f_v0"], "zero_crossing_z": zero_crossing(Timescape(SUPERNOVAE_2025["f_v0"])),
                                      "curve": drift_table(Timescape(SUPERNOVAE_2025["f_v0"]))},
             "lcdm_bao_best": {"Omega_m": lc_best.om, "zero_crossing_z": zero_crossing(lc_best), "curve": drift_table(lc_best)}}

    return {"tool": "timescape_fit.py",
            "status": "DIAGNOSTIC — the timescape cosmology against DESI DR2 BAO; not a registered prediction",
            "sources": {"formulas": "Wiltshire, PRD 80, 123512 (2009), arXiv:0909.0749",
                        "bao": "DESI DR2, arXiv:2503.14738 v3, Table IV"},
            "validation": validate(),
            "n_bao_data": n_bao, "n_ap_data": len(ap_rows),
            "fits": s,
            "delta_chi2_bao_timescape_minus_lcdm": s["timescape_bao"]["chi2_min"] - s["lcdm_bao"]["chi2_min"],
            "delta_chi2_ap_timescape_minus_lcdm": s["timescape_ap"]["chi2_min"] - s["lcdm_ap"]["chi2_min"],
            "desi_published_lcdm_bao_only_Omega_m": list(DESI_DR2_LCDM_BAO_ONLY),
            "best_fit_scale_c_over_H0_rd": {"timescape": a_ts, "lcdm": a_lc},
            "residual_pulls": residuals,
            "robustness": robustness,
            "void_fraction_by_probe": probes,
            "redshift_drift": drift}


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _round(x, digits=6):
    if isinstance(x, float):
        return float(f"{x:.{digits}g}") if x else 0.0
    if isinstance(x, dict):
        return {k: _round(v, digits) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v, digits) for v in x]
    return x


def render_markdown(res):
    v, fits = res["validation"], res["fits"]
    tb, lb, ta, la = fits["timescape_bao"], fits["lcdm_bao"], fits["timescape_ap"], fits["lcdm_ap"]
    pr, dr = res["void_fraction_by_probe"], res["redshift_drift"]
    lines = [
        "# The timescape cosmology against DESI DR2 BAO",
        "",
        "<!-- GENERATED by analyses/timescape_fit.py from analyses/timescape_fit.json. Do not edit by hand. -->",
        "",
        "Diagnostic, not a registered prediction. Timescape (Wiltshire) replaces dark energy with a calibration effect of",
        "ordinary gravity: clocks and rulers in galaxies differ from the volume average that fast-expanding voids",
        "dominate. Formulas: Wiltshire, PRD 80, 123512 (2009). Data: DESI DR2 BAO (arXiv:2503.14738 v3).",
        "Code: [timescape_fit.py](timescape_fit.py); numbers: [timescape_fit.json](timescape_fit.json).",
        "",
        "## Validation against the published model",
        "",
        "| Check | This code | Published |",
        "|---|---|---|",
        f"| Drift of a z = 4 source over 10 years (f_v0 = 0.762, H0 = 61.7) | {v['drift_z4_10yr']['this_code']:.2e} | {v['drift_z4_10yr']['published']:.1e} |",
        f"| Om(0) at f_v0 = 0.774, from H(z) / from eq. 48 | {v['Om0_at_f_0.774']['numerical_from_H']:.4f} / {v['Om0_at_f_0.774']['eq_48']:.4f} | minimum ≈ 0.638 |",
        f"| Closed-form distance vs its integral, z = 1 | {v['distance_closed_form_vs_integral_z1']['closed_form']:.6f} / {v['distance_closed_form_vs_integral_z1']['integral']:.6f} | equal |",
        f"| Lapse function, eq. 72 route / eq. 77 with b from eq. 38 | {v['lapse_consistency_z1']['from_eq72']:.6f} / {v['lapse_consistency_z1']['eq77_with_b_eq38']:.6f} | equal |",
        "",
        "## Fit to DESI DR2 BAO, BAO scale free",
        "",
        f"Both models have two free parameters: the scale c/(H0 r_d) and one shape parameter. {res['n_bao_data']} data points.",
        "",
        "| Model | Shape parameter | Best fit | 1σ range | χ² |",
        "|---|---|---|---|---|",
        f"| Timescape | void fraction f_v0 | {tb['best']:.3f} | {tb['interval_1sigma'][0]:.3f}–{tb['interval_1sigma'][1]:.3f} | {tb['chi2_min']:.2f} |",
        f"| Flat ΛCDM | Ω_m | {lb['best']:.3f} | {lb['interval_1sigma'][0]:.3f}–{lb['interval_1sigma'][1]:.3f} | {lb['chi2_min']:.2f} |",
        "",
        f"Δχ² (timescape − ΛCDM) = {res['delta_chi2_bao_timescape_minus_lcdm']:+.2f}. For comparison, DESI's own BAO-only ΛCDM fit gives",
        f"Ω_m = {res['desi_published_lcdm_bao_only_Omega_m'][0]} ± {res['desi_published_lcdm_bao_only_Omega_m'][1]}.",
        "",
        "**Alcock–Paczyński ratio D_M/D_H alone** (no BAO scale at all, "
        f"{res['n_ap_data']} points): timescape f_v0 = {ta['best']:.3f} (χ² {ta['chi2_min']:.2f}); ΛCDM Ω_m = {la['best']:.3f} (χ² {la['chi2_min']:.2f});",
        f"Δχ² = {res['delta_chi2_ap_timescape_minus_lcdm']:+.2f}.",
        "",
        "Pulls at the best fits, (model − data)/σ:",
        "",
        "| Tracer | z | Timescape | ΛCDM |",
        "|---|---|---|---|",
    ]
    for r in res["residual_pulls"]:
        fmt = lambda d: " / ".join(f"{k.split('_')[0]} {val:+.2f}" for k, val in d.items())
        lines.append(f"| {r['tracer']} | {r['z']} | {fmt(r['timescape'])} | {fmt(r['lcdm'])} |")
    rb = res["robustness"]
    apz = rb["ap_ratio_at_z_0.934"]
    lines += ["", "## Is the result robust?", "",
              "| Check | Timescape χ² | ΛCDM χ² | Δχ² |", "|---|---|---|---|",
              f"| The other DESI compression: D_V/r_d with D_M/D_H | {rb['dv_ap_compression']['timescape_chi2']:.2f} | {rb['dv_ap_compression']['lcdm_chi2']:.2f} | {rb['dv_ap_compression']['delta_chi2']:+.2f} |",
              f"| Without the worst-fitting bin ({rb['without_worst_bin']['dropped']}) | {rb['without_worst_bin']['timescape_chi2']:.2f} | {rb['without_worst_bin']['lcdm_chi2']:.2f} | {rb['without_worst_bin']['delta_chi2']:+.2f} |",
              f"| At the supernova void fraction, f_v0 = 0.737 | {rb['bao_chi2_at_published_void_fractions']['supernovae_f_0.737']:.2f} | {lb['chi2_min']:.2f} | {rb['bao_chi2_at_published_void_fractions']['supernovae_f_0.737'] - lb['chi2_min']:+.2f} |",
              f"| At the CMB void fraction, f_v0 = 0.627 | {rb['bao_chi2_at_published_void_fractions']['cmb_f_0.627']:.2f} | {lb['chi2_min']:.2f} | {rb['bao_chi2_at_published_void_fractions']['cmb_f_0.627'] - lb['chi2_min']:+.2f} |",
              "",
              f"The Alcock–Paczyński ratio at z = 0.934 is at least {apz['timescape_min_over_f_v0_0.02_to_0.98']:.3f} for every void fraction from 0.02 to 0.98 (the minimum",
              f"is at f_v0 = {apz['timescape_min_at_f_v0']:.2f}); it is {apz['timescape_f_0.60']:.3f}, {apz['timescape_f_0.75']:.3f} and {apz['timescape_f_0.90']:.3f} for f_v0 = 0.60, 0.75 and 0.90. DESI measures",
              f"{apz['desi']} ± {apz['desi_sigma']}; ΛCDM at its best fit gives {apz['lcdm_best']:.3f}. So the mismatch is a property of the model's shape, not of a",
              "parameter choice."]
    cmb = pr["cmb_2015"]
    lines += ["", "## The void fraction from three probes", "",
              "| Probe | f_v0 |", "|---|---|",
              f"| DESI DR2 BAO shape (this analysis) | {pr['bao_shape_this_analysis']['f_v0']:.3f} (1σ {pr['bao_shape_this_analysis']['interval_1sigma'][0]:.3f}–{pr['bao_shape_this_analysis']['interval_1sigma'][1]:.3f}) |",
              f"| Pantheon+ supernovae (Seifert et al. 2025) | {pr['supernovae_2025']['f_v0']:.3f} ± {pr['supernovae_2025']['sigma']:.3f} |",
              f"| Planck CMB multipoles (Nazer & Wiltshire 2015) | {cmb['f_v0']:.3f} ± {cmb['sigma_total']:.3f} (statistical and systematic) |",
              "", "## The distinguishing forward observable: redshift drift", "",
              "(1/H0) dz/dτ, dimensionless, so independent of the Hubble constant. It changes sign at the redshift where the",
              "expansion stops looking accelerated:", "",
              "| z | Timescape, BAO best fit | Timescape, supernova f_v0 | ΛCDM, BAO best fit |", "|---|---|---|---|"]
    for a, b, c in zip(dr["timescape_bao_best"]["curve"], dr["timescape_supernovae"]["curve"], dr["lcdm_bao_best"]["curve"]):
        lines.append(f"| {a['z']} | {a['drift_over_H0']:+.4f} | {b['drift_over_H0']:+.4f} | {c['drift_over_H0']:+.4f} |")
    zc = lambda d: "none below z = 6" if d["zero_crossing_z"] is None else f"{d['zero_crossing_z']:.3f}"
    lines += [f"| sign change at z | {zc(dr['timescape_bao_best'])} | {zc(dr['timescape_supernovae'])} | {zc(dr['lcdm_bao_best'])} |",
              "", "## Limits", "",
              "- The BAO scale is free: linking it to the CMB needs the timescape recalibration of the early universe, which",
              "  this package does not implement.",
              "- DESI compresses its clustering data with a fiducial ΛCDM cosmology; a model far from the fiducial may need a",
              "  dedicated reanalysis.",
              "- The supernova and CMB void fractions are quoted from the papers, not recomputed here.", ""]
    return "\n".join(lines)


def _compare(a, b, path="$"):
    if isinstance(b, dict):
        return [e for k in b for e in _compare(a.get(k) if isinstance(a, dict) else None, b[k], f"{path}.{k}")]
    if isinstance(b, list):
        if not isinstance(a, list) or len(a) != len(b):
            return [f"{path}: structure differs"]
        return [e for i, (x, y) in enumerate(zip(a, b)) for e in _compare(x, y, f"{path}[{i}]")]
    if isinstance(b, float) and isinstance(a, (int, float)):
        return [] if abs(a - b) <= 2e-3 * max(1.0, abs(b)) else [f"{path}: {a} != {b}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="recompute and compare with the committed JSON")
    args = ap.parse_args(argv)
    res = _round(analyse())
    if args.check:
        committed = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        problems = _compare(res, committed)
        md_current = OUT_MD.read_text(encoding="utf-8") == render_markdown(committed)
        for p in problems[:10]:
            print("DIFFERS", p)
        if not md_current:
            print("DIFFERS: timescape_fit.md is not the rendering of timescape_fit.json")
        ok = not problems and md_current
        print("timescape fit reproduces its committed output" if ok else "timescape fit does NOT reproduce its committed output")
        return 0 if ok else 1
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(res), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
