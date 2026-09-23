#!/usr/bin/env python3
"""a0_evolution.py — DIAGNOSTIC: does Milgrom's acceleration scale follow the expansion rate? (not a registered prediction).

Why this is here. OPEN_PROBLEMS.md, problem 11. Below an acceleration of about
a0 = 1.2e-10 m/s^2, galaxies stop following Newton's law applied to their visible
mass: that is where dark matter shows up. a0 is close to c H0 / 2π, the speed of
light times today's expansion rate. In GSC's reading H is the rate at which the
matter-based standards shrink, so if the coincidence is physical, the simplest
link ties a0 to that rate at every epoch, a0(z) = a0(0) H(z)/H0: three to four
times today's value at z = 2-2.5. THEORY.md §6.2 proposes an evolving MOND-like scale.

Data. RC100 (Nestor Shachar et al., ApJ 944, 78, 2023): 100 massive star-forming
disks at z = 0.6-2.5. For each, the authors' mass models give the circular
velocity V_c and the dark-matter fraction f_DM at the effective radius R_e
(data/rc100_table3.csv, transcribed from their Table 3). At R_e the observed
acceleration is g_obs = V_c^2 / R_e and the baryonic one g_bar = (1 - f_DM) g_obs.

Method. The radial acceleration relation (McGaugh, Lelli & Schombert, PRL 117,
201101, 2016), g_obs = g_bar / (1 - exp(-sqrt(g_bar / a0))), links the two for a
given a0. The fit maximises the likelihood of each galaxy's log residual, with the
errors of f_DM, V_c and R_e propagated and an intrinsic scatter left free, for
a0(z) = A E(z)^p, where E = H/H0 in flat ΛCDM (Ω_m = 0.315, the background GSC
reproduces). p = 1 is a0 proportional to H(z); p = 0 is a constant. The published
fits of Ciocan et al. (A&A 709, L16, 2026; 79 lower-mass galaxies at
z = 0.33-1.44) are compared through their quoted numbers only.

Deterministic, standard library only. Writes analyses/a0_evolution.json and
analyses/a0_evolution.md; `--check` recomputes and compares with tolerance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joint_fit as jf  # noqa: E402  (nelder_mead, _round, _compare)

REPO_ROOT = HERE.parent
DATA = REPO_ROOT / "data" / "rc100_table3.csv"
OUT_JSON = HERE / "a0_evolution.json"
OUT_MD = HERE / "a0_evolution.md"

KPC_M = 3.0856775814913673e19          # metres per kiloparsec
MPC_KM = 3.0856775814913673e19         # kilometres per megaparsec
C_M_S = 299792458.0
G_KPC = 4.30091e-6                     # G in kpc (km/s)^2 per solar mass
LN10 = math.log(10.0)
UNIT = 1e-10                           # a0 is quoted in units of 1e-10 m/s^2
OMEGA_M = 0.315                        # Planck 2018
H0_PLANCK = 67.4                       # km/s/Mpc, Planck 2018
A0_LOCAL = 1.20                        # McGaugh, Lelli & Schombert 2016: 1.20 +- 0.02 (stat) +- 0.24 (sys)
A0_COINCIDENCE = C_M_S * (H0_PLANCK / MPC_KM) / (2.0 * math.pi) / UNIT   # c H0 / 2π
Z_BINS = ((0.6, 1.2), (1.2, 1.9), (1.9, 2.6))   # z = 1.2 falls in the first bin, as in RC100's own split
SPLIT = 1.2                                      # RC100's two redshift bins: 0.6-1.2 and 1.2-2.5
NOISY_MOCKS = 12                                 # per true exponent; enough to show bias and scatter

# Ciocan et al., A&A 709, L16 (2026), arXiv:2604.22613: published numbers, 95% intervals as printed.
# Linear fits a0(z) = a0(0) + a1 z over 0.33 < z < 1.44, in 1e-10 m/s^2.
CIOCAN = {
    "reference": "Ciocan et al., A&A 709, L16 (2026), arXiv:2604.22613",
    "sample": "79 star-forming galaxies, 0.33 < z < 1.44, stellar masses 10^8.8-10^11 M_sun (MUSE Hubble Ultra Deep Field)",
    "z_range": [0.33, 1.44],
    "fits": {
        "dc14_halos": {"label": "dark-matter halos (DC14), main result", "a0_0": [1.00, 0.04, 0.04],
                       "a1": [1.59, 0.10, 0.10], "a0_z1": [2.38, 0.12, 0.10]},
        "preferred_halos": {"label": "best halo profile per galaxy", "a0_0": [1.05, 0.05, 0.05],
                            "a1": [1.63, 0.13, 0.12], "a0_z1": [2.61, 0.13, 0.09]},
        "mond_framework": {"label": "MOND fits to the data cubes", "a0_0": [1.03, 0.05, 0.05],
                           "a1": [1.20, 0.10, 0.10], "a0_z1": [2.19, 0.12, 0.10]},
    },
    "mond_per_galaxy_regression": {"a0_0": [1.11, 0.39, 0.51], "a1": [1.42, 0.94, 0.89]},
    "binned": "four equal-population redshift bins, a0 rising from about 1.99 to 2.71 (bin values not tabulated)",
}


def e_of_z(z, om=OMEGA_M):
    return math.sqrt(om * (1.0 + z) ** 3 + 1.0 - om)


def nu_rar(x):
    """McGaugh et al. (2016) form: g_obs = g_bar nu(g_bar / a0)."""
    return -1.0 / math.expm1(-math.sqrt(x))


def nu_simple(x):
    return 0.5 + math.sqrt(0.25 + 1.0 / x)


def nu_standard(x):
    return math.sqrt(0.5 + math.sqrt(0.25 + 1.0 / (x * x)))


NU = {"rar": nu_rar, "simple": nu_simple, "standard": nu_standard}


def ln_nu_and_slope(nu, x, h=1e-5):
    """ln nu(x) and d ln nu / d ln x (central difference in ln x)."""
    up, down = math.log(nu(x * math.exp(h))), math.log(nu(x * math.exp(-h)))
    return math.log(nu(x)), (up - down) / (2.0 * h)


def f_dm_predicted(g_obs, a0, nu=nu_rar):
    """Dark-matter fraction 1 - g_bar/g_obs that the relation predicts at a given g_obs (bisection in ln x)."""
    y = g_obs / a0
    lo, hi = math.log(y) + 2.0 * min(0.0, math.log(y)) - 8.0, math.log(y)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        x = math.exp(mid)
        if x * nu(x) < y:
            lo = mid
        else:
            hi = mid
    return 1.0 - math.exp(0.5 * (lo + hi)) / y


def a0_closed_form(g_obs, f_dm):
    """The a0 at which the McGaugh relation gives exactly f_dm at g_obs: a0 = g_bar / (ln f_dm)^2."""
    return (1.0 - f_dm) * g_obs / math.log(f_dm) ** 2


def load_galaxies(path=DATA):
    galaxies = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            v, sv = float(row["vc_kms"]), float(row["vc_err"])
            r, sr = float(row["re_kpc"]), float(row["re_err"])
            galaxies.append({
                "id": int(row["id"]), "galaxy": row["galaxy"], "z": float(row["z"]),
                "f": float(row["fdm"]), "sf": float(row["fdm_err"]), "log_mbar": float(row["log_mbar"]),
                "v": v, "r": r, "sr": sr,
                "g_obs": (v * 1e3) ** 2 / (r * KPC_M),
                "s_log_gobs": math.hypot(2.0 * sv / v, sr / r) / LN10,
            })
    return galaxies


def slopes_at(galaxies, a0_of_z, nu=nu_rar):
    """d ln nu / d ln x for each galaxy at the given a0(z): the weight of its measurement errors."""
    return [ln_nu_and_slope(nu, (1.0 - g["f"]) * g["g_obs"] / (a0_of_z(g["z"]) * UNIT))[1] for g in galaxies]


def m2lnl(galaxies, a0_of_z, sigma_int, slopes, nu=nu_rar):
    """-2 ln L (without the 2π constant) of the log residuals log g_obs - log[g_bar nu(g_bar/a0)], in dex.

    The measurement errors enter through the slope of the relation, held fixed at `slopes` (effective
    variance), so that the variances do not depend on the parameters being fitted; fit_iterated() puts
    the slopes at the best fit.
    """
    total = 0.0
    for g, s in zip(galaxies, slopes):
        x = (1.0 - g["f"]) * g["g_obs"] / (a0_of_z(g["z"]) * UNIT)
        r = (-math.log(1.0 - g["f"]) - math.log(nu(x))) / LN10
        var = (((1.0 + s) * g["sf"] / ((1.0 - g["f"]) * LN10)) ** 2 + (s * g["s_log_gobs"]) ** 2 + sigma_int ** 2)
        total += r * r / var + math.log(var)
    return total


def fit(galaxies, slopes, *, ln_a=None, p=None, sigma_int=None, nu=nu_rar, om=OMEGA_M):
    """Maximum likelihood for a0(z) = A E(z)^p; any of ln A, p and the intrinsic scatter may be held fixed."""
    free = [k for k, v in (("ln_a", ln_a), ("p", p), ("sigma_int", sigma_int)) if v is None]
    start = {"ln_a": math.log(A0_LOCAL), "p": 0.0, "sigma_int": 0.05}
    step = {"ln_a": 0.3, "p": 0.5, "sigma_int": 0.05}

    def unpack(x):
        d = dict(zip(free, x))
        return (d.get("ln_a", ln_a), d.get("p", p), abs(d["sigma_int"]) if "sigma_int" in d else sigma_int)

    def objective(x):
        la, pp, si = unpack(x)
        a = math.exp(la)
        return m2lnl(galaxies, lambda z: a * e_of_z(z, om) ** pp, si, slopes, nu)

    if free:
        x, val = jf.nelder_mead(objective, [start[k] for k in free], [step[k] for k in free], tol=1e-10, max_iter=4000)
        x, val = jf.nelder_mead(objective, x, [step[k] / 4.0 for k in free], tol=1e-10, max_iter=4000)
    else:
        x, val = [], objective([])
    la, pp, si = unpack(x)
    return {"A": math.exp(la), "p": pp, "sigma_int_dex": si, "m2lnL": val}


def fit_iterated(galaxies, *, nu=nu_rar, om=OMEGA_M, **fixed):
    """fit() with the error weights moved to the best fit until they stop changing; returns (best, slopes)."""
    slopes = slopes_at(galaxies, lambda z: A0_LOCAL, nu)
    for _ in range(50):
        best = fit(galaxies, slopes, nu=nu, om=om, **fixed)
        new = slopes_at(galaxies, lambda z, b=best: b["A"] * e_of_z(z, om) ** b["p"], nu)
        done = max(abs(a - b) for a, b in zip(new, slopes)) < 1e-10
        slopes = new
        if done:
            break
    return fit(galaxies, slopes, nu=nu, om=om, **fixed), slopes


def profile_interval(profile, best_param, best_val, lo, hi, level=1.0):
    """Where the profile rises by `level` above its minimum on each side (bisection); None if not bracketed."""
    def root(inner, outer):
        f_outer = profile(outer) - best_val - level
        if f_outer <= 0.0:
            return None
        for _ in range(30):
            mid = 0.5 * (inner + outer)
            if profile(mid) - best_val - level > 0.0:
                outer = mid
            else:
                inner = mid
        return 0.5 * (inner + outer)
    return root(best_param, lo), root(best_param, hi)


def power_law_summary(galaxies, nu=nu_rar, sigma_int=None, om=OMEGA_M):
    """Constant, H-shaped and free-exponent fits, with the profile interval of p and the distance of p = 1.

    All models share the error weights of the free-exponent best fit, so that their likelihoods differ only
    through the residuals and the intrinsic scatter.
    """
    kw = {"nu": nu, "sigma_int": sigma_int, "om": om}
    best, slopes = fit_iterated(galaxies, **kw)
    const = fit(galaxies, slopes, p=0.0, **kw)
    tracks_h = fit(galaxies, slopes, p=1.0, **kw)
    prof = lambda pp: fit(galaxies, slopes, p=pp, **kw)["m2lnL"]  # noqa: E731
    lo, hi = profile_interval(prof, best["p"], best["m2lnL"], best["p"] - 3.0, best["p"] + 3.0)
    d1 = tracks_h["m2lnL"] - best["m2lnL"]
    d0 = const["m2lnL"] - best["m2lnL"]
    return {
        "n": len(galaxies),
        "constant": {"A": const["A"], "sigma_int_dex": const["sigma_int_dex"]},
        "tracks_H": {"A": tracks_h["A"], "sigma_int_dex": tracks_h["sigma_int_dex"]},
        "delta_m2lnL_tracks_H_minus_constant": tracks_h["m2lnL"] - const["m2lnL"],
        "p_best": best["p"], "p_interval_1sigma": [lo, hi], "A_at_p_best": best["A"],
        "p1_sigma": math.sqrt(max(d1, 0.0)), "p0_sigma": math.sqrt(max(d0, 0.0)),
    }


def paper_statistics(galaxies):
    """Statistics quoted in the RC100 text, recomputed from the transcribed table."""
    low = [g["f"] for g in galaxies if g["z"] <= SPLIT]
    high = [g["f"] for g in galaxies if g["z"] > SPLIT]
    ks = sorted((1.0 - g["f"]) * g["v"] ** 2 * g["r"] / (G_KPC * 10.0 ** g["log_mbar"]) for g in galaxies)
    outliers = [g["id"] for g in galaxies
                if not 0.15 < (1.0 - g["f"]) * g["v"] ** 2 * g["r"] / (G_KPC * 10.0 ** g["log_mbar"]) < 1.2]
    return {
        "n_galaxies": len(galaxies),
        "ids_in_order_and_redshift_sorted": [g["id"] for g in galaxies] == list(range(1, len(galaxies) + 1))
        and [g["z"] for g in galaxies] == sorted(g["z"] for g in galaxies),
        "median_fdm_z_0.6_1.2": {"table": statistics.median(low), "paper": 0.38},
        "median_fdm_z_1.2_2.5": {"table": statistics.median(high), "paper": 0.27},
        "spread_fdm_z_0.6_1.2": {"table": statistics.pstdev(low), "paper": 0.23},
        "spread_fdm_z_1.2_2.5": {"table": statistics.pstdev(high), "paper": 0.18},
        "share_below_maximal_disk_z_0.6_1.2": {"table": sum(f < 0.28 for f in low) / len(low), "paper": "roughly 33%"},
        "share_below_maximal_disk_z_1.2_2.5": {"table": sum(f < 0.28 for f in high) / len(high), "paper": "half"},
        "median_Re_kpc": {"table": statistics.median(g["r"] for g in galaxies), "paper": 5.5},
        "mass_consistency_Vbar2_Re_over_G_Mbar": {
            "median": statistics.median(ks), "p10": ks[len(ks) // 10], "p90": ks[len(ks) - len(ks) // 10 - 1],
            "outside_0.15_to_1.2": outliers},
    }


def validate(galaxies):
    """Implementation checks: the closed form inverts the relation, and noise-free mocks are recovered."""
    inversion = []
    for x in (0.1, 1.0, 10.0):
        a0 = A0_LOCAL * UNIT
        g_bar = x * a0
        g_obs = g_bar * nu_rar(x)
        f = 1.0 - g_bar / g_obs
        inversion.append({"g_bar_over_a0": x, "relative_error_closed_form": a0_closed_form(g_obs, f) / a0 - 1.0,
                          "relative_error_bisection": f_dm_predicted(g_obs, a0) / f - 1.0})
    mocks = {}
    for p_true in (0.0, 1.0):
        mock = [dict(g, f=f_dm_predicted(g["g_obs"], A0_LOCAL * UNIT * e_of_z(g["z"]) ** p_true)) for g in galaxies]
        best, _ = fit_iterated(mock)
        mocks[f"p_true_{p_true:g}"] = {"p_recovered": best["p"], "A_recovered": best["A"],
                                       "sigma_int_recovered": best["sigma_int_dex"]}
    return {"inversion": inversion, "noise_free_mock_recovery": mocks}


def noisy_mocks(galaxies, n=NOISY_MOCKS, seed=20260923):
    """Mocks with the table's errors drawn as noise (f_DM kept inside [0.005, 0.95]): bias and scatter of p."""
    rng = random.Random(seed)
    out = {}
    for p_true in (0.0, 1.0):
        ps, far1, far0 = [], [], []
        for _ in range(n):
            mock = []
            for g in galaxies:
                f_true = f_dm_predicted(g["g_obs"], A0_LOCAL * UNIT * e_of_z(g["z"]) ** p_true)
                mock.append(dict(g, f=min(0.95, max(0.005, f_true + rng.gauss(0.0, g["sf"]))),
                                 g_obs=g["g_obs"] * 10.0 ** rng.gauss(0.0, g["s_log_gobs"])))
            s = power_law_summary(mock)
            ps.append(s["p_best"])
            far1.append(s["p1_sigma"])
            far0.append(s["p0_sigma"])
        out[f"p_true_{p_true:g}"] = {"n": n, "mean_p": statistics.fmean(ps), "scatter_p": statistics.pstdev(ps),
                                     "median_sigma_from_p1": statistics.median(far1),
                                     "median_sigma_from_p0": statistics.median(far0)}
    return out


