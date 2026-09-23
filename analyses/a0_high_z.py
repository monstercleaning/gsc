#!/usr/bin/env python3
"""a0_high_z.py — DIAGNOSTIC: can rotation curves at z ≈ 4.5 measure Milgrom's a0? (retrodictive check of P15).

Why this is here. P15 (predictions/P15_a0_dark_energy/) predicts that a0 at
z ≈ 4.5 is 0.43-0.66 of today's. Its registration promised a check against
the rotation curves already published at z ≈ 4-5, examined only after the
registration. This is that check; being retrodictive, it cannot score P15.

Data. Roman-Oliveira, Fraternali & Rizzo, A&A 687, A35 (2024), arXiv:2403.00904:
four [CII] discs at z ≈ 4.5 observed with ALMA. Their circular speeds,
corrected for pressure support, are on Zenodo (doi:10.5281/zenodo.10707348,
CC BY 4.0) and copied in data/ro24_circular_speed/. The baryonic model and the
priors are theirs (Sect. 2.6, Tables 1-4): a deprojected spherical Sérsic
stellar component (Terzić & Graham 2005), with log M* in [9, 12], n in
[0.2, 10] and R_eff between the dust and [CII] effective radii; and a
razor-thin exponential gas disc with the [CII] scale length and
M_gas = gas_norm × L_CO, gas_norm in [0, 10].

Method. Instead of their NFW halo, the radial acceleration relation
g_obs = g_bar / (1 - exp(-sqrt(g_bar/a0))) supplies the extra gravity. For each
fixed a0, the baryonic parameters are refitted within the same priors, and the
minimum chi^2 of the circular speeds is recorded; a0 = 0 is Newtonian gravity
with baryons alone. If the minimum barely changes with a0, these data cannot
measure it.

Deterministic, standard library only. Writes analyses/a0_high_z.json and
analyses/a0_high_z.md; `--check` recomputes and compares with tolerance.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joint_fit as jf  # noqa: E402  (nelder_mead, _round, _compare)

REPO_ROOT = HERE.parent
DATA = REPO_ROOT / "data" / "ro24_circular_speed"
P15_OUTPUT = REPO_ROOT / "predictions" / "P15_a0_dark_energy" / "pipeline_output.json"
OUT_JSON = HERE / "a0_high_z.json"
OUT_MD = HERE / "a0_high_z.md"

G_KPC = 4.30091e-6                     # G in kpc (km/s)^2 per solar mass
KPC_M = 3.0856775814913673e19
A0_GRID = (0.0, 0.3, 0.5, 0.72, 1.0, 1.2, 2.0, 4.0, 8.0)   # 1e-10 m/s^2; 0 is Newtonian, baryons only

# Roman-Oliveira et al. 2024: L_CO (Table 1; SGP38326 split 2.5 : 1 between the components, as in the paper),
# dust and [CII] effective radii (Table 3), and their NFW-model best fit (Table 4) for reference:
# (log M*, R_eff*, n, log M_gas, log M200).
GALAXIES = {
    "BRI1335-0417": {"L_CO": 10.9e10, "r_dust": 1.69, "r_cii": 3.06, "nfw_fit": (10.4, 2.3, 6.9, 9.8, 11.2)},
    "J081740": {"L_CO": 2.4e10, "r_dust": 1.79, "r_cii": 3.2, "nfw_fit": (10.6, 2.4, 6.7, 10.5, 12.3)},
    "SGP38326-1": {"L_CO": 15.4e10 * 2.5 / 3.5, "r_dust": 1.29, "r_cii": 3.2, "nfw_fit": (11.0, 2.2, 6.3, 11.3, 13.2)},
    "SGP38326-2": {"L_CO": 15.4e10 / 3.5, "r_dust": 1.08, "r_cii": 2.4, "nfw_fit": (10.3, 1.7, 5.3, 11.1, 13.3)},
}
PRIORS = {"log_mstar": (9.0, 12.0), "n": (0.2, 10.0), "gas_norm": (0.0, 10.0)}


def gammainc_lower_regularized(s, x):
    """P(s, x) = gamma(s, x) / Gamma(s): series below s + 1, continued fraction above (Numerical Recipes 6.2)."""
    if x <= 0.0:
        return 0.0
    log_pre = -x + s * math.log(x) - math.lgamma(s)
    if x < s + 1.0:
        term = 1.0 / s
        total, k = term, 1
        while abs(term) > 1e-16 * abs(total):
            term *= x / (s + k)
            total += term
            k += 1
        return total * math.exp(log_pre)
    b, c = x + 1.0 - s, 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return 1.0 - math.exp(log_pre) * h


def bessel_i0(x):
    t = x / 3.75
    if x < 3.75:
        return 1 + 3.5156229*t**2 + 3.0899424*t**4 + 1.2067492*t**6 + 0.2659732*t**8 + 0.0360768*t**10 + 0.0045813*t**12
    return math.exp(x) / math.sqrt(x) * (0.39894228 + 0.01328592/t + 0.00225319/t**2 - 0.00157565/t**3
                                         + 0.00916281/t**4 - 0.02057706/t**5 + 0.02635537/t**6
                                         - 0.01647633/t**7 + 0.00392377/t**8)


def bessel_i1(x):
    t = x / 3.75
    if x < 3.75:
        return x * (0.5 + 0.87890594*t**2 + 0.51498869*t**4 + 0.15084934*t**6 + 0.02658733*t**8
                    + 0.00301532*t**10 + 0.00032411*t**12)
    return math.exp(x) / math.sqrt(x) * (0.39894228 - 0.03988024/t - 0.00362018/t**2 + 0.00163801/t**3
                                         - 0.01031555/t**4 + 0.02282967/t**5 - 0.02895312/t**6
                                         + 0.01787654/t**7 - 0.00420059/t**8)


def bessel_k0(x):
    if x <= 2.0:
        t = x * x / 4.0
        return (-math.log(x / 2.0) * bessel_i0(x) - 0.57721566 + 0.42278420*t + 0.23069756*t**2 + 0.03488590*t**3
                + 0.00262698*t**4 + 0.00010750*t**5 + 0.0000074*t**6)
    t = 2.0 / x
    return math.exp(-x) / math.sqrt(x) * (1.25331414 - 0.07832358*t + 0.02189568*t**2 - 0.01062446*t**3
                                          + 0.00587872*t**4 - 0.00251540*t**5 + 0.00053208*t**6)


def bessel_k1(x):
    if x <= 2.0:
        t = x * x / 4.0
        return (math.log(x / 2.0) * bessel_i1(x) + (1.0 / x) * (1 + 0.15443144*t - 0.67278579*t**2 - 0.18156897*t**3
                                                              - 0.01919402*t**4 - 0.00110404*t**5 - 0.00004686*t**6))
    t = 2.0 / x
    return math.exp(-x) / math.sqrt(x) * (1.25331414 + 0.23498619*t - 0.03655620*t**2 + 0.01504268*t**3
                                          - 0.00780353*t**4 + 0.00325614*t**5 - 0.00068245*t**6)


def v2_sersic(r, mass, r_eff, n):
    """Circular speed^2 of a deprojected spherical Sérsic profile (Terzić & Graham 2005; p of Lima Neto et al. 1999)."""
    p = 1.0 - 0.6097 / n + 0.05463 / n ** 2
    b = 2.0 * n - 1.0 / 3.0 + 4.0 / (405.0 * n) + 46.0 / (25515.0 * n * n)
    return G_KPC * mass / r * gammainc_lower_regularized(n * (3.0 - p), b * (r / r_eff) ** (1.0 / n))


def v2_exponential_disc(r, mass, r_d):
    """Circular speed^2 of a razor-thin exponential disc (Freeman 1970)."""
    y = r / (2.0 * r_d)
    return 2.0 * G_KPC * mass * y * y / r_d * (bessel_i0(y) * bessel_k0(y) - bessel_i1(y) * bessel_k1(y))


def nu_rar(x):
    return -1.0 / math.expm1(-math.sqrt(x))


def load_curve(name):
    rows = []
    for line in (DATA / f"circular_speed_{name}.dat").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            v, sv, r = (float(x) for x in line.split())
            rows.append({"r": r, "v": v, "sv": sv})
    return rows


def model_speed(r, a0, log_mstar, r_eff, n, gas_norm, gal):
    v2_bar = v2_sersic(r, 10.0 ** log_mstar, r_eff, n) + v2_exponential_disc(r, gas_norm * gal["L_CO"], gal["r_cii"] / 1.678)
    g_bar = v2_bar * 1e6 / (r * KPC_M)
    g_obs = g_bar * nu_rar(g_bar / (a0 * 1e-10)) if a0 > 0 else g_bar
    return math.sqrt(g_obs * r * KPC_M) / 1e3


def refit(name, a0):
    """Minimum chi^2 over the baryonic parameters, within the authors' priors, for a fixed a0."""
    gal, curve = GALAXIES[name], load_curve(name)
    bounds = [PRIORS["log_mstar"], (gal["r_dust"], gal["r_cii"]), PRIORS["n"], PRIORS["gas_norm"]]

    def clamp(x):
        return [min(hi, max(lo, v)) for v, (lo, hi) in zip(x, bounds)]

    def objective(x):
        c = clamp(x)
        penalty = 1e4 * sum((a - b) ** 2 for a, b in zip(x, c))
        return sum(((model_speed(p["r"], a0, *c, gal) - p["v"]) / p["sv"]) ** 2 for p in curve) + penalty

    nfw = gal["nfw_fit"]
    starts = ([nfw[0], nfw[1], nfw[2], 10.0 ** nfw[3] / gal["L_CO"]],
              [nfw[0] + 0.3, gal["r_dust"], 2.0, 1.0],
              [nfw[0] - 0.3, gal["r_cii"], 8.0, 5.0],
              [11.0, 0.5 * (gal["r_dust"] + gal["r_cii"]), 4.0, 3.0])
    best_val, best_x = float("inf"), None
    for start in starts:
        x, val = jf.nelder_mead(objective, start, [0.2, 0.3, 1.0, 0.8], tol=1e-9, max_iter=4000)
        x, val = jf.nelder_mead(objective, x, [0.05, 0.1, 0.3, 0.2], tol=1e-10, max_iter=4000)
        if val < best_val:
            best_val, best_x = val, x
    c = clamp(best_x)
    return {"chi2": best_val, "log_mstar": c[0], "r_eff_star_kpc": c[1], "sersic_n": c[2], "gas_norm": c[3],
            "log_mgas": math.log10(c[3] * gal["L_CO"]) if c[3] > 0 else None}


