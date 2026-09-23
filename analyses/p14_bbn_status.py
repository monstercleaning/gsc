#!/usr/bin/env python3
"""p14_bbn_status.py — DIAGNOSTIC: where P14 stands against the primordial helium and deuterium measured so far.

Why this is here. P14 (predictions/P14_early_gravity/) predicts that gravity,
relative to atoms, was 2.98% weaker during nucleosynthesis (G/G0 = 0.9702;
0.9670 at the neutron-proton freeze-out). Its registration cited Alvey et al.
(2020) as the best nucleosynthesis bound and missed results published before it:
the LBT helium abundance (Aver et al. 2026, arXiv:2601.22238) and two readings of
it as the expansion rate during nucleosynthesis (Goldstein & Hill 2026,
arXiv:2603.13226; Loverde, Saravanan & Weiner 2026, arXiv:2609.13140). None of
them can score P14: all predate the registration and none is a determination of
G itself. This diagnostic records what they imply.

Method. During nucleosynthesis G enters only through the expansion rate, so the
abundances follow the logarithmic sensitivities of Fields et al. (arXiv:1912.01132,
eqs. 16-17): Y_p ~ G^0.357 eta^0.039 N_nu^0.163 and D/H ~ G^0.952 eta^-1.597.
Each measurement gives ln(G/G0) = ln(X_obs / X_std) / alpha_G, with measurement
and prediction errors added in quadrature. The standard deuterium prediction
X_std (G = G0) depends on how the measured deuterium-burning cross sections are
fitted: with low-degree polynomials (Yeh, Olive & Fields 2021), with ab initio
energy dependences (PRIMAT, Pitrou et al. 2021), or with Gaussian processes
(Launders, Giovanetti & Liu 2026), who show that the polynomial fits
over-predict deuterium. Helium is insensitive to these rates. Two treatments
of the baryon density: as each prediction took it from the CMB ("as
published"), and 0.02236 +- 0.00030 from a Planck analysis that lets G at
recombination vary freely (Bai et al. 2015, as used by Alvey et al. 2020;
"widened"). P14 changes G at recombination by a fixed 0.8%, so the treatment
its model implies lies between the two: close to the published error, with a
central value moved by an amount that needs a CMB fit of the model. An
expansion rate quoted as N_eff maps to G through the ratio of the helium
sensitivities to G and to the number of neutrino species.

Deterministic, standard library only. Writes analyses/p14_bbn_status.json and
analyses/p14_bbn_status.md; `--check` recomputes and compares with tolerance.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joint_fit as jf  # noqa: E402  (_round, _compare)

REPO_ROOT = HERE.parent
P14_OUTPUT = REPO_ROOT / "predictions" / "P14_early_gravity" / "pipeline_output.json"
OUT_JSON = HERE / "p14_bbn_status.json"
OUT_MD = HERE / "p14_bbn_status.md"

# Fields, Olive, Yeh & Young, arXiv:1912.01132 (JCAP 03 (2020) 010), eqs. 16-17: d ln X / d ln p.
SENS = {"Y_p": {"G": 0.357, "eta": 0.039, "N_nu": 0.163}, "D/H": {"G": 0.952, "eta": -1.597, "N_nu": 0.396}}
N_EFF_SM = 3.044
# Change of ln G per unit N_eff that moves helium as much: (d ln Y_p / d N_nu) / (d ln Y_p / d ln G).
G_PER_N_EFF = SENS["Y_p"]["N_nu"] / 3.0 / SENS["Y_p"]["G"]
G_PER_N_EFF_RADIATION = 7.0 / 43.0  # radiation counting before e+e- annihilation (10.75 degrees of freedom)

# Standard predictions (G = G0), each at the CMB baryon density it was computed with; D/H in 1e-5.
# "Y_p": None means the prediction covers deuterium only; helium is then taken from HELIUM_FROM.
THEORY = {
    "Polynomial fits (Yeh, Olive & Fields 2021)": {
        "ref": "arXiv:2011.13874, Table 2 and abstract (Planck 2018 TT+TE+EE+lowE+lensing; eta_10 = 6.129 +- 0.040)",
        "cmb": "Planck 2018", "Y_p": (0.24693, 0.00018), "D/H": (2.51, 0.11), "omega_b": (0.02239, 0.00014)},
    "PRIMAT (Pitrou et al. 2021)": {
        "ref": "arXiv:2011.11320, predicted-abundance table and eq. 10 (Planck 2018 CMB+BAO)",
        "cmb": "Planck 2018", "Y_p": (0.24721, 0.00014), "D/H": (2.439, 0.037), "omega_b": (0.02242, 0.00014)},
    "Gaussian processes (Launders et al. 2026)": {
        "ref": "arXiv:2604.16600, eq. 6 (LINX; Planck 2018 TT,TE,EE+lowE+lensing baryon density marginalised)",
        "cmb": "Planck 2018", "Y_p": None, "D/H": (2.442, 0.040), "omega_b": (0.02237, 0.00015)},
    "Gaussian processes (Launders et al. 2026), Planck+ACT+SPT": {
        "ref": "arXiv:2604.16600, Table 1 (baryon density of Planck, ACT DR6 and SPT-3G D1 combined)",
        "cmb": "Planck+ACT+SPT", "Y_p": None, "D/H": (2.437, 0.034), "omega_b": (0.022398, 0.000095)},
}
HELIUM_FROM = "PRIMAT (Pitrou et al. 2021)"
POLY, PRIMAT, GP, GP_SPA = list(THEORY)
GP_NUCLEAR_ONLY = (2.442, 0.029)  # Launders et al. eq. 12: baryon density fixed at Planck's central value
BARYON_G_FREE = (0.02236, 0.00030)  # Bai et al. 2015, Planck with G_CMB free; Alvey et al. 2020, eq. 7
TREATMENTS = ("as published", "widened")  # the prediction's own CMB baryon density; error widened to BARYON_G_FREE

# Measurements, as (value, +err, -err); D/H in 1e-5.
HELIUM = {
    "LBT (Aver et al. 2026)": {"ref": "arXiv:2601.22238", "value": (0.2458, 0.0013, 0.0013)},
    "Kurichin et al. 2021": {"ref": "arXiv:2101.09127", "value": (0.2462, 0.0022, 0.0022)},
    "Aver et al. 2021": {"ref": "arXiv:2010.04180", "value": (0.2453, 0.0034, 0.0034)},
    "EMPRESS (Matsumoto et al. 2022)": {"ref": "arXiv:2203.09617", "value": (0.2370, 0.0034, 0.0033)},
}
DEUTERIUM = {
    "PDG 2025, mean of 12 systems": {"ref": "Review of Particle Physics 2025, BBN review, Table 24.1 (scale factor 1.08)",
                                     "value": (2.508, 0.029, 0.029)},
    "Cooke, Pettini & Steidel 2018": {"ref": "arXiv:1710.11129", "value": (2.527, 0.030, 0.030)},
}
PRIMARY_HELIUM = "LBT (Aver et al. 2026)"
PRIMARY_DEUTERIUM = "PDG 2025, mean of 12 systems"

# Published determinations of the expansion rate, or of G, during nucleosynthesis (1 sigma).
PUBLISHED = {
    "Loverde, Saravanan & Weiner 2026, LBT helium": {"ref": "arXiv:2609.13140, Sect. III.2",
                                                    "n_eff_bbn": (2.974, 0.091, 0.091)},
    "Loverde, Saravanan & Weiner 2026, LBT helium + CMB": {"ref": "arXiv:2609.13140, Sect. III.2",
                                                          "n_eff_bbn": (2.964, 0.096, 0.096)},
    "Goldstein & Hill 2026, LBT helium + deuterium": {"ref": "arXiv:2603.13226, Sect. III",
                                                     "n_eff_bbn": (2.976, 0.093, 0.093)},
    "Alvey et al. 2020": {"ref": "arXiv:1910.10730; 2σ interval halved", "g": (0.99, 0.03, 0.025)},
    "Kohri & Maeda 2022, EMPRESS helium": {"ref": "arXiv:2206.11257", "g": (0.915, 0.026, 0.028)},
}
HEADLINE = "Loverde, Saravanan & Weiner 2026, LBT helium"
# Context: with PRIMAT, deuterium prefers a faster expansion while deuterium burns (a very early dark energy).
POULIN_2026 = {"ref": "Poulin, Froustey, Pitrou & Smith, arXiv:2607.20635", "delta_H_over_H": (0.087, 0.036, 0.037),
               "temperature_MeV": 0.03}

# Alvey et al. 2020 inputs, used to validate the method: PDG 2019 abundances, Fields et al. prediction errors,
# the G-free baryon density, and PRIMAT 2018 (as tabulated in arXiv:2011.11320) at omega_b = 0.02225.
ALVEY = {"Y_p_obs": (0.245, 0.003), "D/H_obs": (2.569, 0.027), "theory_err": {"Y_p": 0.00018, "D/H": 0.13},
         "primat2018": {"omega_b": 0.02225, "Y_p": 0.24709, "D/H": 2.460}, "published_g_2sigma": (0.99, 0.06, 0.05)}


def g_from_n_eff(n_eff, slope=G_PER_N_EFF):
    return math.exp(slope * (n_eff - N_EFF_SM))


def side(value, target):
    """The error on the side facing the target, for a (v, +e, -e) triple."""
    v, up, down = value
    return up if target > v else down


def treatments_for(code):
    """Widening replaces Planck's baryon-density error; it does not apply to other CMB combinations."""
    return TREATMENTS if THEORY[code]["cmb"] == "Planck 2018" else TREATMENTS[:1]