def binned(galaxies):
    out = []
    for i, (lo, hi) in enumerate(Z_BINS):
        sel = [g for g in galaxies if (lo <= g["z"] if i == 0 else lo < g["z"]) and g["z"] <= hi]
        best, slopes = fit_iterated(sel, p=0.0)
        prof = lambda la: fit(sel, slopes, ln_a=la, p=0.0)["m2lnL"]  # noqa: E731
        la = math.log(best["A"])
        a_lo, a_hi = profile_interval(prof, la, best["m2lnL"], la - 2.0, la + 2.0)
        z_med = statistics.median(g["z"] for g in sel)
        closed = [a0_closed_form(g["g_obs"], g["f"]) / UNIT for g in sel]
        out.append({
            "z_range": [lo, hi], "n": len(sel), "z_median": z_med,
            "a0": best["A"], "a0_interval_1sigma": [math.exp(a_lo), math.exp(a_hi)],
            "sigma_int_dex": best["sigma_int_dex"],
            "median_single_galaxy_a0": statistics.median(closed),
            "median_g_obs": statistics.median(g["g_obs"] for g in sel) / UNIT,
            "tracks_H_local_normalisation": A0_LOCAL * e_of_z(z_med),
            "tracks_H_coincidence_normalisation": A0_COINCIDENCE * e_of_z(z_med),
            "median_fdm_observed": statistics.median(g["f"] for g in sel),
            "median_fdm_if_tracks_H_local": statistics.median(
                f_dm_predicted(g["g_obs"], A0_LOCAL * UNIT * e_of_z(g["z"])) for g in sel),
        })
    return out


