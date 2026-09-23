#!/usr/bin/env python3
"""ccbh_fit.py — DIAGNOSTIC: cosmologically coupled black holes as dark energy (not a registered prediction).

Why this is here. The second published attempt to replace dark energy with
gravity (OPEN_PROBLEMS.md, problem 10). Black holes whose interiors are regions
of vacuum energy can grow with the expansion, m ∝ a^k; for k = 3 a population
of them keeps a constant physical density and acts in aggregate like a
cosmological constant. Dark energy then grows as massive stars collapse into
such black holes, consuming baryons (Farrah et al., ApJL 944, L31, 2023;
Croker et al., JCAP 10 (2024) 094; Ahlen et al., PRL 135, 081003, 2025).

Model (Ahlen et al. 2025, eqs. 1-3, k = 3). With psi the comoving star-formation
rate density, star formation starting at a_i = 1/20, and X one conversion
constant fixed by flatness:
  omega_b(a) a^3 = omega_b_proj - X S(a),   S = ∫_{a_i}^a psi da'/(H a')
  omega_DE(a)    = X D(a),                  D = ∫_{a_i}^a psi da'/(H a'^4)
so each unit of baryon density lost at formation reappears as dark energy.
omega_b_proj is the baryon density the early universe (CMB, nucleosynthesis)
implies; the early universe is standard, so the CMB distance priors and the
sound horizon apply unchanged, and the model has the same free parameters as
ΛCDM. Star formation: Madau & Dickinson (ARA&A 52, 415, 2014, eq. 15) and Madau
& Fragos (ApJ 840, 39, 2017, eq. 1), the "Madau psi" family of Ahlen et al.

Test. The same CMB + BAO fit as analyses/joint_fit.py (Planck 2018 distance
priors, DESI DR2 BAO), with Ahlen et al.'s published results as the reference.
Their JWST-based star-formation history (Trinca et al.) is a semi-analytic model
without a closed form and is not reproduced here.

Deterministic, standard library only. Writes analyses/ccbh_fit.json and
analyses/ccbh_fit.md; `--check` recomputes and compares with tolerance.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import joint_fit as jf  # noqa: E402

OUT_JSON = HERE / "ccbh_fit.json"
OUT_MD = HERE / "ccbh_fit.md"
A_I = 1.0 / 20.0
AHLEN_2025_MADAU = {"H0": (70.03, 0.40), "baryon_survival": 0.50, "delta_chi2": 6.1,
                    "note": "DESI DR2 + Planck PR4 full likelihood, summed neutrino mass free"}
AHLEN_2025_TRINCA = {"H0": (69.37, 0.36), "baryon_survival": 0.74, "delta_chi2": 0.7}


def sfrd_md14(z):
    return 0.015 * (1.0 + z) ** 2.7 / (1.0 + ((1.0 + z) / 2.9) ** 5.6)


def sfrd_mf17(z):
    return 0.01 * (1.0 + z) ** 2.6 / (1.0 + ((1.0 + z) / 3.2) ** 6.2)


class CCBH(jf.LCDM):
    """k = 3 coupled black holes; flat; the early universe is ΛCDM without Λ."""
    name = "ccbh"
    SFRD = staticmethod(sfrd_md14)
    N_STEPS = 600

    def __init__(self, h, omega_b, omega_c, q=0.0):
        super().__init__(h, omega_b, omega_c, q)
        self.w_r = self.Or * h * h
        self.w_m = self.omega_m                         # early (projected) matter density
        self._u0, self._du = math.log(A_I), -math.log(A_I) / self.N_STEPS
        self._solve()

    def _h2(self, a, s, d, x):
        return self.w_r / a ** 4 + (self.w_m - x * s) / a ** 3 + x * d

    def _integrate(self, x):
        """RK4 in u = ln a for S and D; returns the tables at every step."""
        def deriv(u, s, d):
            a = math.exp(u)
            hh = math.sqrt(self._h2(a, s, d, x))
            psi = self.SFRD(1.0 / a - 1.0)
            return psi / hh, psi / (hh * a ** 3)
        s = d = 0.0
        ss, ds = [0.0], [0.0]
        du = self._du
        for i in range(self.N_STEPS):
            u = self._u0 + i * du
            k1 = deriv(u, s, d)
            k2 = deriv(u + du / 2, s + du / 2 * k1[0], d + du / 2 * k1[1])
            k3 = deriv(u + du / 2, s + du / 2 * k2[0], d + du / 2 * k2[1])
            k4 = deriv(u + du, s + du * k3[0], d + du * k3[1])
            s += du / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            d += du / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            ss.append(s)
            ds.append(d)
        return ss, ds

    def _solve(self):
        target = self.h * self.h - self.w_r - self.w_m      # today's dark-energy density
        if target <= 0:
            raise ValueError("no room for dark energy")
        x = target / 50.0
        for _ in range(60):
            ss, ds = self._integrate(x)
            x_new = target / (ds[-1] - ss[-1])
            if abs(x_new - x) <= 1e-13 * x:
                x = x_new
                break
            x = x_new
        self.X, self._ss, self._ds = x, ss, ds
        self.omega_b_today = self.omega_b - x * ss[-1]
        self.baryon_survival = self.omega_b_today / self.omega_b

    def _sd(self, a):
        pos = (math.log(a) - self._u0) / self._du
        i = min(int(pos), self.N_STEPS - 1)
        f = pos - i
        return (self._ss[i] + f * (self._ss[i + 1] - self._ss[i]),
                self._ds[i] + f * (self._ds[i + 1] - self._ds[i]))

    def HE(self, zE):
        a = 1.0 / (1.0 + zE)
        if a <= A_I:
            return 100.0 * math.sqrt(self.w_r / a ** 4 + self.w_m / a ** 3)
        s, d = self._sd(a)
        return 100.0 * math.sqrt(self._h2(a, s, d, self.X))

    def w_eff(self, z):
        """Effective dark-energy equation of state, -1 - (1/3) dln rho_DE / dln a."""
        a = 1.0 / (1.0 + z)
        s, d = self._sd(a)
        hh = math.sqrt(self._h2(a, s, d, self.X))
        return -1.0 - self.SFRD(z) / (3.0 * hh * a ** 3 * d)


class CCBH_MF17(CCBH):
    name = "ccbh_mf17"
    SFRD = staticmethod(sfrd_mf17)


jf.MODELS.update({CCBH.name: CCBH, CCBH_MF17.name: CCBH_MF17})


def validate():
    m = CCBH(0.70, 0.0224, 0.119)
    s1, d1 = m._ss[-1], m._ds[-1]
    return {
        "closure_H0_today": m.HE(0.0) / 100.0 - m.h,
        "no_dark_energy_before_star_formation": m.HE(25.0) - 100.0 * math.sqrt(m.w_r * 26.0 ** 4 + m.w_m * 26.0 ** 3),
        "dark_energy_density_today_over_baryon_loss_comoving": d1 / s1,
        "w_eff_during_production_z3": m.w_eff(3.0),
        "w_eff_today": m.w_eff(0.0),
        "step_convergence_H_at_z1": m.HE(1.0) - type("Fine", (CCBH,), {"N_STEPS": 2400})(0.70, 0.0224, 0.119).HE(1.0),
    }


def analyse():
    data = jf.load_data()
    lcdm = jf.fit("lcdm", 0.0, data)
    lcdm_model = jf.LCDM(lcdm["h"], lcdm["omega_b"], lcdm["omega_c"])
    out = {}
    for name, label in ((CCBH.name, "Madau & Dickinson 2014"), (CCBH_MF17.name, "Madau & Fragos 2017")):
        r = jf.fit(name, 0.0, data, start=(0.70, lcdm["omega_b"], lcdm["omega_c"]))
        m = jf.MODELS[name](r["h"], r["omega_b"], r["omega_c"])
        out[name] = {
            "star_formation_history": label, "H0": m.H0, "omega_b_early": m.omega_b, "omega_c": m.omega_c,
            "chi2": r["chi2"], "delta_chi2_vs_lcdm": r["chi2"] - lcdm["chi2"],
            "chi2_cmb": jf.chi2_cmb(m, data), "chi2_bao": jf.chi2_bao(m, data),
            "baryon_survival_fraction": m.baryon_survival,
            "w_eff": [{"z": z, "w": m.w_eff(z)} for z in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0)],
        }
    return {"tool": "ccbh_fit.py",
            "status": "DIAGNOSTIC — cosmologically coupled black holes against CMB + BAO; not a registered prediction",
            "sources": {"model": "Ahlen et al., PRL 135, 081003 (2025), eqs. 1-3",
                        "star_formation": "Madau & Dickinson 2014 eq. 15; Madau & Fragos 2017 eq. 1",
                        "data": "Planck 2018 distance priors; DESI DR2 BAO (as analyses/joint_fit.py)"},
            "validation": validate(),
            "lcdm": {"H0": lcdm_model.H0, "chi2": lcdm["chi2"]},
            "fits": out,
            "published_reference": {"madau_psi": AHLEN_2025_MADAU, "trinca_psi": AHLEN_2025_TRINCA}}


def render_markdown(res):
    v, f, ref = res["validation"], res["fits"], res["published_reference"]
    lines = [
        "# Cosmologically coupled black holes against CMB + BAO",
        "",
        "<!-- GENERATED by analyses/ccbh_fit.py from analyses/ccbh_fit.json. Do not edit by hand. -->",
        "",
        "Diagnostic, not a registered prediction. Black holes whose mass grows with the expansion (m ∝ a³) act in",
        "aggregate like a cosmological constant; dark energy then grows as stars collapse into them, consuming baryons.",
        "Model: Ahlen et al., PRL 135, 081003 (2025). Data: Planck 2018 distance priors and DESI DR2 BAO, as in",
        "[joint_fit.md](joint_fit.md). Code: [ccbh_fit.py](ccbh_fit.py); numbers: [ccbh_fit.json](ccbh_fit.json).",
        "",
        "## Checks of the implementation",
        "",
        "| Check | Value | Expected |",
        "|---|---|---|",
        f"| H0 from the solution minus the input h | {v['closure_H0_today']:.1e} | 0 (flatness closes) |",
        f"| Expansion rate before star formation minus matter + radiation only | {v['no_dark_energy_before_star_formation']:.1e} | 0 (no dark energy yet) |",
        f"| Dark energy today per unit of baryon mass lost | {v['dark_energy_density_today_over_baryon_loss_comoving']:.1f} | ≫ 1 (each black hole grew with the expansion) |",
        f"| w_eff at z = 3, during black-hole production | {v['w_eff_during_production_z3']:.3f} | < −1 (density growing) |",
        f"| Step-size convergence of H at z = 1 | {v['step_convergence_H_at_z1']:.1e} km/s/Mpc | ≈ 0 |",
        "",
        "## Fits",
        "",
        "Both models have the same three free parameters (h, ω_b, ω_c); in the black-hole model the dark-energy density",
        "is fixed by flatness, not free. 3 CMB + 13 BAO data points.",
        "",
        "| Model | H0 | χ² | Δχ² vs ΛCDM | Baryons left today |",
        "|---|---|---|---|---|",
        f"| ΛCDM | {res['lcdm']['H0']:.2f} | {res['lcdm']['chi2']:.2f} | 0 | all |",
    ]
    for name in ("ccbh", "ccbh_mf17"):
        r = f[name]
        lines.append(f"| Black holes, {r['star_formation_history']} | {r['H0']:.2f} | {r['chi2']:.2f} | "
                     f"{r['delta_chi2_vs_lcdm']:+.2f} | {100 * r['baryon_survival_fraction']:.0f}% |")
    m = ref["madau_psi"]
    t = ref["trinca_psi"]
    lines += ["",
              "**Published reference** (Ahlen et al. 2025, full Planck PR4 likelihood, neutrino mass free): with the Madau",
              f"star-formation history H0 = {m['H0'][0]} ± {m['H0'][1]}, baryons left {100 * m['baryon_survival']:.0f}%, Δχ² = +{m['delta_chi2']};",
              f"with the JWST-based Trinca history H0 = {t['H0'][0]} ± {t['H0'][1]}, baryons left {100 * t['baryon_survival']:.0f}%, Δχ² = +{t['delta_chi2']}.",
              "",
              "## The effective dark-energy equation of state", "",
              "| z | " + " | ".join(f"{w['z']}" for w in f["ccbh"]["w_eff"]) + " |",
              "|---|" + "---|" * len(f["ccbh"]["w_eff"])]
    for name in ("ccbh", "ccbh_mf17"):
        lines.append(f"| {f[name]['star_formation_history']} | " + " | ".join(f"{w['w']:.3f}" for w in f[name]["w_eff"]) + " |")
    lines += ["", "w below −1 means the dark-energy density is growing, as black holes form; it returns towards −1 as star",
              "formation declines.", "",
              "## Limits", "",
              "- Compressed CMB priors and a fixed neutrino mass of 0.06 eV, where the published analysis uses the full Planck",
              "  likelihood and a free neutrino mass; the comparison with it is approximate.",
              "- The JWST-based star-formation history that fits best in the published analysis is not reproduced.",
              "- This tests the expansion history only. Whether individual black holes grow as a³ is tested by local",
              "  observations, recorded in OPEN_PROBLEMS.md, problem 10.", ""]
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
            print("DIFFERS: ccbh_fit.md is not the rendering of ccbh_fit.json")
        ok = not problems and md_current
        print("black-hole fit reproduces its committed output" if ok else "black-hole fit does NOT reproduce its committed output")
        return 0 if ok else 1
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(res), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(HERE.parent)} and {OUT_MD.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