def standard(code, element, treatment):
    """Standard prediction and its relative error, at the baryon density of the chosen treatment."""
    th = THEORY[code] if THEORY[code][element] is not None else THEORY[HELIUM_FROM]
    x, s = th[element]
    w, sw = th["omega_b"]
    a_eta = SENS[element]["eta"]
    if treatment == "as published":
        return x, s / x
    x_free = x * (BARYON_G_FREE[0] / w) ** a_eta
    extra = a_eta * math.sqrt(BARYON_G_FREE[1] ** 2 - sw ** 2) / BARYON_G_FREE[0]
    return x_free, math.hypot(s / x, extra)


def estimate(x_obs, s_obs, x_std, s_rel_std, alpha):
    """ln(G/G0) and its error from one abundance."""
    return math.log(x_obs / x_std) / alpha, math.hypot(s_obs / x_obs, s_rel_std) / abs(alpha)


def combine(estimates):
    w = [1.0 / s ** 2 for _, s in estimates]
    return sum(wi * e for wi, (e, _) in zip(w, estimates)) / sum(w), 1.0 / math.sqrt(sum(w))


def rule_verdict(z, sigma, threshold):
    """P14's registered rule applied to one determination."""
    if abs(z) >= 3.0:
        return "FAIL"
    return "PASS" if sigma <= threshold else "SUB-THRESHOLD"


