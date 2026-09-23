#!/usr/bin/env python3
"""emergent_gravity.py — DIAGNOSTIC: is "dark matter" gravity's response to dark energy? Verlinde's formula on RC100.

Why this is here. OPEN_PROBLEMS.md, problem 11. Friction is not a new force but
electromagnetism seen in bulk; by the same logic, the extra gravity in galaxies
could be gravity's collective response to the dark energy that fills space
rather than a new substance. Verlinde's emergent gravity (SciPost Phys. 2, 016,
2017, arXiv:1611.02269) makes that precise: baryons displace the entropy of the
dark-energy vacuum, and the response is an apparent dark matter

    M_D(r)^2 = (a_M r^2 / G) d(M_B(r) r)/dr,     a_M = c H0 / 6,

derived for a de Sitter universe (his eq. 7.40). With M_B(r) = r V_bar(r)^2 / G,
the observed acceleration at radius r is

    g_obs = g_bar + sqrt(k a_M g_bar),    k = 2 + d ln V_bar^2 / d ln r,

so k = 1 for a point mass, where the formula reduces to MOND-like form with
a0 = a_M. Nothing is fitted: both the shape and the scale are fixed.

Test. RC100 (Nestor Shachar et al., ApJ 944, 78, 2023; data/rc100_table3.csv)
gives, for 100 disks at z = 0.6-2.5, g_obs and g_bar at the effective radius and
the bulge mass. V_bar's slope at R_e follows the authors' mass model: an
exponential disc of effective radius R_e and a spherical Sérsic n = 4 bulge of
effective radius 1 kpc. Verlinde's theory is derived for a universe dominated
by dark energy; at z = 0.6-2.5 it has to be extended, and two extensions are
compared, both with no free parameter:

    H = H(z), the expansion rate at that epoch;
    H = H_DE(z) = H0 sqrt(Omega_DE rho_DE(z)/rho_DE(0)), its dark-energy part,
        with DESI DR2's dark-energy histories (the form registered as P15).

The likelihood is that of analyses/a0_evolution.py: the log residual of each
galaxy, with the errors of f_DM, V_c and R_e propagated and an intrinsic
scatter free.

Deterministic, standard library only. Writes analyses/emergent_gravity.json and
analyses/emergent_gravity.md; `--check` recomputes and compares with tolerance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joint_fit as jf  # noqa: E402  (nelder_mead, _round, _compare)
import a0_evolution as a0e  # noqa: E402  (galaxies, e_of_z, rho_de_ratio, UNIT, LN10)
import a0_high_z as hz  # noqa: E402  (v2_sersic, v2_exponential_disc)

REPO_ROOT = HERE.parent
OUT_JSON = HERE / "emergent_gravity.json"
OUT_MD = HERE / "emergent_gravity.md"

C_KM_S = 299792.458
MPC_M = 3.0856775814913673e22
R_EFF_BULGE = 1.0          # kpc, RC100's fixed bulge effective radius (Sérsic n = 4)
N_BULGE = 4.0
H0_PLANCK, OMEGA_M_PLANCK = 67.4, 0.315
# DESI DR2 Results II (arXiv:2503.14738 v3, Table V and eqs. 25-28): (w0, wa, Omega_m, H0) per combination.
DESI_DR2 = {
    "DESI+CMB": (-0.42, -1.75, 0.353, 63.6),
    "DESI+CMB+Pantheon+": (-0.838, -0.62, 0.3114, 67.51),
    "DESI+CMB+Union3": (-0.667, -1.09, 0.3275, 65.91),
    "DESI+CMB+DESY5": (-0.752, -0.86, 0.3191, 66.74),
}


def a_verlinde(h0_km_s_mpc):
    """c H / 6 in units of 1e-10 m/s^2."""
    return C_KM_S * 1e3 * (h0_km_s_mpc * 1e3 / MPC_M) / 6.0 / a0e.UNIT


def load_galaxies():
    """a0_evolution's galaxies, with the bulge mass and Verlinde's slope factor k at R_e."""
    galaxies = a0e.load_galaxies()
    with open(a0e.DATA, newline="", encoding="utf-8") as fh:
        bulge = {int(r["id"]): float(r["log_mbulge"]) for r in csv.DictReader(fh)}
    for g in galaxies:
        m_bar, m_bul = 10.0 ** g["log_mbar"], 10.0 ** bulge[g["id"]]
        g["bt"] = m_bul / m_bar
        g["k"] = slope_factor(g["r"], m_bar - m_bul, m_bul)
    return galaxies


def v2_baryons(r, m_disc, m_bulge, r_eff):
    return (hz.v2_exponential_disc(r, m_disc, r_eff / 1.678) if m_disc > 0 else 0.0) + \
        hz.v2_sersic(r, m_bulge, R_EFF_BULGE, N_BULGE)


def slope_factor(r_eff, m_disc, m_bulge, h=1e-4):
    """k = 2 + d ln V_bar^2 / d ln r at R_e (central difference in ln r)."""
    up = v2_baryons(r_eff * math.exp(h), m_disc, m_bulge, r_eff)
    down = v2_baryons(r_eff * math.exp(-h), m_disc, m_bulge, r_eff)
    return 2.0 + (math.log(up) - math.log(down)) / (2.0 * h)


def nu_verlinde(x, k):
    """g_obs / g_bar = 1 + sqrt(k / x), x = g_bar / a_M."""
    return 1.0 + math.sqrt(k / x)


def m2lnl(galaxies, a_of_z, sigma_int, point_mass=False):
    """-2 ln L of the log residuals, with the error weights evaluated at the model itself."""
    total = 0.0
    for g in galaxies:
        k = 1.0 if point_mass else g["k"]
        x = (1.0 - g["f"]) * g["g_obs"] / (a_of_z(g["z"]) * a0e.UNIT)
        h = 1e-5
        slope = (math.log(nu_verlinde(x * math.exp(h), k)) - math.log(nu_verlinde(x * math.exp(-h), k))) / (2 * h)
        r = (-math.log(1.0 - g["f"]) - math.log(nu_verlinde(x, k))) / a0e.LN10
        var = (((1.0 + slope) * g["sf"] / ((1.0 - g["f"]) * a0e.LN10)) ** 2 + (slope * g["s_log_gobs"]) ** 2
               + sigma_int ** 2)
        total += r * r / var + math.log(var)
    return total


def best_scatter(galaxies, a_of_z, point_mass=False):
    """Minimum over the intrinsic scatter only (golden section on [0, 0.6] dex)."""
    lo, hi = 0.0, 0.6
    gr = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = hi - gr * (hi - lo), lo + gr * (hi - lo)
    fc, fd = m2lnl(galaxies, a_of_z, c, point_mass), m2lnl(galaxies, a_of_z, d, point_mass)
    for _ in range(80):
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - gr * (hi - lo)
            fc = m2lnl(galaxies, a_of_z, c, point_mass)
        else:
            lo, c, fc = c, d, fd
            d = lo + gr * (hi - lo)
            fd = m2lnl(galaxies, a_of_z, d, point_mass)
    s = 0.5 * (lo + hi)
    return {"sigma_int_dex": s, "m2lnL": m2lnl(galaxies, a_of_z, s, point_mass)}


def fit_scale(galaxies, shape, point_mass=False):
    """The normalisation A of a_M(z) = A shape(z) that the data prefer (for comparison with Verlinde's value)."""
    def objective(x):
        return best_scatter(galaxies, lambda z: math.exp(x[0]) * shape(z), point_mass)["m2lnL"]
    x, val = jf.nelder_mead(objective, [math.log(1.0)], [0.3], tol=1e-9, max_iter=2000)
    return {"A": math.exp(x[0]), "m2lnL": val}


def shapes():
    planck = a_verlinde(H0_PLANCK)
    out = {
        "expansion rate H(z) (Planck)": (planck, lambda z: a0e.e_of_z(z, OMEGA_M_PLANCK)),
        "constant, c H0/6 (Planck)": (planck, lambda z: 1.0),
        "constant, dark-energy part today (Planck)": (planck * math.sqrt(1.0 - OMEGA_M_PLANCK), lambda z: 1.0),
    }
    for key, (w0, wa, om, h0) in DESI_DR2.items():
        out[f"dark-energy part H_DE(z), {key}"] = (
            a_verlinde(h0) * math.sqrt(1.0 - om),
            lambda z, w0=w0, wa=wa: math.sqrt(a0e.rho_de_ratio(z, w0, wa)))
    return out


def validate(galaxies):
    big = 1e11
    return {
        "k_point_mass_bulge_far_out": slope_factor(50.0, 0.0, big),
        "k_exponential_disc_at_R_e": slope_factor(5.0, big, 1e-9 * big),
        "a_M_planck_today": a_verlinde(H0_PLANCK),
        "k_distribution": {"min": min(g["k"] for g in galaxies), "median": statistics.median(g["k"] for g in galaxies),
                           "max": max(g["k"] for g in galaxies)},
        "bt_distribution": {"min": min(g["bt"] for g in galaxies), "median": statistics.median(g["bt"] for g in galaxies),
                            "max": max(g["bt"] for g in galaxies)},
    }


def analyse():
    galaxies = load_galaxies()
    models = {}
    for name, (scale, shape) in shapes().items():
        row = {"a_M_today": scale * shape(0.0), "a_M_at_z2.2": scale * shape(2.2)}
        for label, pm in (("extended", False), ("point_mass", True)):
            zero = best_scatter(galaxies, lambda z: scale * shape(z), pm)
            free = fit_scale(galaxies, shape, pm)
            row[label] = {"zero_parameter_m2lnL": zero["m2lnL"], "sigma_int_dex": zero["sigma_int_dex"],
                          "preferred_scale_today": free["A"] * shape(0.0), "free_scale_m2lnL": free["m2lnL"],
                          "preferred_over_verlinde_scale": free["A"] / scale}
        models[name] = row
    for label in ("extended", "point_mass"):
        best = min(m[label]["zero_parameter_m2lnL"] for m in models.values())
        best_free = min(m[label]["free_scale_m2lnL"] for m in models.values())
        for m in models.values():
            m[label]["delta_vs_best_zero_parameter"] = m[label]["zero_parameter_m2lnL"] - best
            m[label]["delta_free_vs_best_free"] = m[label]["free_scale_m2lnL"] - best_free
    return {
        "question": "Is the extra gravity in galaxies Verlinde's response to dark energy, and which H sets its scale?",
        "data": {"file": "data/rc100_table3.csv", "galaxies": len(galaxies),
                 "mass_model": "exponential disc (R_e) + spherical Sersic n = 4 bulge (R_e = 1 kpc), as in RC100"},
        "validation": validate(galaxies),
        "models": models,
    }


def render_markdown(res):
    m, v = res["models"], res["validation"]
    h_name = "expansion rate H(z) (Planck)"
    const_name = "constant, c H0/6 (Planck)"
    de_names = [k for k in m if k.startswith("dark-energy part H_DE(z)")]
    ext = lambda name: m[name]["extended"]  # noqa: E731
    best_de = min(de_names, key=lambda k: ext(k)["zero_parameter_m2lnL"])
    ratios_e = [r["extended"]["preferred_over_verlinde_scale"] for r in m.values()]
    ratios_p = [r["point_mass"]["preferred_over_verlinde_scale"] for r in m.values()]
    gap = min(r["extended"]["zero_parameter_m2lnL"] - r["extended"]["free_scale_m2lnL"] for r in m.values())
    free_de = min(ext(k)["free_scale_m2lnL"] for k in de_names)
    lines = [
        "# Is \"dark matter\" gravity's response to dark energy? Verlinde's formula on 100 galaxies",
        "",
        "<!-- GENERATED by analyses/emergent_gravity.py from analyses/emergent_gravity.json. Do not edit by hand. -->",
        "",
        "Diagnostic behind [OPEN_PROBLEMS.md](../OPEN_PROBLEMS.md) problem 11, not a registered prediction. Emergent",
        "gravity (Verlinde, SciPost Phys. 2, 016, 2017) treats the extra gravity of galaxies as the response of the",
        "dark-energy vacuum to ordinary matter, with no new substance: g_obs = g_bar + √(k a_M g_bar), a_M = c H/6, where",
        "k depends on how the mass is distributed (k = 1 for a point mass). Data: the 100 RC100 disks at z = 0.6–2.5",
        "([data/rc100_table3.csv](../data/rc100_table3.csv)). Code: [emergent_gravity.py](emergent_gravity.py); numbers:",
        "[emergent_gravity.json](emergent_gravity.json). Accelerations in 10⁻¹⁰ m/s².",
        "",
        "## Answer",
        "",
        "Not in the form Verlinde published. With his scale, c H/6, the formula predicts far more extra gravity at the",
        "effective radius than RC100 measures, whichever H sets it: left free, the galaxies prefer a scale of",
        f"{min(ratios_e):.2f}–{max(ratios_e):.2f} times his ({min(ratios_p):.2f}–{max(ratios_p):.2f} for a point mass). Every form with his scale fits worse than",
        f"the same form with a free scale by at least Δ(−2 ln L) = {gap:.0f}.",
        "",
        "The question the extension raises is still answered the same way. Among the forms with no free parameter, the",
        f"dark-energy part H_DE(z) beats the expansion rate H(z) by Δ(−2 ln L) = {ext(h_name)['zero_parameter_m2lnL'] - ext(best_de)['zero_parameter_m2lnL']:.0f} (best with DESI's",
        f"{best_de.split(', ')[-1]} dark energy). With the scale free, the dark-energy shape fits better than a constant",
        f"(Δ(−2 ln L) = {free_de - ext(const_name)['free_scale_m2lnL']:+.1f}) and the H(z) shape worse ({ext(h_name)['free_scale_m2lnL'] - ext(const_name)['free_scale_m2lnL']:+.1f}): the pattern of",
        "[a0_evolution.md](a0_evolution.md) and P15, now with Verlinde's form of the relation.",
        "",
        "## All forms",
        "",
        "Δ(−2 ln L) against the best of each kind. \"Extended\" uses each galaxy's mass distribution; \"point mass\" sets",
        "k = 1. \"Preferred / Verlinde\" is the scale the data prefer over Verlinde's value for that form.",
        "",
        "| Scale of the extra gravity | a_M today | a_M at z = 2.2 | Verlinde's scale: Δ | Free scale: Δ | Preferred / Verlinde | Point mass, Verlinde's scale: Δ | Point mass: preferred / Verlinde |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, row in m.items():
        e, p = row["extended"], row["point_mass"]
        lines.append(f"| {name} | {row['a_M_today']:.2f} | {row['a_M_at_z2.2']:.2f} | {e['delta_vs_best_zero_parameter']:+.1f} | "
                     f"{e['delta_free_vs_best_free']:+.1f} | {e['preferred_over_verlinde_scale']:.2f} | "
                     f"{p['delta_vs_best_zero_parameter']:+.1f} | {p['preferred_over_verlinde_scale']:.2f} |")
    lines += [
        "",
        "## How far this goes",
        "",
        "- Verlinde derived the formula for the regime where the apparent dark matter dominates, in a universe dominated",
        "  by dark energy. At the effective radius most RC100 galaxies are dominated by their baryons, and at z = 0.6–2.5",
        "  the universe is not dominated by dark energy, so both uses are extrapolations, as in the published tests.",
        "- At z ≈ 0, Lelli, McGaugh & Schombert (MNRAS 468, L68, 2017) found the formula fits nearby galaxies only with",
        "  stellar masses lower than other estimates allow: the same excess of extra gravity seen here.",
        "- The mass distribution enters through k, taken from RC100's model (exponential disc, n = 4 bulge of 1 kpc).",
        f"  Across the sample k runs from {v['k_distribution']['min']:.2f} to {v['k_distribution']['max']:.2f} (median {v['k_distribution']['median']:.2f}); "
        f"bulge fractions run from {v['bt_distribution']['min']:.2f} to {v['bt_distribution']['max']:.2f}.",
        "- The dark-matter fractions come from the authors' mass models with dark-matter halos, as in",
        "  [a0_evolution.md](a0_evolution.md).",
        "",
        "## Checks",
        "",
        f"A point mass gives k = {v['k_point_mass_bulge_far_out']:.3f} (expected 1); a pure exponential disc at its effective radius gives",
        f"k = {v['k_exponential_disc_at_R_e']:.3f}, its rotation curve still rising there. Verlinde's scale for Planck's H0 is",
        f"c H0/6 = {v['a_M_planck_today']:.3f}.",
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
            print("DIFFERS: emergent_gravity.md is not the rendering of emergent_gravity.json")
        ok = not problems and md_current
        print("emergent-gravity check reproduces its committed output" if ok
              else "emergent-gravity check does NOT reproduce its committed output")
        return 0 if ok else 1
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(res), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