def validate():
    """Special functions and component speeds against known values."""
    peak = max((v2_exponential_disc(r / 100.0, 1.0, 1.0), r / 100.0) for r in range(50, 500))
    return {
        "gammainc_P1_x2_vs_closed_form": gammainc_lower_regularized(1.0, 2.0) - (1.0 - math.exp(-2.0)),
        "gammainc_P3_x10_vs_closed_form": gammainc_lower_regularized(3.0, 10.0)
        - (1.0 - math.exp(-10.0) * (1.0 + 10.0 + 50.0)),
        "bessel_at_1_vs_tables": [bessel_i0(1.0) - 1.2660658, bessel_i1(1.0) - 0.5651591,
                                  bessel_k0(1.0) - 0.4210244, bessel_k1(1.0) - 0.6019072],
        "exponential_disc_peak": {"radius_over_rd": peak[1], "v2_over_GM_rd": peak[0] / G_KPC,
                                  "expected": "2.15-2.2 R_d and 0.387 G M / R_d (Freeman 1970)"},
        "sersic_encloses_total_mass": v2_sersic(1e4, 1.0, 1.0, 4.0) * 1e4 / G_KPC,
    }


def analyse():
    p15 = json.loads(P15_OUTPUT.read_text(encoding="utf-8"))
    band_45 = next(g for g in p15["prediction"]["ratio_to_today"] if g["z"] == 4.5)
    galaxies, totals = {}, {f"{a:g}": 0.0 for a in A0_GRID}
    n_points = 0
    for name in GALAXIES:
        curve = load_curve(name)
        n_points += len(curve)
        fits = {}
        for a0 in A0_GRID:
            r = refit(name, a0)
            fits[f"{a0:g}"] = r
            totals[f"{a0:g}"] += r["chi2"]
        galaxies[name] = {"points": len(curve), "radius_range_kpc": [curve[0]["r"], curve[-1]["r"]],
                          "g_obs_outermost_over_1.2e-10": (curve[-1]["v"] * 1e3) ** 2 / (curve[-1]["r"] * KPC_M) / 1.2e-10,
                          "published_nfw_fit": dict(zip(("log_mstar", "r_eff_star_kpc", "sersic_n", "log_mgas", "log_m200"),
                                                        GALAXIES[name]["nfw_fit"])),
                          "refits": fits}
    chi_values = list(totals.values())
    return {
        "question": "Can the z ~ 4.5 rotation curves published so far measure a0?",
        "data": {"source": "Roman-Oliveira, Fraternali & Rizzo, A&A 687, A35 (2024), arXiv:2403.00904",
                 "files": "data/ro24_circular_speed/ (Zenodo doi:10.5281/zenodo.10707348, CC BY 4.0)",
                 "galaxies": len(GALAXIES), "points": n_points,
                 "free_parameters_per_galaxy": 4},
        "a0_grid": list(A0_GRID),
        "validation": validate(),
        "galaxies": galaxies,
        "total_chi2_by_a0": totals,
        "total_chi2_range": [min(chi_values), max(chi_values)],
        "p15_band_at_z4.5": {"central": band_45["central"], "band": band_45["band"]},
    }