def summary(ln_g, s_ln, g_p14, threshold):
    z_p14 = (math.log(g_p14) - ln_g) / s_ln
    z_std = -ln_g / s_ln
    g = math.exp(ln_g)
    return {"G_over_G0": g, "sigma": g * s_ln, "p14_sigma_away": z_p14, "standard_sigma_away": z_std,
            "likelihood_standard_over_p14": math.exp((z_p14 ** 2 - z_std ** 2) / 2.0),
            "rule_if_it_counted": rule_verdict(z_p14, g * s_ln, threshold)}


def validate():
    """Reproduce Alvey et al. (2020) from their inputs; read the LBT helium three ways."""
    a = ALVEY
    shift = BARYON_G_FREE[0] / a["primat2018"]["omega_b"]
    est = []
    for el, obs in (("Y_p", a["Y_p_obs"]), ("D/H", a["D/H_obs"])):
        x_std = a["primat2018"][el] * shift ** SENS[el]["eta"]
        s_rel = math.hypot(a["theory_err"][el] / x_std, SENS[el]["eta"] * BARYON_G_FREE[1] / BARYON_G_FREE[0])
        est.append(estimate(obs[0], obs[1], x_std, s_rel, SENS[el]["G"]))
    ln_g, s_ln = combine(est)
    lbt = HELIUM[PRIMARY_HELIUM]["value"]
    x_std, s_rel = standard(POLY, "Y_p", "as published")
    ln_he, s_he = estimate(lbt[0], lbt[1], x_std, s_rel, SENS["Y_p"]["G"])
    n = PUBLISHED[HEADLINE]["n_eff_bbn"]
    return {
        "alvey_2020_reproduced": {"G_over_G0": math.exp(ln_g), "two_sigma": 2.0 * math.exp(ln_g) * s_ln,
                                  "published": {"G_over_G0": a["published_g_2sigma"][0],
                                                "two_sigma_up": a["published_g_2sigma"][1],
                                                "two_sigma_down": a["published_g_2sigma"][2]}},
        "lbt_helium_three_ways": {
            "direct_yeh_2021": {"G_over_G0": math.exp(ln_he), "sigma": math.exp(ln_he) * s_he},
            "loverde_n_eff_helium_slope": {"G_over_G0": g_from_n_eff(n[0]), "sigma": g_from_n_eff(n[0]) * G_PER_N_EFF * n[1]},
            "loverde_n_eff_radiation_slope": {"G_over_G0": g_from_n_eff(n[0], G_PER_N_EFF_RADIATION),
                                              "sigma": g_from_n_eff(n[0], G_PER_N_EFF_RADIATION) * G_PER_N_EFF_RADIATION * n[1]},
        },
    }