def zero_parameter_normalisations(galaxies, best_m2lnl, slopes):
    """a0 fixed to a local value, constant or scaled by E(z); intrinsic scatter free."""
    out = {}
    for name, a in (("local_1.20", A0_LOCAL), ("coincidence_cH0_over_2pi", A0_COINCIDENCE)):
        for p in (0.0, 1.0):
            r = fit(galaxies, slopes, ln_a=math.log(a), p=p)
            out[f"{name}_{'constant' if p == 0.0 else 'tracks_H'}"] = {
                "a0_today": a, "p": p, "delta_m2lnL_vs_best": r["m2lnL"] - best_m2lnl}
    return out


def ciocan_comparison(rc100_bins):
    """Where the published linear fits sit relative to a0 = 1.2 E(z), and their effective exponent of E(z)."""
    z0, z1 = CIOCAN["z_range"]
    out = {}
    for key, fit_ in CIOCAN["fits"].items():
        a, b = fit_["a0_0"][0], fit_["a1"][0]
        line = lambda z: a + b * z  # noqa: E731
        zs = (z0, 0.5 * (z0 + z1), z1)
        ratios = [line(z) / (A0_LOCAL * e_of_z(z)) for z in zs]
        out[key] = {
            "label": fit_["label"],
            "ratio_to_1.2E": [{"z": z, "published_line": line(z), "tracks_H_local": A0_LOCAL * e_of_z(z),
                               "ratio": q} for z, q in zip(zs, ratios)],
            "max_abs_deviation_from_1.2E": max(abs(q - 1.0) for q in ratios),
            "effective_p": math.log(line(z1) / line(z0)) / math.log(e_of_z(z1) / e_of_z(z0)),
        }
    for name, b in (("overlap_with_rc100_lowest_bin", rc100_bins[0]),
                    ("extrapolated_to_rc100_highest_bin", rc100_bins[-1])):
        out[name] = {
            "z": b["z_median"], "rc100_a0": b["a0"], "rc100_interval_1sigma": b["a0_interval_1sigma"],
            "ciocan_lines_at_z": {k: v["a0_0"][0] + v["a1"][0] * b["z_median"] for k, v in CIOCAN["fits"].items()},
        }
    return out