def render_markdown(res):
    t, rng = res["total_chi2_by_a0"], res["total_chi2_range"]
    grid = [f"{a:g}" for a in res["a0_grid"]]
    band = res["p15_band_at_z4.5"]
    d = res["data"]
    best_a0 = min(grid, key=lambda a: t[a])
    best_text = ("Newtonian gravity with baryons alone (a0 = 0) fits best" if best_a0 == "0"
                 else f"the best fit is at a0 = {best_a0}")
    high = sum(1 for g in res["galaxies"].values() if g["g_obs_outermost_over_1.2e-10"] > 4.0)
    lines = [
        "# Can rotation curves at z ≈ 4.5 measure Milgrom's a0?",
        "",
        "<!-- GENERATED by analyses/a0_high_z.py from analyses/a0_high_z.json. Do not edit by hand. -->",
        "",
        "Retrodictive check of [P15](../predictions/P15_a0_dark_energy/), promised in its registration; it cannot score",
        "P15. Data: the four [CII] discs at z ≈ 4.5 of Roman-Oliveira, Fraternali & Rizzo (A&A 687, A35, 2024), whose",
        "circular speeds are public ([data/ro24_circular_speed/](../data/ro24_circular_speed/)). Code:",
        "[a0_high_z.py](a0_high_z.py); numbers: [a0_high_z.json](a0_high_z.json). Accelerations in 10⁻¹⁰ m/s².",
        "",
        "## Answer",
        "",
        f"No. With the baryons refitted within the authors' own priors, the {d['points']} circular speeds of the",
        f"{d['galaxies']} galaxies fit about equally well for any a0 from 0 to 8: the total χ² runs from {rng[0]:.1f} to",
        f"{rng[1]:.1f}, and {best_text}. P15 predicts {band['central']:.2f} ({band['band'][0]:.2f}–{band['band'][1]:.2f}) of today's a0",
        f"at z = 4.5, that is {1.2 * band['band'][0]:.1f}–{1.2 * band['band'][1]:.1f}; a constant a0 is 1.2. Between a0 = 0.72, P15's central value, and",
        f"1.2 the total χ² differs by {t['1.2'] - t['0.72']:.1f}. These data can tell neither from the other, nor either from no",
        "extra gravity at all.",
        "",
        f"Two reasons. The discs are compact and rotate fast: {high} of the {d['galaxies']} stay above four times a0 even at their",
        "outermost point, where the radial acceleration relation adds little. And without rest-frame optical imaging",
        "the stellar masses are known only from the same rotation curves, so a different a0 is absorbed by a different",
        "mass. The dark-matter halos of the authors' decomposition come from assuming an NFW halo, not from the data",
        "requiring one.",
        "",
        "## Minimum χ² for fixed a0",
        "",
        "| Galaxy | Points | Outermost g_obs / 1.2 | " + " | ".join(f"a0 = {a}" for a in grid) + " |",
        "|---|---|---|" + "---|" * len(grid),
    ]
    for name, g in res["galaxies"].items():
        lines.append(f"| {name} | {g['points']} | {g['g_obs_outermost_over_1.2e-10']:.1f} | "
                     + " | ".join(f"{g['refits'][a]['chi2']:.2f}" for a in grid) + " |")
    lines.append("| **Total** | " + f"{d['points']} | | " + " | ".join(f"{t[a]:.2f}" for a in grid) + " |")
    lines += [
        "",
        f"Each galaxy has {d['free_parameters_per_galaxy']} free baryonic parameters (stellar mass, radius and Sérsic index, gas",
        "normalisation) and 3 to 5 points, so the fits are nearly exact whatever a0 is. The refitted stellar and gas",
        "masses are in the JSON file.",
        "",
        "## What would test P15",
        "",
        "Rotation curves at z ≳ 3 that reach accelerations near or below a0 (outer discs, or less massive galaxies),",
        "with stellar masses from rest-frame optical imaging rather than from the kinematics, and at least ten galaxies",
        "analysed in one way, as P15's scoring rule requires.",
        "",
        "## Checks",
        "",
        "The incomplete gamma function matches closed forms " + (
            "to machine precision" if max(abs(res['validation']['gammainc_P1_x2_vs_closed_form']),
                                          abs(res['validation']['gammainc_P3_x10_vs_closed_form'])) < 1e-14
            else f"to {max(abs(res['validation']['gammainc_P1_x2_vs_closed_form']), abs(res['validation']['gammainc_P3_x10_vs_closed_form'])):.0e}") + ";",
        f"the Bessel functions match tables to {max(abs(x) for x in res['validation']['bessel_at_1_vs_tables']):.0e}; the exponential disc peaks at",
        f"{res['validation']['exponential_disc_peak']['radius_over_rd']:.2f} R_d with v² = {res['validation']['exponential_disc_peak']['v2_over_GM_rd']:.3f} G M/R_d (expected 2.15–2.2 R_d and 0.387);",
        f"the Sérsic component encloses {res['validation']['sersic_encloses_total_mass']:.4f} of its mass at large radius.",
        "",
        "## Limits",
        "",
        "- The circular speeds already include the authors' pressure-support correction; their uncertainty is used as given.",
        "- The five lensed galaxies at z ≈ 4.5 of Rizzo et al. (MNRAS 507, 3952, 2021) are also massive and mostly",
        "  bulge-dominated; they were not analysed and would face the same two limits.",
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
            print("DIFFERS: a0_high_z.md is not the rendering of a0_high_z.json")
        ok = not problems and md_current
        print("a0 high-z check reproduces its committed output" if ok else "a0 high-z check does NOT reproduce its committed output")
        return 0 if ok else 1
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(res), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