def analyse():
    p14 = json.loads(P14_OUTPUT.read_text(encoding="utf-8"))
    epochs = {e["epoch"]: e["G_over_G0"] for e in p14["prediction"]["epochs"]}
    g_p14, g_fo = epochs["nucleosynthesis"], epochs["weak_freeze_out"]
    q_reg = p14["registered_parameters"]["q"]
    threshold = abs(g_p14 - 1.0) / 2.0

    predicted = []
    for code, th in THEORY.items():
        y = th["Y_p"] or THEORY[HELIUM_FROM]["Y_p"]
        predicted.append({"prediction": code, "ref": th["ref"], "cmb": th["cmb"], "omega_b": th["omega_b"][0],
                          "helium_from": code if th["Y_p"] else HELIUM_FROM,
                          "standard_Y_p": y[0], "p14_Y_p": y[0] * g_p14 ** SENS["Y_p"]["G"],
                          "p14_Y_p_freeze_out_G": y[0] * g_fo ** SENS["Y_p"]["G"],
                          "standard_D_H": th["D/H"][0], "p14_D_H": th["D/H"][0] * g_p14 ** SENS["D/H"]["G"]})

    single, combined = [], []
    for code in THEORY:
        for treatment in treatments_for(code):
            per = {}
            for element, data in (("Y_p", HELIUM), ("D/H", DEUTERIUM)):
                for name, m in data.items():
                    x_std, s_rel = standard(code, element, treatment)
                    v = m["value"]
                    per[name] = estimate(v[0], side(v, x_std), x_std, s_rel, SENS[element]["G"])
                    if element == "D/H" or THEORY[code]["Y_p"] is not None:
                        single.append({"element": element, "measurement": name, "prediction": code,
                                       "baryon_density": treatment, **summary(*per[name], g_p14, threshold)})
            for d_name in DEUTERIUM:
                e_he, e_d = per[PRIMARY_HELIUM], per[d_name]
                combined.append({"helium": PRIMARY_HELIUM, "deuterium": d_name, "prediction": code,
                                 "baryon_density": treatment, **summary(*combine([e_he, e_d]), g_p14, threshold),
                                 "helium_vs_deuterium_sigma": abs(e_he[0] - e_d[0]) / math.hypot(e_he[1], e_d[1])})

    published = []
    for name, p in PUBLISHED.items():
        if "n_eff_bbn" in p:
            v = p["n_eff_bbn"]
            g = g_from_n_eff(v[0])
            s_p14 = s_std = g * G_PER_N_EFF * v[1]
            quoted = {"n_eff_bbn": v[0], "n_eff_sigma": v[1]}
        else:
            v = p["g"]
            g, s_p14, s_std = v[0], side(v, g_p14), side(v, 1.0)
            quoted = {}
        z = (g_p14 - g) / s_p14
        published.append({"result": name, "ref": p["ref"], **quoted, "G_over_G0": g, "sigma_toward_p14": s_p14,
                          "p14_sigma_away": z, "standard_sigma_away": (1.0 - g) / s_std,
                          "likelihood_standard_over_p14": math.exp((z ** 2 - ((1.0 - g) / s_std) ** 2) / 2.0),
                          "rule_if_it_counted": rule_verdict(z, s_p14, threshold)})

    k_q = math.log(g_p14) / q_reg  # ln(G_BBN/G0) per unit q, fixed by the transition shape

    def q_from(g, s):
        q, sq = math.log(g) / k_q, s / g / abs(k_q)
        return {"q": q, "sigma": sq, "two_sigma_range": [q - 2 * sq, q + 2 * sq]}

    head = next(r for r in published if r["result"] == HEADLINE)
    both = next(r for r in combined if r["prediction"] == GP and r["deuterium"] == PRIMARY_DEUTERIUM
                and r["baryon_density"] == "as published")

    # What a new measurement would need, with the larger of the two helium prediction errors.
    y_obs = HELIUM[PRIMARY_HELIUM]["value"][0]
    s_theory = max(standard(c, "Y_p", "as published")[1] for c in (POLY, PRIMAT)) * y_obs
    need_rule = y_obs * SENS["Y_p"]["G"] * threshold
    need_3sigma = y_obs * SENS["Y_p"]["G"] * abs(math.log(g_p14)) / 3.0
    d_poly = standard(POLY, "D/H", "widened")[0]  # both at omega_b = 0.02236
    d_gp = standard(GP, "D/H", "widened")[0]

    return {
        "question": "Where does P14 stand against the primordial helium and deuterium measured so far?",
        "p14": {"G_over_G0_nucleosynthesis": g_p14, "G_over_G0_weak_freeze_out": g_fo, "q_registered": q_reg,
                "pass_needs_sigma_at_most": threshold},
        "inputs": {"sensitivities": SENS, "g_per_n_eff": G_PER_N_EFF, "baryon_density_g_free": BARYON_G_FREE,
                   "theory": THEORY, "helium_from": HELIUM_FROM, "helium": HELIUM, "deuterium": DEUTERIUM,
                   "poulin_2026": POULIN_2026},
        "predicted_abundances": predicted,
        "single_measurements": single,
        "combined": combined,
        "published": published,
        "q": {"from_lbt_helium": q_from(head["G_over_G0"], head["sigma_toward_p14"]),
              "from_helium_and_deuterium": q_from(both["G_over_G0"], both["sigma"]),
              "registration_quoted_two_sigma_range": [-1.4e-3, 1.8e-3]},
        "what_would_decide": {
            "p14_helium_shift": abs(THEORY[POLY]["Y_p"][0] * (1.0 - g_p14 ** SENS["Y_p"]["G"])),
            "helium_prediction_error": s_theory,
            "helium_error_for_rule_precision": math.sqrt(max(need_rule ** 2 - s_theory ** 2, 0.0)),
            "helium_error_for_3sigma_separation": math.sqrt(max(need_3sigma ** 2 - s_theory ** 2, 0.0)),
            "lbt_helium_error": HELIUM[PRIMARY_HELIUM]["value"][1],
            "lbt_over_empress_precision": HELIUM["EMPRESS (Matsumoto et al. 2022)"]["value"][1] / HELIUM[PRIMARY_HELIUM]["value"][1],
            "p14_deuterium_shift_percent": 100.0 * (1.0 - g_p14 ** SENS["D/H"]["G"]),
            "polynomial_over_gp_percent": 100.0 * math.log(d_poly / d_gp),
            "gp_nuclear_error_percent": 100.0 * GP_NUCLEAR_ONLY[1] / GP_NUCLEAR_ONLY[0],
        },
        "validation": validate(),
    }