def analyse():
    galaxies = load_galaxies()
    base = power_law_summary(galaxies)
    best_all, slopes_all = fit_iterated(galaxies)
    variants = {"baseline: McGaugh relation, scatter free": base}
    variants["simple interpolating function"] = power_law_summary(galaxies, nu=nu_simple)
    variants["standard interpolating function"] = power_law_summary(galaxies, nu=nu_standard)
    variants["intrinsic scatter fixed at 0.11 dex (SPARC)"] = power_law_summary(galaxies, sigma_int=0.11)
    variants["intrinsic scatter fixed at 0.17 dex (Ciocan et al.)"] = power_law_summary(galaxies, sigma_int=0.17)
    variants["without f_DM <= 0.05 and the dispersion-dominated #83"] = power_law_summary(
        [g for g in galaxies if g["f"] > 0.05 and g["id"] != 83])
    variants["only 0.1 <= f_DM <= 0.9"] = power_law_summary([g for g in galaxies if 0.1 <= g["f"] <= 0.9])
    variants["only sigma(f_DM) <= 0.13"] = power_law_summary([g for g in galaxies if g["sf"] <= 0.13])
    variants["Omega_m = 0.30"] = power_law_summary(galaxies, om=0.30)
    bins = binned(galaxies)
    return {
        "question": "Does a0 follow the expansion rate, a0(z) = a0(0) H(z)/H0?",
        "data": {"file": "data/rc100_table3.csv",
                 "source": "Nestor Shachar et al., ApJ 944, 78 (2023), arXiv:2209.12199, Table 3"},
        "constants": {"Omega_m": OMEGA_M, "a0_local": A0_LOCAL, "a0_coincidence_cH0_over_2pi": A0_COINCIDENCE,
                      "H0_for_coincidence": H0_PLANCK},
        "transcription_checks": paper_statistics(galaxies),
        "validation": dict(validate(galaxies), noisy_mocks=noisy_mocks(galaxies)),
        "all_galaxies": base,
        "zero_parameter_models": zero_parameter_normalisations(galaxies, best_all["m2lnL"], slopes_all),
        "bins": bins,
        "robustness": variants,
        "ciocan_2026": {"published": CIOCAN, "comparison": ciocan_comparison(bins)},
    }


