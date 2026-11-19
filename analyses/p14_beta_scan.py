#!/usr/bin/env python3
"""Scan the early scalar coupling at the registered P14 drift and transition."""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joint_fit as jf
import p14_bbn_status as status
import p14_network as bbn
import p14_physical_model as model
import timescape_fit as bao

OUTPUT = HERE / "p14_beta_scan.json"
REPORT = OUTPUT.with_suffix(".md")
H_TEMPS = (1., .1, .03)  # atomic MeV
# Gómez-Valent et al., smooth component around decoupling, data-set dependent.
FRACTION_LIMITS = (.006, .004)
BETA_MIN, BETA_MAX = .001, 1.


class LateBranch:
    def __init__(self, cm, k2):
        self.cm = cm
        self.k2 = k2

    def e(self, z):
        return math.sqrt(self.cm * (1+z)**3 + (1-self.cm) * (1+z)**self.k2)

    def h0_dm(self, z):
        return jf.simpson(lambda x: 1/self.e(x), 0., z, 128)


def fit_bao(k2, data):
    """Minimize in C_m with the common distance scale profiled analytically."""
    def fit(cm):
        return bao.chi2_bao_scale_free(LateBranch(cm, k2), data)

    lo, hi = 0., 1.
    for _ in range(45):
        left, right = (2*lo + hi)/3, (lo + 2*hi)/3
        if fit(left)[0] < fit(right)[0]:
            hi = right
        else:
            lo = left
    cm = (lo + hi)/2
    chi2, scale = fit(cm)
    return {"C_m": cm, "H0_rd_km_s": jf.C/scale, "chi2": chi2}


def scalar_fraction(background, t, matter):
    # history reports U/radiation. Dust also enters the total at recombination.
    field = background[t][3] * matter.radiation
    return field / (matter.rho + field)


def beta_at_fraction(limit, q, zt, t_star, matter_star):
    def fraction(beta):
        history, _ = model.history([t_star], q, zt, beta)
        return scalar_fraction(history, t_star, matter_star)

    lo, hi = BETA_MIN, BETA_MAX
    if not fraction(hi) < limit < fraction(lo):
        raise ValueError("Recombination fraction crossing outside the beta scan")
    for _ in range(34):
        mid = math.sqrt(lo*hi)
        if fraction(mid) > limit:
            lo = mid
        else:
            hi = mid
    return hi


def analyse():
    params = json.loads(status.P14_OUTPUT.read_text())["registered_parameters"]
    q, zt = params["q"], params["z_transition"]
    cancel = json.loads(model.OUTPUT.read_text())["alternative_coupling"]["beta"]
    t_star = model.T0 * (1 + jf.Z_STAR_PLANCK)  # observed redshift, after pair annihilation
    nt = -math.log1p(zt)
    matter_star = model.matter(t_star, q, nt)
    bounds = [{"omega_phi_max": limit, "beta_min": beta_at_fraction(limit, q, zt, t_star, matter_star)}
              for limit in FRACTION_LIMITS]
    betas = {10**(-3 + i/8) for i in range(25)}
    betas.update([cancel, .008, .01, .02, *(bound["beta_min"] for bound in bounds)])

    temps = bbn.temperatures(model.STEPS)
    sample = sorted(set(temps).union(H_TEMPS, [t_star]))
    standard = bbn.integrate(temps, [model.matter(t, 0., nt).h_std for t in temps])
    data = model.measurements(status.GP, "as published", status.PRIMARY_HELIUM, status.PRIMARY_DEUTERIUM)
    standard_fit = model.likelihood(data, {el: 1. for el in model.ELEMENTS})
    bao_data = bao.load_bao()
    bao_null = fit_bao(0., bao_data)
    # After annihilation, rho_rad/rho_one_neutrino includes the photons.
    rad_per_nu = status.N_EFF_SM + (8/7)*(11/4)**(4/3)
    # SPT-3G D1 Table 5, CMB-SPA with helium free (mean, upper and lower errors).
    spt_neff = (2.96, .21, .24)
    delta_upper = spt_neff[0] + 2*spt_neff[1] - status.N_EFF_SM
    spt_beta = abs(q)/math.sqrt(4*delta_upper/(rad_per_nu + delta_upper))
    rows = []
    for beta in sorted(betas):
        k2 = (q/beta)**2
        history, _ = model.history(sample, q, zt, beta)
        yields = bbn.integrate(temps, [history[t][0] for t in temps])
        ratios = {el: yields[el]/standard[el] for el in model.ELEMENTS}
        abundances = model.likelihood(data, ratios)
        lr = math.exp((abundances["chi2"] - standard_fit["chi2"])/2)
        fit = fit_bao(k2, bao_data)
        rad_fraction = k2/4
        rows.append({
            "beta": beta, "k": math.sqrt(k2),
            "H_atomic_over_standard": {f"{t:g}": history[t][0]/history[t][1] for t in H_TEMPS},
            "omega_phi_recombination": scalar_fraction(history, t_star, matter_star),
            "omega_phi_radiation": rad_fraction,
            "delta_N_eff_energy": rad_per_nu * rad_fraction / (1-rad_fraction),
            "w_phi_today": -1 + k2/(3*model.DARK0/model.CRITICAL),
            "network_ratios": ratios, "signed_sigma": abundances["signed_sigma"],
            "abundance_chi2": abundances["chi2"], "likelihood_standard_over_model": lr,
            "bao": {**fit, "delta_chi2_vs_k0": fit["chi2"] - bao_null["chi2"]},
        })
    for bound in bounds:
        accepted = [r["likelihood_standard_over_model"] for r in rows if r["beta"] >= bound["beta_min"]]
        bound["likelihood_range"] = [min(accepted), max(accepted)]

    return {
        "q": q, "z_transition": zt, "z_recombination": jf.Z_STAR_PLANCK, "cancelling_beta": cancel,
        "temperature_MeV": H_TEMPS, "N_eff_standard": status.N_EFF_SM,
        "network_steps": model.STEPS, "omega_b": bbn.OMEGA_B, "rates": status.GP,
        "baryon_density": "as published", "helium": status.PRIMARY_HELIUM, "deuterium": status.PRIMARY_DEUTERIUM,
        "standard_abundance_chi2": standard_fit["chi2"], "bao_k0": bao_null,
        "smooth_fraction_translations": bounds,
        "external_comparisons": {"da_fonseca_k_68": .056, "goh_beta_68": .026,
                                 "spt_free_helium_N_eff": spt_neff, "spt_energy_only_beta_min": spt_beta},
        "rows": rows,
    }