def _pm(v, s):
    return f"{v:.3f} ± {s:.3f}"


def _find(rows, **kw):
    return next(r for r in rows if all(r[k] == v for k, v in kw.items()))


def _away(r):
    return f"{abs(r['p14_sigma_away']):.1f}σ"


def _range(rows):
    lo, hi = sorted(abs(r["p14_sigma_away"]) for r in rows)[:: len(rows) - 1] if len(rows) > 1 else [abs(rows[0]["p14_sigma_away"])] * 2
    return f"{lo:.1f}σ" if f"{lo:.1f}" == f"{hi:.1f}" else f"{lo:.1f}–{hi:.1f}σ"


def _range_std(rows):
    vals = sorted(abs(r["standard_sigma_away"]) for r in rows)
    lo, hi = f"{vals[0]:.1f}", f"{vals[-1]:.1f}"
    return f"{lo}σ" if lo == hi else f"{lo}–{hi}σ"


def _inside(x, q):
    lo, hi = q["two_sigma_range"]
    return "inside" if lo <= x <= hi else "outside"


def _q(q):
    return (f"({q['q'] * 1e3:.2f} ± {q['sigma'] * 1e3:.2f})×10⁻³, or {q['two_sigma_range'][0] * 1e3:.2f}×10⁻³ < q < "
            f"{q['two_sigma_range'][1] * 1e3:.2f}×10⁻³ at 2σ").replace("-", "−")


