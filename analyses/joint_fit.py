#!/usr/bin/env python3
"""joint_fit.py — DIAGNOSTIC behind OPEN_PROBLEMS.md problems 1, 4, 5 and 8 (not a registered prediction).

Question. OPEN_PROBLEMS.md problem 1 found one coherent reading of the canonical
exponent: particle masses drift relative to the Planck mass only above z = 10
(the "early-transition" variant). Tuned to reproduce P1's registered BAO shift
at fixed cosmological parameters, it needs q = 8.65e-4. Does that variant
survive once the cosmological parameters are refitted to the CMB and BAO data,
and what is left of its signature?

Data.
  * CMB: Planck 2018 distance priors (R, l_A, omega_b), Chen, Huang & Wang,
    JCAP 02 (2019) 028 (data/planck2018_distance_priors.json); n_s is
    marginalized by dropping its row and column.
  * BAO: DESI DR2, arXiv:2503.14738 v3, Table IV (data/desi_dr2_bao.csv):
    D_V/r_d for BGS and correlated (D_M/r_d, D_H/r_d) pairs for six tracers.

Models (flat; one massive neutrino of 0.06 eV counted as matter). Masses
m = m0 g(z_E) relative to the Planck mass, Einstein frame, photons conformal,
observed redshift 1 + z = (1 + z_E)/g (the construction of
analyses/p_role_consistency.py, with closed-form redshift maps):
  lcdm              g = 1
  early_transition  g = 1 below z_E = 10, ((1 + z_E)/11)^(-q) above
  powerlaw          g = (1 + z_E)^(-q)            (q = p: excluded locally by lunar ranging)
  history_b         H = H_LCDM(z) (1 + z)^p, standard redshifts (the P8 r2 history)
Recombination and drag redshifts use the fitting formulae with the effective
matter density omega_m G_eff, where G_eff = g^2 is the gravitational coupling in
atomic units (history_b: (1 + z)^(2p)). r_d for BAO is the CAMB-calibrated
formula of Aubourg et al. (2015, eq. 16) times the model-to-LCDM ratio of the
sound-horizon integral at the same parameters.

Limits. Compressed CMB priors capture the acoustic scale and the shift
parameter, not the damping tail or the peak heights, which a change of the
early expansion rate also moves. Passing here is necessary, not sufficient.

Deterministic, standard library only. Writes analyses/joint_fit.json and
analyses/joint_fit.md; `--check` recomputes and compares with tolerance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gsc.canonical_params import CANONICAL_P  # noqa: E402
from gsc.early_time.rd import z_drag_eisenstein_hu  # noqa: E402

C = 299792.458                       # km/s
T_CMB = 2.7255                       # K
THETA4 = (T_CMB / 2.7) ** 4
OMEGA_NU = 0.06 / 93.14              # one massive neutrino, 0.06 eV
Z_TRANSITION = 10.0
U_MAX = math.log(1.0 + 1.0e7)        # upper limit of the sound-horizon integral in ln(1 + z)
DATA = REPO_ROOT / "data"
OUT_JSON = REPO_ROOT / "analyses" / "joint_fit.json"
OUT_MD = REPO_ROOT / "analyses" / "joint_fit.md"
PLANCK2018_TTTEEE_LOWE = {"h": 0.6727, "omega_b": 0.02236, "omega_c": 0.1202}  # Planck 2018 VI, Table 2
DESI_DR2_LCDM = {"DESI": {"Omega_m": (0.2975, 0.0086)},                        # arXiv:2503.14738 v3, Table V
                 "DESI+CMB": {"Omega_m": (0.3027, 0.0036), "H0": (68.17, 0.28)}}
G1_COEFFICIENT = 0.0738              # as printed in Chen, Huang & Wang (2019) eq. 9
Z_STAR_PLANCK = 1089.95              # Planck 2018 VI, Table 2, TT,TE,EE+lowE


def simpson(f, a, b, n):
    n += n % 2
    h = (b - a) / n
    s = f(a) + f(b)
    for i in range(1, n):
        s += (4.0 if i % 2 else 2.0) * f(a + i * h)
    return s * h / 3.0


def z_star_formula(omega_b, omega_m, g1_coefficient=G1_COEFFICIENT):
    """Recombination redshift as printed in Chen, Huang & Wang (2019) eqs. 8-10 (Hu & Sugiyama 1996)."""
    g1 = g1_coefficient * omega_b ** -0.238 / (1.0 + 39.5 * omega_b ** 0.763)
    g2 = 0.560 / (1.0 + 21.1 * omega_b ** 1.81)
    return 1048.0 * (1.0 + 0.00124 * omega_b ** -0.738) * (1.0 + g1 * omega_m ** g2)


# The printed formula gives z* = 1090.65 at the Planck 2018 parameters, where
# Planck's own z* is 1089.95; with the printed value the priors' central l_A is
# missed by 1.8 sigma at those parameters, with Planck's by 0.3 sigma. The priors
# were evidently derived with the chains' z*, so the formula is rescaled by one
# constant to equal Planck's z* there; its parameter dependence is kept.
Z_STAR_SCALE = Z_STAR_PLANCK / z_star_formula(
    PLANCK2018_TTTEEE_LOWE["omega_b"],
    PLANCK2018_TTTEEE_LOWE["omega_b"] + PLANCK2018_TTTEEE_LOWE["omega_c"] + OMEGA_NU)


def z_star_hu_sugiyama(omega_b, omega_m):
    return Z_STAR_SCALE * z_star_formula(omega_b, omega_m)


def rd_aubourg(omega_b, omega_c):
    """CAMB-convention drag sound horizon in Mpc, Aubourg et al. (2015) eq. 16 (0.021% accuracy)."""
    return (55.154 * math.exp(-72.3 * (OMEGA_NU + 0.0006) ** 2)
            / ((omega_b + omega_c) ** 0.25351 * omega_b ** 0.12807))


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

class LCDM:
    name = "lcdm"

    def __init__(self, h, omega_b, omega_c, q=0.0):
        self.h, self.omega_b, self.omega_c, self.q = h, omega_b, omega_c, q
        self.omega_m = omega_b + omega_c + OMEGA_NU
        self.Om = self.omega_m / h ** 2
        self.Or = self.Om / (1.0 + 2.5e4 * self.omega_m / THETA4)   # Chen et al. eq. 6
        self.OL = 1.0 - self.Om - self.Or
        self.H0 = 100.0 * h

    # Einstein-frame bookkeeping: identity for LCDM.
    def g(self, zE):
        return 1.0

    def zobs(self, zE):
        return zE

    def zE(self, zo):
        return zo

    def dzobs_dzE(self, zE):
        return 1.0

    def G_eff(self, zo):
        """Gravitational coupling in atomic units, relative to today, at observed redshift zo."""
        return self.g(self.zE(zo)) ** 2

    def HE(self, zE):
        x = 1.0 + zE
        return self.H0 * math.sqrt(self.Or * x ** 4 + self.Om * self.g(zE) * x ** 3 + self.OL)

    # Observables (lengths in Mpc, comoving).
    def dm(self, zo, n=64):
        return simpson(lambda u: C * math.exp(u) / self.HE(math.expm1(u)), 0.0, math.log1p(self.zE(zo)), n)

    def dh(self, zo):
        zE = self.zE(zo)
        return C / (self.dzobs_dzE(zE) * self.HE(zE))

    def dv(self, zo):
        return (zo * self.dm(zo) ** 2 * self.dh(zo)) ** (1.0 / 3.0)

    def sound_horizon(self, zo, n=800):
        rb0 = 31500.0 * self.omega_b / THETA4                          # Chen et al. eq. 3

        def f(u):
            zE = math.expm1(u)
            a_obs = 1.0 / (1.0 + self.zobs(zE))                        # baryon loading in atomic units
            return C / math.sqrt(3.0 * (1.0 + rb0 * a_obs)) * math.exp(u) / self.HE(zE)
        return simpson(f, math.log1p(self.zE(zo)), U_MAX, n)

    def z_star(self):
        zs = 1090.0
        for _ in range(3):
            zs = z_star_hu_sugiyama(self.omega_b, self.omega_m * self.G_eff(zs))
        return zs

    def z_drag(self):
        zd = 1060.0
        for _ in range(3):
            zd = z_drag_eisenstein_hu(omega_m_h2=self.omega_m * self.G_eff(zd), omega_b_h2=self.omega_b)
        return zd

    def cmb(self):
        zs = self.z_star()
        dm = self.dm(zs, n=1000)
        return {"z_star": zs, "R": 100.0 * math.sqrt(self.omega_m) * dm / C,
                "l_A": math.pi * dm / self.sound_horizon(zs), "omega_b": self.omega_b}

    def r_d(self):
        base = rd_aubourg(self.omega_b, self.omega_c)
        if type(self) is LCDM:
            return base
        ref = LCDM(self.h, self.omega_b, self.omega_c)
        return base * self.sound_horizon(self.z_drag()) / ref.sound_horizon(ref.z_drag())


class EarlyTransition(LCDM):
    """Masses frozen below z_E = 10 and drifting above it with exponent q."""
    name = "early_transition"
    _K = 1.0 + Z_TRANSITION

    def g(self, zE):
        return 1.0 if zE < Z_TRANSITION else ((1.0 + zE) / self._K) ** -self.q

    def zobs(self, zE):
        if zE < Z_TRANSITION:
            return zE
        return (1.0 + zE) ** (1.0 + self.q) * self._K ** -self.q - 1.0

    def zE(self, zo):
        if zo < Z_TRANSITION:
            return zo
        return ((1.0 + zo) * self._K ** self.q) ** (1.0 / (1.0 + self.q)) - 1.0

    def dzobs_dzE(self, zE):
        return 1.0 if zE < Z_TRANSITION else (1.0 + self.q) * (1.0 + self.zobs(zE)) / (1.0 + zE)


class PowerLaw(LCDM):
    """Masses drift at all times: g = (1 + z_E)^(-q)."""
    name = "powerlaw"

    def g(self, zE):
        return (1.0 + zE) ** -self.q

    def zobs(self, zE):
        return (1.0 + zE) ** (1.0 + self.q) - 1.0

    def zE(self, zo):
        return (1.0 + zo) ** (1.0 / (1.0 + self.q)) - 1.0

    def dzobs_dzE(self, zE):
        return (1.0 + self.q) * (1.0 + zE) ** self.q


class HistoryB(LCDM):
    """The P8 revision r2 history: H = H_LCDM(z) (1 + z)^p, standard redshifts."""
    name = "history_b"

    def HE(self, zE):
        return LCDM.HE(self, zE) * (1.0 + zE) ** self.q

    def G_eff(self, zo):
        return (1.0 + zo) ** (2.0 * self.q)


MODELS = {cls.name: cls for cls in (LCDM, EarlyTransition, PowerLaw, HistoryB)}


# --------------------------------------------------------------------------
# Likelihoods
# --------------------------------------------------------------------------

def _inv3(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    adj = [[e * i - f * h, c * h - b * i, b * f - c * e],
           [f * g - d * i, a * i - c * g, c * d - a * f],
           [d * h - e * g, b * g - a * h, a * e - b * d]]
    return [[x / det for x in row] for row in adj]


def load_data():
    priors = json.loads((DATA / "planck2018_distance_priors.json").read_text(encoding="utf-8"))
    idx = [priors["parameters"].index(k) for k in ("R", "l_A", "omega_b")]
    mean = [priors["mean"][i] for i in idx]
    sig = [priors["sigma"][i] for i in idx]
    cov = [[priors["correlation"][i][j] * sig[a] * sig[b] for b, j in enumerate(idx)] for a, i in enumerate(idx)]
    bao = []
    with open(DATA / "desi_dr2_bao.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            row = {"tracer": r["tracer"], "z": float(r["z_eff"])}
            if r["dv_over_rd"]:
                row.update(kind="DV", dv=float(r["dv_over_rd"]), sdv=float(r["sigma_dv_over_rd"]))
            else:
                row.update(kind="DMDH", dm=float(r["dm_over_rd"]), sdm=float(r["sigma_dm_over_rd"]),
                           dh=float(r["dh_over_rd"]), sdh=float(r["sigma_dh_over_rd"]), rho=float(r["rho_dm_dh"]))
            bao.append(row)
    return {"cmb_mean": mean, "cmb_icov": _inv3(cov), "bao": bao}


def chi2_cmb(model, data):
    obs = model.cmb()
    d = [obs["R"] - data["cmb_mean"][0], obs["l_A"] - data["cmb_mean"][1], obs["omega_b"] - data["cmb_mean"][2]]
    ic = data["cmb_icov"]
    return sum(d[i] * ic[i][j] * d[j] for i in range(3) for j in range(3))


def chi2_bao(model, data):
    rd = model.r_d()
    chi2 = 0.0
    for r in data["bao"]:
        if r["kind"] == "DV":
            chi2 += ((model.dv(r["z"]) / rd - r["dv"]) / r["sdv"]) ** 2
        else:
            x = (model.dm(r["z"]) / rd - r["dm"]) / r["sdm"]
            y = (model.dh(r["z"]) / rd - r["dh"]) / r["sdh"]
            chi2 += (x * x - 2.0 * r["rho"] * x * y + y * y) / (1.0 - r["rho"] ** 2)
    return chi2


def chi2_total(model, data, use=("cmb", "bao")):
    return (chi2_cmb(model, data) if "cmb" in use else 0.0) + (chi2_bao(model, data) if "bao" in use else 0.0)


# --------------------------------------------------------------------------
# Minimizer (Nelder-Mead, deterministic)
# --------------------------------------------------------------------------

def nelder_mead(f, x0, steps, tol=1e-9, max_iter=3000):
    n = len(x0)
    pts = [list(x0)] + [[x0[j] + (steps[j] if j == i else 0.0) for j in range(n)] for i in range(n)]
    vals = [f(p) for p in pts]
    for _ in range(max_iter):
        order = sorted(range(n + 1), key=lambda i: vals[i])
        pts, vals = [pts[i] for i in order], [vals[i] for i in order]
        if vals[-1] - vals[0] < tol:
            break
        cen = [sum(p[j] for p in pts[:-1]) / n for j in range(n)]
        ref = [2.0 * cen[j] - pts[-1][j] for j in range(n)]
        fr = f(ref)
        if fr < vals[0]:
            exp_ = [3.0 * cen[j] - 2.0 * pts[-1][j] for j in range(n)]
            fe = f(exp_)
            pts[-1], vals[-1] = (exp_, fe) if fe < fr else (ref, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = ref, fr
        else:
            tgt = ref if fr < vals[-1] else pts[-1]
            con = [cen[j] + 0.5 * (tgt[j] - cen[j]) for j in range(n)]
            fc = f(con)
            if fc < min(fr, vals[-1]):
                pts[-1], vals[-1] = con, fc
            else:
                for i in range(1, n + 1):
                    pts[i] = [pts[0][j] + 0.5 * (pts[i][j] - pts[0][j]) for j in range(n)]
                    vals[i] = f(pts[i])
    best = min(range(n + 1), key=lambda i: vals[i])
    return pts[best], vals[best]


def fit(name, q, data, use=("cmb", "bao"), start=(0.68, 0.02237, 0.1190)):
    cls = MODELS[name]

    def f(x):
        h, wb, wc = x
        if not (0.4 < h < 1.0 and 0.01 < wb < 0.04 and 0.05 < wc < 0.25):
            return 1e12
        m = cls(h, wb, wc, q)
        return 1e12 if m.OL <= 0 else chi2_total(m, data, use)

    x, v = nelder_mead(f, start, (0.01, 0.0004, 0.004))
    for step in ((0.002, 0.0001, 0.001), (0.0005, 0.00002, 0.0002)):
        x, v = nelder_mead(f, x, step)
    return {"h": x[0], "omega_b": x[1], "omega_c": x[2], "chi2": v}


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

Z_BBN = 4.3e8                           # as in analyses/p_role_consistency.py
BBN_G_RATIO_2SIGMA = (0.94, 1.05)       # Alvey et al. 2020, arXiv:1910.10730: G_BBN/G0 = 0.99 +0.06/-0.05 (2 sigma)
GRIDS = {
    "early_transition": (-1e-2, -5e-3, -2e-3, -1e-3, -5e-4, 0.0, 5e-4, 1e-3, 2e-3, 5e-3, 1e-2),
    "powerlaw": (-2e-3, -1e-3, -5e-4, 0.0, 1.73e-4, 5e-4, 1e-3, 2e-3, 3e-3, 4e-3, 5e-3, 6e-3, 7.5e-3, 1e-2),
    "history_b": (-5e-3, -4e-3, -3e-3, -2.5e-3, -2e-3, -1.5e-3, -1e-3, -5e-4, 0.0, 5e-4, 1e-3, 2e-3),
}


def q_tuned_to_p1():
    record = json.loads((REPO_ROOT / "analyses" / "p_role_consistency.json").read_text(encoding="utf-8"))
    return record["model_A_early_transition"]["q_prime_tuned_to_p1"]


def g_ratio_early_transition(q, z):
    """G/G0 in atomic units at observed redshift z (above the transition), early-transition variant."""
    zE = EarlyTransition(0.68, 0.0224, 0.12, q).zE(z)
    return EarlyTransition(0.68, 0.0224, 0.12, q).g(zE) ** 2


def _cosmo(model):
    return {"h": model.h, "H0": model.H0, "omega_b": model.omega_b, "omega_c": model.omega_c, "Omega_m": model.Om}


def signature(name, q, fit_model, fit_lcdm, data):
    """Percent differences of D_M/r_d and D_H/r_d from the LCDM best fit, before and after refitting."""
    ref = LCDM(fit_lcdm["h"], fit_lcdm["omega_b"], fit_lcdm["omega_c"])
    fixed = MODELS[name](fit_lcdm["h"], fit_lcdm["omega_b"], fit_lcdm["omega_c"], q)
    refit = MODELS[name](fit_model["h"], fit_model["omega_b"], fit_model["omega_c"], q)
    rd = {id(m): m.r_d() for m in (ref, fixed, refit)}
    rows = []
    for r in data["bao"]:
        z = r["z"]
        dm = {id(m): m.dm(z) / rd[id(m)] for m in (ref, fixed, refit)}
        dh = {id(m): m.dh(z) / rd[id(m)] for m in (ref, fixed, refit)}
        rows.append({"tracer": r["tracer"], "z": z,
                     "DM_over_rd_fixed_percent": 100.0 * (dm[id(fixed)] / dm[id(ref)] - 1.0),
                     "DM_over_rd_refit_percent": 100.0 * (dm[id(refit)] / dm[id(ref)] - 1.0),
                     "DH_over_rd_fixed_percent": 100.0 * (dh[id(fixed)] / dh[id(ref)] - 1.0),
                     "DH_over_rd_refit_percent": 100.0 * (dh[id(refit)] / dh[id(ref)] - 1.0)})
    return rows


def interval(curve, level):
    """q-range where delta_chi2 - min <= level, by linear interpolation; None marks an open edge."""
    best = min(p["delta_chi2"] for p in curve)
    inside = [p["delta_chi2"] - best <= level for p in curve]
    if not any(inside):
        return [None, None]
    i0 = inside.index(True)
    i1 = len(inside) - 1 - inside[::-1].index(True)

    def cross(a, b):
        ya, yb = a["delta_chi2"] - best - level, b["delta_chi2"] - best - level
        return a["q"] + (b["q"] - a["q"]) * ya / (ya - yb)
    lo = None if i0 == 0 else cross(curve[i0 - 1], curve[i0])
    hi = None if i1 == len(curve) - 1 else cross(curve[i1], curve[i1 + 1])
    return [lo, hi]


def analyse():
    data = load_data()
    q_p1 = q_tuned_to_p1()
    lcdm = fit("lcdm", 0.0, data)
    start = (lcdm["h"], lcdm["omega_b"], lcdm["omega_c"])
    lcdm_model = LCDM(*start)

    # Validation: the implementation reproduces the priors and DESI's own LCDM results.
    planck = LCDM(PLANCK2018_TTTEEE_LOWE["h"], PLANCK2018_TTTEEE_LOWE["omega_b"], PLANCK2018_TTTEEE_LOWE["omega_c"])
    p_obs = planck.cmb()
    bao_only = fit("lcdm", 0.0, data, use=("bao",))
    restart = fit("lcdm", 0.0, data, start=(0.72, 0.0220, 0.1250))
    validation = {
        "priors_at_planck2018_parameters": {
            "R": p_obs["R"], "R_sigma_offset": (p_obs["R"] - data["cmb_mean"][0]) / 0.0046,
            "l_A": p_obs["l_A"], "l_A_sigma_offset": (p_obs["l_A"] - data["cmb_mean"][1]) / 0.0895,
            "z_star": p_obs["z_star"], "z_star_printed_formula": z_star_formula(
                PLANCK2018_TTTEEE_LOWE["omega_b"],
                PLANCK2018_TTTEEE_LOWE["omega_b"] + PLANCK2018_TTTEEE_LOWE["omega_c"] + OMEGA_NU)},
        "rd_at_planck2018_parameters_Mpc": planck.r_d(),
        "lcdm_bao_only": {"Omega_m": LCDM(bao_only["h"], bao_only["omega_b"], bao_only["omega_c"]).Om,
                          "chi2": bao_only["chi2"], "desi_dr2_published": DESI_DR2_LCDM["DESI"]},
        "lcdm_cmb_plus_bao": dict(_cosmo(lcdm_model), chi2=lcdm["chi2"],
                                  desi_dr2_published_full_cmb=DESI_DR2_LCDM["DESI+CMB"]),
        "lcdm_refit_from_another_start_chi2_difference": restart["chi2"] - lcdm["chi2"],
        "n_data": {"cmb": 3, "bao": sum(1 if r["kind"] == "DV" else 2 for r in data["bao"])},
    }

    fixed = {}
    for name, q in (("early_transition", q_p1), ("powerlaw", CANONICAL_P), ("history_b", CANONICAL_P)):
        r = fit(name, q, data, start=start)
        m = MODELS[name](r["h"], r["omega_b"], r["omega_c"], q)
        fixed[name] = dict(_cosmo(m), q=q, chi2=r["chi2"], delta_chi2=r["chi2"] - lcdm["chi2"],
                           chi2_cmb=chi2_cmb(m, data), chi2_bao=chi2_bao(m, data),
                           signature=signature(name, q, r, lcdm, data))

    profiles = {}
    for name, grid in GRIDS.items():
        curve = []
        for q in grid:
            r = fit(name, q, data, start=start)
            m = MODELS[name](r["h"], r["omega_b"], r["omega_c"], q)
            curve.append({"q": q, "delta_chi2": r["chi2"] - lcdm["chi2"], "H0": m.H0, "Omega_m": m.Om})
        best = min(curve, key=lambda c: c["delta_chi2"])
        profiles[name] = {"curve": curve, "best": best, "best_at_scan_edge": best is curve[0] or best is curve[-1],
                          "interval_1sigma": interval(curve, 1.0), "interval_2sigma": interval(curve, 4.0)}

    # External bound on the early-transition variant: nucleosynthesis.
    lnk = math.log((1.0 + Z_BBN) / (1.0 + Z_TRANSITION))
    q_lo = -math.log(BBN_G_RATIO_2SIGMA[1]) / (2.0 * lnk)
    q_hi = -math.log(BBN_G_RATIO_2SIGMA[0]) / (2.0 * lnk)
    bbn_edges = {}
    for label, q in (("lower", q_lo), ("upper", q_hi)):
        r = fit("early_transition", q, data, start=start)
        bbn_edges[label] = {"q": q, "H0": EarlyTransition(r["h"], r["omega_b"], r["omega_c"], q).H0,
                            "delta_chi2": r["chi2"] - lcdm["chi2"]}
    z_star = LCDM(*start).z_star()
    external = {
        "bbn_q_range_2sigma": [q_lo, q_hi],
        "bbn_edges_cmb_plus_bao_fit": bbn_edges,
        "q_p1": {"G_rec_over_G0": g_ratio_early_transition(q_p1, z_star),
                 "G_bbn_over_G0": g_ratio_early_transition(q_p1, Z_BBN)},
        "ln_G_bbn_over_ln_G_rec": lnk / math.log((1.0 + z_star) / (1.0 + Z_TRANSITION)),
    }
    return {"tool": "joint_fit.py",
            "status": "DIAGNOSTIC — evidence for OPEN_PROBLEMS.md problems 1, 4, 5 and 8; not a registered prediction",
            "data": {"cmb": "Planck 2018 distance priors, Chen, Huang & Wang, JCAP 02 (2019) 028",
                     "bao": "DESI DR2 BAO, arXiv:2503.14738 v3, Table IV"},
            "q_tuned_to_p1": q_p1, "lcdm": dict(_cosmo(lcdm_model), chi2=lcdm["chi2"]),
            "validation": validation, "fixed_parameter_fits": fixed, "profiles": profiles,
            "external_bounds_early_transition": external}


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


def _fmt_q(q):
    return "open" if q is None else f"{q:+.2e}"


def render_markdown(res):
    v, fx, pr, ext = res["validation"], res["fixed_parameter_fits"], res["profiles"], res["external_bounds_early_transition"]
    et = fx["early_transition"]
    lines = [
        "# Joint CMB + BAO fit of the GSC readings",
        "",
        "<!-- GENERATED by analyses/joint_fit.py from analyses/joint_fit.json. Do not edit by hand. -->",
        "",
        "Diagnostic behind [OPEN_PROBLEMS.md](../OPEN_PROBLEMS.md) problems 1, 4, 5 and 8, not a registered prediction.",
        "Data: Planck 2018 CMB distance priors (Chen, Huang & Wang, JCAP 02 (2019) 028) and DESI DR2 BAO",
        "(arXiv:2503.14738 v3). Code: [joint_fit.py](joint_fit.py); numbers: [joint_fit.json](joint_fit.json).",
        "",
        "## Answer",
        "",
        f"The early-transition variant tuned to P1 (q = {res['q_tuned_to_p1']:.3g}) fits the CMB and BAO data as well as",
        f"ΛCDM: Δχ² = {et['delta_chi2']:+.2f}. Its BAO signature does not survive the refit. At fixed cosmological",
        f"parameters it shifts D_M/r_d by {et['signature'][3]['DM_over_rd_fixed_percent']:+.3f}% at z = {et['signature'][3]['z']};",
        f"once the parameters are refitted, the shift is {et['signature'][3]['DM_over_rd_refit_percent']:+.4f}%. The fit",
        f"absorbs the variant into H0, which moves from {res['lcdm']['H0']:.2f} to {et['H0']:.2f} km/s/Mpc.",
        "",
        "The same degeneracy makes the variant's parameter almost unconstrained by these data. Nucleosynthesis",
        f"constrains it instead: q between {ext['bbn_q_range_2sigma'][0]:+.2e} and {ext['bbn_q_range_2sigma'][1]:+.2e} at 2σ, which limits the",
        f"H0 it can reach in this fit to {ext['bbn_edges_cmb_plus_bao_fit']['upper']['H0']:.2f}–{ext['bbn_edges_cmb_plus_bao_fit']['lower']['H0']:.2f} km/s/Mpc. That is far short",
        "of the distance-ladder measurements, which lie several km/s/Mpc higher, so the variant does not address the",
        "Hubble tension either.",
        "",
        "## Validation",
        "",
        "| Check | This code | Reference |",
        "|---|---|---|",
        f"| R at the Planck 2018 parameters | {v['priors_at_planck2018_parameters']['R']:.5f} ({v['priors_at_planck2018_parameters']['R_sigma_offset']:+.2f}σ) | 1.7502 ± 0.0046 |",
        f"| l_A at the Planck 2018 parameters | {v['priors_at_planck2018_parameters']['l_A']:.3f} ({v['priors_at_planck2018_parameters']['l_A_sigma_offset']:+.2f}σ) | 301.471 ± 0.090 |",
        f"| z* (calibrated / printed formula) | {v['priors_at_planck2018_parameters']['z_star']:.2f} / {v['priors_at_planck2018_parameters']['z_star_printed_formula']:.2f} | Planck 2018: 1089.95 ± 0.27 |",
        f"| r_d at the Planck 2018 parameters | {v['rd_at_planck2018_parameters_Mpc']:.2f} Mpc | Aubourg et al. formula, CAMB convention |",
        f"| ΛCDM, DESI DR2 alone: Ω_m | {v['lcdm_bao_only']['Omega_m']:.4f} | DESI: 0.2975 ± 0.0086 |",
        f"| ΛCDM, CMB + DESI: Ω_m | {v['lcdm_cmb_plus_bao']['Omega_m']:.4f} | DESI with the full CMB likelihood: 0.3027 ± 0.0036 |",
        f"| ΛCDM, CMB + DESI: H0 | {v['lcdm_cmb_plus_bao']['H0']:.2f} | DESI with the full CMB likelihood: 68.17 ± 0.28 |",
        f"| ΛCDM χ² for {v['n_data']['cmb']} + {v['n_data']['bao']} data points | {v['lcdm_cmb_plus_bao']['chi2']:.2f} | refit from another start: Δχ² = {v['lcdm_refit_from_another_start_chi2_difference']:+.1e} |",
        "",
        "The CMB + DESI values differ from DESI's by about 1σ because compressed priors replace the full CMB likelihood.",
        "",
        "## Fits at the registered parameter values",
        "",
        "| Reading | q | Δχ² vs ΛCDM | χ² CMB / BAO | H0 | Ω_m |",
        "|---|---|---|---|---|---|",
    ]
    for name, label in (("early_transition", "Masses drift above z = 10 (tuned to P1)"),
                        ("powerlaw", "Masses drift at all times (canonical p)"),
                        ("history_b", "P8 r2 history (canonical p)")):
        f_ = fx[name]
        lines.append(f"| {label} | {f_['q']:.3g} | {f_['delta_chi2']:+.2f} | {f_['chi2_cmb']:.2f} / {f_['chi2_bao']:.2f} | {f_['H0']:.2f} | {f_['Omega_m']:.4f} |")
    lines += [f"| ΛCDM | 0 | 0 | — | {res['lcdm']['H0']:.2f} | {res['lcdm']['Omega_m']:.4f} |", "",
              "## What is left of P1's signature (early-transition variant)", "",
              "Percent difference from the ΛCDM best fit, at fixed cosmological parameters and after refitting them:", "",
              "| Tracer | z | D_M/r_d fixed | D_M/r_d refitted | D_H/r_d fixed | D_H/r_d refitted |",
              "|---|---|---|---|---|---|"]
    for s in et["signature"]:
        lines.append(f"| {s['tracer']} | {s['z']} | {s['DM_over_rd_fixed_percent']:+.3f}% | {s['DM_over_rd_refit_percent']:+.4f}% | "
                     f"{s['DH_over_rd_fixed_percent']:+.3f}% | {s['DH_over_rd_refit_percent']:+.4f}% |")
    lines += ["", "## How far each parameter can move", "",
              "Δχ² relative to ΛCDM, with the cosmological parameters refitted at every point.", ""]
    for name, label in (("early_transition", "Early transition"), ("powerlaw", "Power law"), ("history_b", "P8 r2 history")):
        p = pr[name]
        dchi = [c["delta_chi2"] for c in p["curve"]]
        if p["best_at_scan_edge"]:
            head = (f"**{label}.** The best fit lies at the edge of the scan (q = {p['best']['q']:+.2e}, "
                    f"Δχ² = {p['best']['delta_chi2']:+.2f}), so no interval is quoted; over the scan Δχ² runs from "
                    f"{min(dchi):+.2f} to {max(dchi):+.2f}.")
        else:
            head = (f"**{label}.** Best fit q = {p['best']['q']:+.2e} (Δχ² = {p['best']['delta_chi2']:+.2f}); "
                    f"1σ range {_fmt_q(p['interval_1sigma'][0])} to {_fmt_q(p['interval_1sigma'][1])}, "
                    f"2σ range {_fmt_q(p['interval_2sigma'][0])} to {_fmt_q(p['interval_2sigma'][1])}.")
        lines += [head, "", "| q | Δχ² | H0 | Ω_m |", "|---|---|---|---|"]
        lines += [f"| {c['q']:+.2e} | {c['delta_chi2']:+.2f} | {c['H0']:.2f} | {c['Omega_m']:.4f} |" for c in p["curve"]]
        lines.append("")
    lines += ["**Reading the scans.** The early-transition scan is nearly flat because the variant rescales every",
              "early-time length together, which a change of H0 undoes. The mild preferences of the power law for q > 0",
              "and of the P8 r2 history for p < 0 reflect the known tension of about 2.3σ between DESI DR2 BAO and the CMB",
              "within ΛCDM (arXiv:2503.14738), which any model that bends the late-time distance–redshift relation can",
              "absorb. They are not evidence for GSC, and the power law is excluded locally by lunar laser ranging",
              "([OPEN_PROBLEMS.md](../OPEN_PROBLEMS.md), problem 1). The P8 r2 history at the canonical p fits worse than ΛCDM.", "",
              "## What constrains the early-transition variant instead", "",
              f"- **Nucleosynthesis.** Alvey et al. 2020 (arXiv:1910.10730) give G_BBN/G0 = 0.99 +0.06/−0.05 at 2σ. For this",
              f"  variant that means q between {ext['bbn_q_range_2sigma'][0]:+.2e} and {ext['bbn_q_range_2sigma'][1]:+.2e}. At those edges the CMB + BAO fit",
              f"  gives H0 = {ext['bbn_edges_cmb_plus_bao_fit']['lower']['H0']:.2f} and {ext['bbn_edges_cmb_plus_bao_fit']['upper']['H0']:.2f} km/s/Mpc.",
              f"- **At the P1-tuned value** G in atomic units is {ext['q_p1']['G_rec_over_G0']:.4f} of today's at recombination and",
              f"  {ext['q_p1']['G_bbn_over_G0']:.4f} at nucleosynthesis. The variant ties the two: ln(G_BBN/G0) = {ext['ln_G_bbn_over_ln_G_rec']:.2f} × ln(G_rec/G0).",
              "- **The CMB damping tail and peak heights** respond to the expansion rate at recombination, which these",
              "  compressed priors do not capture. A full-spectrum fit is the test that remains.", "",
              "## Limits", "",
              "- Compressed CMB priors: passing here is necessary, not sufficient.",
              "- The recombination redshift is the Hu–Sugiyama fitting formula as printed by Chen, Huang & Wang, rescaled by",
              "  one constant so that it equals Planck 2018's z* at the Planck parameters; see the code for why.",
              "- One massive neutrino (0.06 eV) is counted as matter at all redshifts, as in the priors' own definitions.",
              ""]
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
            print("DIFFERS: joint_fit.md is not the rendering of joint_fit.json")
        ok = not problems and md_current
        print("joint fit reproduces its committed output" if ok else "joint fit does NOT reproduce its committed output")
        return 0 if ok else 1
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(res), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