def render_markdown(r):
    rows = r["rows"]
    by_beta = {row["beta"]: row for row in rows}
    cancel = by_beta[r["cancelling_beta"]]
    unit = rows[-1]
    ext = r["external_comparisons"]
    lines = [
        "<!-- GENERATED by analyses/p14_beta_scan.py from analyses/p14_beta_scan.json. Do not edit by hand. -->",
        "",
        "# What fixes the P14 coupling?",
        "",
        f"At fixed q = {r['q']:g} and z_t = {r['z_transition']:g}, a smaller early coupling β requires a faster "
        "field, k = |q|/β. The extra field energy can offset the slower atomic expansion during nucleosynthesis. "
        "The same field is still present at recombination, where its effect on the CMB peaks offers an independent test.",
        "",
        f"At β = {cancel['beta']:.8f}, H_atomic/H_std at {r['temperature_MeV'][1]:g} MeV is "
        f"{cancel['H_atomic_over_standard']['0.1']:.5f}, yet the scalar carries {cancel['omega_phi_recombination']:.2%} "
        f"of the energy at z = {r['z_recombination']}. At β = {unit['beta']:g} these values are "
        f"{unit['H_atomic_over_standard']['0.1']:.5f} and {unit['omega_phi_recombination']:.4%}.",
        "",
        "## Which couplings pass the smooth-fraction comparison?",
        "",
        "Gómez-Valent et al. give approximate two-sigma upper limits for a smooth component around decoupling. "
        "The limit depends on the data combination. Each row applies one published limit to the P14 background "
        "and evaluates the abundance likelihood from that crossing to the top of the scan. "
        "These are translations of related models. P14 has no fitted CMB confidence interval here. "
        "[Gómez-Valent et al.](https://arxiv.org/abs/2107.11065)",
        "",
        "| Upper Ωφ at recombination | β passing within scan | L(standard)/L(P14), helium + deuterium |",
        "|---:|---:|---:|",
    ]
    for bound in r["smooth_fraction_translations"]:
        low, high = bound["likelihood_range"]
        lines.append(f"| {bound['omega_phi_max']:.1%} | {bound['beta_min']:.5f}–{unit['beta']:g} | {low:.1f}–{high:.1f} |")
    lines += [
        "",
        f"Both comparisons put cancellation below the indicated β range. At β = {by_beta[.01]['beta']:g} "
        f"and {by_beta[.02]['beta']:g}, standard expansion fits the abundances "
        f"{by_beta[.01]['likelihood_standard_over_model']:.1f} and "
        f"{by_beta[.02]['likelihood_standard_over_model']:.1f} times better. Choosing β to remove the deuterium "
        "discrepancy would use up deuterium as an independent test. The project rule requires the mechanism "
        "to be fixed before seeing the discrepancy. These likelihood ratios do not score P14.",
        "",
        f"Da Fonseca et al. find k < {ext['da_fonseca_k_68']:g} at 68% for a constant field velocity. At fixed q "
        f"this would imply β > {abs(r['q'])/ext['da_fonseca_k_68']:.4f}. Their coupling acts only on cold dark "
        "matter and persists today. [da Fonseca et al.](https://arxiv.org/abs/2104.14889)",
        "",
        f"Goh et al. find a pre-recombination coupling below {ext['goh_beta_68']:g} at 68% in their binned "
        "cold-dark-matter model. Growth and lensing can therefore probe larger couplings. Transferring that "
        "upper bound to P14 would require its baryon coupling and switch-off in the perturbation equations. "
        "[Goh et al.](https://arxiv.org/abs/2211.13588)",
        "",
        f"SPT, Planck and ACT give N_eff = {ext['spt_free_helium_N_eff'][0]:g} "
        f"(+{ext['spt_free_helium_N_eff'][1]:g}, −{ext['spt_free_helium_N_eff'][2]:g}) with helium free. "
        f"At cancellation the field adds the energy equivalent of ΔN_eff = {cancel['delta_N_eff_energy']:.3f} "
        "after pair annihilation. Matching the approximate upper two-sigma endpoint by energy alone gives "
        f"β ≳ {ext['spt_energy_only_beta_min']:.4f}, which admits cancellation. "
        "A smooth scalar and free-streaming neutrinos drive different perturbations, "
        "so energy matching alone gives no P14 likelihood. [SPT-3G D1](https://arxiv.org/abs/2506.20707)",
        "",
        "## Expansion and field energy",
        "",
        "The background uses the conserving scalar history at fixed atomic temperature. At recombination, "
        "Ωφ = U/(B+U) includes matter and radiation in B. In pure radiation domination Ωφ = k²/4. "
        "ΔN_eff divides the field energy on this attractor by the energy of one neutrino species "
        f"after pair annihilation, with standard N_eff = {r['N_eff_standard']}. "
        "Today the kinetic energy gives wφ = −1 + k²/(3Ωφ₀).",
        "",
        "| β | " + " | ".join(f"H/H_std ({t:g} MeV)" for t in r["temperature_MeV"]) +
        " | Ωφ(z*) % | Ωφ(rad) % | ΔN_eff | wφ today |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        h = row["H_atomic_over_standard"]
        lines.append(f"| {row['beta']:.7g} | " + " | ".join(f"{h[f'{t:g}']:.5f}" for t in r["temperature_MeV"]) +
                     f" | {100*row['omega_phi_recombination']:.5g} | {100*row['omega_phi_radiation']:.5g} "
                     f"| {row['delta_N_eff_energy']:.4g} | {row['w_phi_today']:.8f} |")
    lines += [
        "",
        "## Abundances and late expansion",
        "",
        f"Each yield ratio divides a network run by its standard-expansion run at ω_b = {r['omega_b']}. "
        "We apply those ratios to the published Planck Gaussian-process deuterium and PRIMAT helium predictions. "
        "The signed distances from LBT helium and PDG deuterium use the same errors and shared baryon-density "
        "covariance as the P14 abundance analysis. Negative distances mean the predicted abundance is low. "
        "[Abundance inputs](p14_bbn_status.md) · [Network and validation](p14_physical_model.md)",
        "",
        "For DESI DR2 BAO alone we use E²(z) = C_m(1+z)³ + (1−C_m)(1+z)^(k²), neglecting late radiation. "
        "We profile C_m and H₀r_d independently at each β, retaining the within-bin distance covariances. "
        f"The reference fit at k = 0 gives χ² = {r['bao_k0']['chi2']:.2f}. At cancellation it is "
        f"{cancel['bao']['chi2']:.2f}. BAO alone admits cancellation. "
        "[DESI DR2 measurements](../data/desi_dr2_bao.csv)",
        "",
        "| β | Yₚ ratio | D/H ratio | LBT (σ) | PDG (σ) | L(standard)/L(P14) | BAO Δχ² vs k=0 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        yields, pulls = row["network_ratios"], row["signed_sigma"]
        lines.append(f"| {row['beta']:.7g} | {yields['Y_p']:.6f} | {yields['D/H']:.6f} "
                     f"| {pulls['Y_p']:+.2f} | {pulls['D/H']:+.2f} | {row['likelihood_standard_over_model']:.4g} "
                     f"| {row['bao']['delta_chi2_vs_k0']:+.4g} |")
    lines += [
        "",
        "**The missing calculation** is a CLASS/Cobaya fit of the coupled scalar, baryon and cold-dark-matter "
        "perturbations to Planck/ACT spectra and lensing plus DESI. Profile β with free ω_b and helium, "
        "reconstruct the potential at each trial cosmology, and compute recombination in atomic units. "
        "This would test cancellation independently of deuterium and supply the baryon density for its abundance test.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = jf._round(analyse(), digits=10)
    if args.check:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        problems = jf._compare(result, saved)
        if REPORT.read_text(encoding="utf-8") != render_markdown(saved):
            problems.append("Markdown differs from the JSON rendering")
        for problem in problems[:10]:
            print("DIFFERS", problem)
        print("P14 beta scan " + ("differs" if problems else "reproduces its output"))
        return int(bool(problems))
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    REPORT.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT.name} and {REPORT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