def render_markdown(res):
    p, pub, val, wd = res["p14"], res["published"], res["validation"], res["what_would_decide"]
    comb, single = res["combined"], res["single_measurements"]
    thr = p["pass_needs_sigma_at_most"]
    cooke = "Cooke, Pettini & Steidel 2018"
    head = _find(pub, result=HEADLINE)
    gh = _find(pub, result="Goldstein & Hill 2026, LBT helium + deuterium")

    def d1(pred, meas=PRIMARY_DEUTERIUM, tr="as published"):
        return _find(single, element="D/H", measurement=meas, prediction=pred, baryon_density=tr)

    def c1(pred, meas=PRIMARY_DEUTERIUM, tr="as published"):
        return _find(comb, deuterium=meas, prediction=pred, baryon_density=tr)

    modern = (PRIMAT, GP, GP_SPA)
    d_mod = [d1(x) for x in modern]
    c_mod = [c1(x) for x in modern]
    c_mod_cooke = [c1(x, cooke) for x in modern]
    d_mod_w = [d1(x, tr="widened") for x in (PRIMAT, GP)]
    c_mod_w = [c1(x, tr="widened") for x in (PRIMAT, GP)]
    d_poly, c_poly = d1(POLY), c1(POLY)
    c_gp = c1(GP)
    po = res["inputs"]["poulin_2026"]
    lines = [
        "# P14 against primordial helium and deuterium",
        "",
        "<!-- GENERATED by analyses/p14_bbn_status.py from analyses/p14_bbn_status.json. Do not edit by hand. -->",
        "",
        "Diagnostic, not a scoring: every result here was published before P14 was registered, and none is a",
        f"determination of G itself. P14 predicts G/G0 = {p['G_over_G0_nucleosynthesis']:.4f} during nucleosynthesis "
        f"({p['G_over_G0_weak_freeze_out']:.4f} at the neutron–proton freeze-out); its",
        f"rule needs σ ≤ {thr:.4f} to tell it from G = G0. Code: [p14_bbn_status.py](p14_bbn_status.py); numbers:",
        "[p14_bbn_status.json](p14_bbn_status.json).",
        "",
        "## Answer",
        "",
        "**Helium: consistent with P14, a little closer to G = G0.** The LBT measurement (Aver et al. 2026), read as the",
        f"expansion rate during nucleosynthesis by Loverde, Saravanan & Weiner (2026), gives G/G0 = {_pm(head['G_over_G0'], head['sigma_toward_p14'])}: P14",
        f"is {_away(head)} away, G = G0 {abs(head['standard_sigma_away']):.1f}σ. Goldstein & Hill (2026), from helium and deuterium without the CMB,",
        f"find {_pm(gh['G_over_G0'], gh['sigma_toward_p14'])}. The EMPRESS helium, which favoured much weaker gravity, is not confirmed by LBT,",
        f"which is {wd['lbt_over_empress_precision']:.1f} times more precise.",
        "",
        f"**Deuterium: against P14.** P14 lowers D/H by {wd['p14_deuterium_shift_percent']:.1f}%. The standard prediction depends on how the",
        "measured deuterium-burning cross sections are fitted. Launders, Giovanetti & Liu (2026) fitted them with",
        "Gaussian processes, validated on mock data, and found that the low-degree polynomial fits used by Yeh, Olive &",
        f"Fields (2021) over-predict deuterium; here the polynomial prediction lies {wd['polynomial_over_gp_percent']:.1f}% above theirs at the same baryon",
        "density. Their result agrees with PRIMAT's, which takes the energy dependence from ab initio theory. With either,",
        f"and the PDG 2025 deuterium average, deuterium alone puts P14 {_range(d_mod)} away, around the 3σ line of its rule",
        f"(the upper end with the newest CMB baryon density, from Planck, ACT and SPT together). Only the polynomial fits",
        f"leave deuterium neutral ({_away(d_poly)}). Deuterium is also {_range_std(d_mod)} from G = G0, in the other direction: the",
        "measured abundance lies above the modern standard prediction. Widening the baryon density's error, as for a freely varying G at",
        f"recombination, brings the modern values to {_range(d_mod_w)}; P14's fixed 0.8% change at recombination implies",
        "something closer to the published error.",
        "",
        f"**Together**, helium and deuterium put P14 {_range(c_mod)} away with the modern rates ({_range(c_mod_cooke)} with Cooke et al.'s",
        f"deuterium instead of the PDG average; {_range(c_mod_w)} widened), and {_away(c_poly)} with the polynomial fits. Nothing",
        f"prefers P14: with the Gaussian-process rates, G = G0 fits the combined data {c_gp['likelihood_standard_over_p14']:.0f} times better. Poulin, Froustey, Pitrou",
        f"& Smith (2026) read the same deuterium as asking for a faster expansion while deuterium burns (ΔH/H = +{po['delta_H_over_H'][0]:.3f}),",
        "the opposite of P14's slower one.",
        "",
        "**What this means for P14.** Nothing here is scored: every result predates the registration, and none is a",
        "determination of G. P14's rule also fails it if a fit of its model to CMB, BAO and abundance data excludes the",
        f"registered q at 3σ or more. This diagnostic is not that fit, but it shows where such a fit would land today:",
        f"{_range(c_mod)} ({_range(c_mod_cooke)} with Cooke et al.'s deuterium), below the line but close to it. No new laboratory measurement of the deuterium-burning reactions",
        "has settled the rates; Launders et al. ask for d(d,n)³He and d(d,p)³H at 0.1–0.6 MeV. The registration missed these",
        "results; editorial flags on P14 record them.",
        "",
        "## Predicted abundances",
        "",
        "| Deuterium-burning rates | CMB baryon density | Standard Y_p | P14 Y_p | Standard D/H (10⁻⁵) | P14 D/H (10⁻⁵) |",
        "|---|---|---|---|---|---|",
    ]
    for r in res["predicted_abundances"]:
        y_note = "" if r["helium_from"] == r["prediction"] else "*"
        lines.append(f"| {r['prediction']} | {r['cmb']} ({r['omega_b']}) | {r['standard_Y_p']:.4f}{y_note} | {r['p14_Y_p']:.4f}{y_note} | "
                     f"{r['standard_D_H']:.3f} | {r['p14_D_H']:.3f} |")
    pr0 = res["predicted_abundances"][0]
    lines += [
        "",
        f"\\* Helium from {res['inputs']['helium_from']}: the Gaussian-process fits change only the deuterium-burning rates, to",
        "which helium is insensitive. All four use LUNA's d(p,γ)³He data. Slower expansion leaves more time: neutrons decay",
        "longer before they are locked into helium, and deuterium burns longer. With G at the freeze-out value for the whole",
        f"of helium's history, P14's Y_p would be lower by a further {abs(pr0['p14_Y_p'] - pr0['p14_Y_p_freeze_out_G']):.5f}.",
        "",
        "## Each measurement",
        "",
        "G/G0 and the signed distance in σ, with each prediction's published baryon density. Positive: the measurement",
        "lies below that value of G.",
        "",
        "| Measurement | Prediction | G/G0 | From P14 | From G = G0 |",
        "|---|---|---|---|---|",
    ]
    for r in single:
        if r["baryon_density"] == "as published":
            lines.append(f"| {r['element']}: {r['measurement']} | {r['prediction']} | {_pm(r['G_over_G0'], r['sigma'])} | "
                         f"{r['p14_sigma_away']:+.1f} | {r['standard_sigma_away']:+.1f} |")
    lines += [
        "",
        f"With the widened baryon density ({BARYON_G_FREE[0]} ± {BARYON_G_FREE[1]:.5f}), helium barely changes; deuterium loosens:",
        "",
        "| Deuterium measurement | Prediction | G/G0 | From P14 | From G = G0 |",
        "|---|---|---|---|---|",
    ]
    for r in single:
        if r["baryon_density"] == "widened" and r["element"] == "D/H":
            lines.append(f"| {r['measurement']} | {r['prediction']} | {_pm(r['G_over_G0'], r['sigma'])} | "
                         f"{r['p14_sigma_away']:+.1f} | {r['standard_sigma_away']:+.1f} |")
    lines += [
        "",
        "## Helium and deuterium together",
        "",
        "LBT helium with each deuterium measurement. \"He vs D\" is the tension between the helium and the deuterium values",
        "of G. The last column is P14's rule applied as if the result were a post-registration determination of G.",
        "",
        "| Deuterium | Prediction | Baryon density | G/G0 | From P14 | From G = G0 | He vs D | Rule |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in comb:
        lines.append(f"| {r['deuterium']} | {r['prediction']} | {r['baryon_density']} | {_pm(r['G_over_G0'], r['sigma'])} | "
                     f"{r['p14_sigma_away']:+.1f} | {r['standard_sigma_away']:+.1f} | {r['helium_vs_deuterium_sigma']:.1f}σ | "
                     f"{r['rule_if_it_counted']} |")
    lines += [
        "",
        "## Published determinations",
        "",
        "N_eff during nucleosynthesis is converted to G through the helium sensitivities "
        f"(ln G/G0 = {res['inputs']['g_per_n_eff']:.4f} × (N_eff − 3.044)).",
        "",
        "| Result | G/G0 | From P14 | From G = G0 | P14's rule, if it counted |",
        "|---|---|---|---|---|",
    ]
    for r in pub:
        lines.append(f"| {r['result']} ({r['ref']}) | {_pm(r['G_over_G0'], r['sigma_toward_p14'])} | {r['p14_sigma_away']:+.1f} | "
                     f"{r['standard_sigma_away']:+.1f} | {r['rule_if_it_counted']} |")
    d_gp = d1(GP)
    lines += [
        "",
        "## What the rule would say",
        "",
        "None of these results is scored: all predate the registration. They show how P14's rule reads evidence. PASS",
        "needs |z| < 3 and σ ≤ " f"{thr:.4f}, so it means \"not excluded by a measurement able to tell the two apart\", not \"preferred\":",
        "",
        f"- The LBT helium reading would score {head['rule_if_it_counted']} (|z| = {abs(head['p14_sigma_away']):.1f}, σ = {head['sigma_toward_p14']:.4f}), "
        f"although G = G0 fits it {head['likelihood_standard_over_p14']:.1f} times better.",
        f"- Helium and deuterium together, with the Gaussian-process rates, would score {c_gp['rule_if_it_counted']} "
        f"(|z| = {abs(c_gp['p14_sigma_away']):.1f}, σ = {c_gp['sigma']:.4f}), although",
        f"  G = G0 fits them {c_gp['likelihood_standard_over_p14']:.0f} times better.",
        f"- Deuterium alone, with the same rates, would score {d_gp['rule_if_it_counted']} (|z| = {abs(d_gp['p14_sigma_away']):.1f}); "
        f"with PRIMAT's, {d1(PRIMAT)['rule_if_it_counted']} (|z| = {abs(d1(PRIMAT)['p14_sigma_away']):.2f});",
        f"  with the Planck+ACT+SPT baryon density, {d1(GP_SPA)['rule_if_it_counted']} (|z| = {abs(d1(GP_SPA)['p14_sigma_away']):.1f}).",
        "",
        "Reports on P14 therefore give both distances.",
        "",
        f"In terms of P14's parameter, the LBT helium alone gives q = {_q(res['q']['from_lbt_helium'])}; with deuterium",
        f"(Gaussian-process rates, PDG average), q = {_q(res['q']['from_helium_and_deuterium'])}. The registration quoted",
        f"−1.4×10⁻³ < q < 1.8×10⁻³. The registered q = {p['q_registered'] * 1e3:.3f}×10⁻³ is "
        f"{_inside(p['q_registered'], res['q']['from_lbt_helium'])} the first range and "
        f"{_inside(p['q_registered'], res['q']['from_helium_and_deuterium'])} the second.",
        "",
        "## What would decide it",
        "",
        "- **Deuterium-burning cross sections**, d(d,n)³He and d(d,p)³H, measured at 0.1–0.6 MeV. They set the nuclear part",
        f"  of the deuterium prediction's error ({wd['gp_nuclear_error_percent']:.1f}% with Gaussian processes), against P14's "
        f"{wd['p14_deuterium_shift_percent']:.1f}% shift.",
        f"- **Helium** measured to ±{wd['helium_error_for_3sigma_separation']:.4f} (LBT: ±{wd['lbt_helium_error']:.4f}) would separate P14 from "
        "G = G0 at 3σ on its own:",
        f"  P14 lowers Y_p by {wd['p14_helium_shift']:.4f}, and the prediction error is ±{wd['helium_prediction_error']:.4f}. "
        f"P14's rule precision corresponds to ±{wd['helium_error_for_rule_precision']:.4f}.",
        "- **A CMB fit of P14's model**, with G = 0.992 at recombination, to fix the baryon density it implies.",
        "- **A published determination of G during nucleosynthesis** after the registration, from an analysis that lets it",
        "  differ from today's: that is what P14's rule scores.",
        "",
        "## Checks",
        "",
        f"- Alvey et al.'s inputs give G/G0 = {val['alvey_2020_reproduced']['G_over_G0']:.3f} ± "
        f"{val['alvey_2020_reproduced']['two_sigma']:.3f} (2σ) by this method; they published "
        f"{val['alvey_2020_reproduced']['published']['G_over_G0']} +{val['alvey_2020_reproduced']['published']['two_sigma_up']}/−"
        f"{val['alvey_2020_reproduced']['published']['two_sigma_down']}",
        "  with a full nucleosynthesis code.",
        "- The LBT helium three ways: directly with Yeh et al.'s prediction, "
        f"{_pm(val['lbt_helium_three_ways']['direct_yeh_2021']['G_over_G0'], val['lbt_helium_three_ways']['direct_yeh_2021']['sigma'])};",
        "  through Loverde et al.'s N_eff with the helium conversion, "
        f"{_pm(val['lbt_helium_three_ways']['loverde_n_eff_helium_slope']['G_over_G0'], val['lbt_helium_three_ways']['loverde_n_eff_helium_slope']['sigma'])};",
        "  with radiation counting before electron–positron annihilation (7/43), "
        f"{_pm(val['lbt_helium_three_ways']['loverde_n_eff_radiation_slope']['G_over_G0'], val['lbt_helium_three_ways']['loverde_n_eff_radiation_slope']['sigma'])}.",
        "",
        "## Limits",
        "",
        "- Linear in the logarithms: accurate for changes of a few percent, as here.",
        "- The sensitivities to G come from one code (Fields et al.) and are applied to every prediction; the expansion-rate",
        "  physics is the same in all.",
        "- \"As published\" ignores P14's 0.8% change of G at recombination; \"widened\" covers any change there, so it",
        "  overstates the error for a model in which the change is fixed. Deuterium depends on the difference (a 1% shift in",
        "  the baryon density moves D/H by 1.6%); helium barely does.",
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
            print("DIFFERS: p14_bbn_status.md is not the rendering of p14_bbn_status.json")
        ok = not problems and md_current
        print("P14 BBN status reproduces its committed output" if ok else "P14 BBN status does NOT reproduce its committed output")
        return 0 if ok else 1
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(res), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