def _f(x, d=2):
    return "—" if x is None else f"{x:.{d}f}"


def render_markdown(res):
    base, bins, rob = res["all_galaxies"], res["bins"], res["robustness"]
    zp, tc, val = res["zero_parameter_models"], res["transcription_checks"], res["validation"]
    cc = res["ciocan_2026"]["comparison"]
    hi_bin = bins[-1]
    lines = [
        "# Does Milgrom's acceleration scale follow the expansion rate?",
        "",
        "<!-- GENERATED by analyses/a0_evolution.py from analyses/a0_evolution.json. Do not edit by hand. -->",
        "",
        "Diagnostic behind [OPEN_PROBLEMS.md](../OPEN_PROBLEMS.md) problem 11, not a registered prediction.",
        "Data: the 100 rotation curves of RC100 (Nestor Shachar et al., ApJ 944, 78, 2023) at z = 0.6–2.5,",
        "[data/rc100_table3.csv](../data/rc100_table3.csv). Code: [a0_evolution.py](a0_evolution.py); numbers:",
        "[a0_evolution.json](a0_evolution.json). Accelerations in units of 10⁻¹⁰ m/s².",
        "",
        "## Answer",
        "",
        f"Not in these data. Fitting a0(z) = A E(z)^p to the 100 galaxies gives p = {base['p_best']:+.2f} "
        f"(1σ: {_f(base['p_interval_1sigma'][0])} to {_f(base['p_interval_1sigma'][1])}). A scale that follows the",
        f"expansion rate, p = 1, is {base['p1_sigma']:.1f}σ away; a constant, p = 0, is {base['p0_sigma']:.1f}σ away. "
        f"With the normalisation free,",
        f"the H(z) shape fits worse than a constant by Δ(−2 ln L) = {base['delta_m2lnL_tracks_H_minus_constant']:+.1f}. "
        f"A constant fits with a0 = {base['constant']['A']:.2f},",
        "the value measured in nearby galaxies (1.20 ± 0.24).",
        "",
        f"At z ≈ {hi_bin['z_median']:.2f} the {hi_bin['n']} galaxies give a0 = {hi_bin['a0']:.2f} "
        f"(1σ: {hi_bin['a0_interval_1sigma'][0]:.2f}–{hi_bin['a0_interval_1sigma'][1]:.2f}), where a scale following H(z) "
        f"would be {hi_bin['tracks_H_local_normalisation']:.2f}",
        f"(from today's 1.20) or {hi_bin['tracks_H_coincidence_normalisation']:.2f} (from c H0 / 2π). "
        "From six of these galaxies, Milgrom",
        "(arXiv:1703.06110) concluded that a value about four times today's at z ≈ 2 is all but excluded.",
        "",
        "## Redshift bins",
        "",
        "| z range | Galaxies | Median z | a0 (fit) | 1σ | Median of single-galaxy a0 | H(z)-scaled, from 1.20 | from c H0/2π |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for b in bins:
        lines.append(f"| {b['z_range'][0]}–{b['z_range'][1]} | {b['n']} | {b['z_median']:.2f} | {b['a0']:.2f} | "
                     f"{b['a0_interval_1sigma'][0]:.2f}–{b['a0_interval_1sigma'][1]:.2f} | {b['median_single_galaxy_a0']:.2f} | "
                     f"{b['tracks_H_local_normalisation']:.2f} | {b['tracks_H_coincidence_normalisation']:.2f} |")
    lines += [
        "",
        "The single-galaxy value is the a0 at which the relation gives exactly the galaxy's dark-matter fraction,",
        "a0 = g_bar / (ln f_DM)²; its median ignores the error bars, which the fit uses.",
        "",
        "## Models with no free normalisation",
        "",
        "Δ(−2 ln L) relative to the best power law; the intrinsic scatter is free in every case.",
        "",
        "| a0 today | Constant | Follows H(z) |",
        "|---|---|---|",
        f"| 1.20 (nearby galaxies) | {zp['local_1.20_constant']['delta_m2lnL_vs_best']:+.1f} | "
        f"{zp['local_1.20_tracks_H']['delta_m2lnL_vs_best']:+.1f} |",
        f"| {res['constants']['a0_coincidence_cH0_over_2pi']:.3f} (c H0 / 2π, H0 = {res['constants']['H0_for_coincidence']}) | "
        f"{zp['coincidence_cH0_over_2pi_constant']['delta_m2lnL_vs_best']:+.1f} | "
        f"{zp['coincidence_cH0_over_2pi_tracks_H']['delta_m2lnL_vs_best']:+.1f} |",
        "",
        "## Robustness",
        "",
        "| Variant | Galaxies | Constant a0 | A for H(z) shape | Δ(−2 ln L), H(z) − constant | p (1σ) | p = 1 excluded at |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, v in rob.items():
        lo, hi = v["p_interval_1sigma"]
        lines.append(f"| {name} | {v['n']} | {v['constant']['A']:.2f} | {v['tracks_H']['A']:.2f} | "
                     f"{v['delta_m2lnL_tracks_H_minus_constant']:+.1f} | {v['p_best']:+.2f} ({_f(lo)} to {_f(hi)}) | "
                     f"{v['p1_sigma']:.1f}σ |")
    lines += [
        "",
        "The normalisation depends on the interpolating function, as is known; the trend with redshift does not.",
        "The weakest case is an intrinsic scatter fixed at the large value Ciocan et al. find at z ≈ 1.",
        "",
        "## The one sample in which a0 rises",
        "",
        "Ciocan et al. (A&A 709, L16, 2026) measure the relation in 79 lower-mass galaxies at z = 0.33–1.44 and find",
        "a0 rising with redshift. Their published linear fits, compared with a0 = 1.20 E(z) (numbers as printed;",
        "95% intervals):",
        "",
        "| Their fit | a0(0) | a1 | Line / 1.20 E(z) at z = 0.33, 0.885, 1.44 | Effective p over their range |",
        "|---|---|---|---|---|",
    ]
    pub = res["ciocan_2026"]["published"]["fits"]
    for key in ("dc14_halos", "preferred_halos", "mond_framework"):
        c = cc[key]
        lines.append(f"| {c['label']} | {pub[key]['a0_0'][0]:.2f} ± {pub[key]['a0_0'][1]:.2f} | "
                     f"{pub[key]['a1'][0]:.2f} ± {pub[key]['a1'][1]:.2f} | "
                     + ", ".join(f"{r['ratio']:.2f}" for r in c["ratio_to_1.2E"]) + f" | {c['effective_p']:.2f} |")
    ov, ex = cc["overlap_with_rc100_lowest_bin"], cc["extrapolated_to_rc100_highest_bin"]
    lines += [
        "",
        f"In their MOND fits the rise follows H(z) almost exactly (effective p = {cc['mond_framework']['effective_p']:.2f}, "
        f"within {100 * cc['mond_framework']['max_abs_deviation_from_1.2E']:.0f}% of 1.20 E(z));",
        "with dark-matter halos it is somewhat faster, which is what the authors report. The two samples disagree",
        f"where they overlap: at z = {ov['z']:.2f} RC100 gives {ov['rc100_a0']:.2f} "
        f"({ov['rc100_interval_1sigma'][0]:.2f}–{ov['rc100_interval_1sigma'][1]:.2f}), their three lines give "
        + ", ".join(f"{v:.2f}" for v in ov["ciocan_lines_at_z"].values()) + ".",
        f"Continued to z = {ex['z']:.2f}, the lines give "
        + ", ".join(f"{v:.2f}" for v in ex["ciocan_lines_at_z"].values())
        + f", where RC100 gives {ex['rc100_a0']:.2f}. No single a0(z), constant or",
        "evolving, describes both samples at face value. A rise of about their size also appears in a ΛCDM",
        "simulation (Mayer et al., arXiv:2206.04333: a factor of about 3 from z = 0 to 2), so a rising a0 would not by",
        "itself point to new physics.",
        "",
        "## Checks",
        "",
        "Transcription (the statistics the RC100 text quotes for the dark-matter fractions and sizes, recomputed from",
        "the table):",
        "",
        "| Statistic | Table | Paper |",
        "|---|---|---|",
    ]
    labels = {"median_fdm_z_0.6_1.2": "Median f_DM, z = 0.6–1.2", "median_fdm_z_1.2_2.5": "Median f_DM, z = 1.2–2.5",
              "spread_fdm_z_0.6_1.2": "Spread of f_DM, z = 0.6–1.2", "spread_fdm_z_1.2_2.5": "Spread of f_DM, z = 1.2–2.5",
              "share_below_maximal_disk_z_0.6_1.2": "Share with f_DM < 0.28, z = 0.6–1.2",
              "share_below_maximal_disk_z_1.2_2.5": "Share with f_DM < 0.28, z = 1.2–2.5",
              "median_Re_kpc": "Median R_e (kpc)"}
    for key, label in labels.items():
        t = tc[key]
        lines.append(f"| {label} | {t['table']:.3f} | {t['paper']} |")
    mc = tc["mass_consistency_Vbar2_Re_over_G_Mbar"]
    lines += [
        "",
        f"Mass consistency, a check across four columns: V_bar² R_e / (G M_bar) has median {mc['median']:.2f} "
        f"(10–90%: {mc['p10']:.2f}–{mc['p90']:.2f}).",
        "The one galaxy outside 0.15–1.2 is "
        + ", ".join(f"#{i}" for i in mc["outside_0.15_to_1.2"])
        + ", bulge-dominated with a velocity dispersion of 100 km/s.",
        "",
        "Implementation: the closed form inverts the relation to "
        + f"{max(abs(r['relative_error_closed_form']) for r in val['inversion']):.0e}; noise-free mocks built from the",
        "table's own accelerations and errors return p = "
        + ", ".join(f"{m['p_recovered']:.4f}" for m in val["noise_free_mock_recovery"].values())
        + " for p = 0, 1. Mocks with the table's errors drawn as noise",
        "(" + "; ".join(f"p = {k.split('_')[-1]}: mean p = {m['mean_p']:+.2f}, scatter {m['scatter_p']:.2f}, "
                         f"{m['n']} mocks" for k, m in val["noisy_mocks"].items())
        + ") show no bias beyond the",
        "scatter, and a scatter close to the quoted 1σ interval. A sample like this one separates p = 0 from p = 1 by",
        "a median of " + " and ".join(f"{m['median_sigma_from_p1' if k.endswith('_0') else 'median_sigma_from_p0']:.1f}σ"
                                       for k, m in val["noisy_mocks"].items())
        + " (mocks made with p = 0 and p = 1).",
        "",
        "## Limits",
        "",
        "- The dark-matter fractions come from the authors' mass models, which assume dark-matter halos; a MOND",
        "  reanalysis of the rotation curves could shift them. Milgrom's reading of six of these galaxies agrees.",
        "- The errors of f_DM, V_c and R_e are treated as independent; the table gives no correlations.",
        "- Beam smearing and pressure-support corrections grow with redshift and could bias the trend. To allow",
        f"  a0 ∝ H(z) they would have to raise the median dark-matter fraction at z ≈ {hi_bin['z_median']:.1f} "
        f"from {hi_bin['median_fdm_observed']:.2f} to {hi_bin['median_fdm_if_tracks_H_local']:.2f}.",
        "- RC100 and Ciocan et al. select different galaxies and use different mass models; published summary numbers,",
        "  not their data, are used for the latter.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="recompute and compare with the committed JSON")
    args = ap.parse_args(argv)
    res = jf._round(analyse())
    if args.check:
        committed = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        problems = jf._compare(res, committed)
        md_current = OUT_MD.read_text(encoding="utf-8") == render_markdown(committed)
        for p in problems[:10]:
            print("DIFFERS", p)
        if not md_current:
            print("DIFFERS: a0_evolution.md is not the rendering of a0_evolution.json")
        ok = not problems and md_current
        print("a0-evolution analysis reproduces its committed output" if ok
              else "a0-evolution analysis does NOT reproduce its committed output")
        return 0 if ok else 1
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(res), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
