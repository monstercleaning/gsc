#!/usr/bin/env python3
"""A conserving scalar completion of P14 and its differential nucleosynthesis likelihood."""
import argparse
import bisect
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joint_fit as jf
import p14_bbn_status as status
import p14_network as bbn

OUTPUT = HERE / "p14_physical_model.json"
REPORT = OUTPUT.with_suffix(".md")
T0 = jf.T_CMB * 8.617333262e-11
PLANCK = jf.PLANCK2018_TTTEEE_LOWE
STEPS = 4800
ELEMENTS = ("Y_p", "D/H")
H_UNIT = math.sqrt(8*math.pi/3)/bbn.MPL/bbn.HBAR  # sqrt(MeV^4) to s^-1
CRITICAL = (100*PLANCK["h"]/3.08567758149e19/H_UNIT)**2
OMEGA_M = bbn.OMEGA_B + PLANCK["omega_c"]  # baryons and CDM; massless neutrino background
DUST0 = CRITICAL*OMEGA_M/PLANCK["h"]**2
DARK0 = CRITICAL-DUST0-bbn.plasma(T0).rho


class ThermalState(NamedTuple):
    log_a: float
    radiation: float
    dust: float
    trace: float
    cooling: float


@lru_cache(None)
def thermal(t):
    plasma = bbn.plasma(t)
    a = (T0/t)*(2/plasma.entropy_dof)**(1/3)
    dust = DUST0/a**3
    return ThermalState(math.log(a),plasma.rho,dust,dust+plasma.trace,plasma.cooling)


class State(NamedTuple):
    A: float
    rho: float  # material stress-energy in Einstein units, including thermal species
    trace: float
    radiation: float
    cooling: float
    h_std: float


def matter(t, q, nt):
    log_a,rad,dust,trace,cooling = thermal(t)
    A = math.exp(q/(1+q)*min(log_a-nt,0.))
    return State(A,A**4*(rad+dust),A**4*trace,A**4*rad,cooling,H_UNIT*math.sqrt(rad+dust+DARK0))


def history(temps, q, zt, beta=1.):
    """Integrate the reconstructed field density from today, splitting at the kink.

    With N=ln a_E, dphi/dN=M |q|/beta everywhere. U'= -k^2(U+B)-s*trace.
    The independent first-law check uses the *total* density difference and
    a Simpson quadrature of the total enthalpy on each finite interval.
    """
    nt = -math.log1p(zt)
    transition = T0*(1+zt)
    # Keep the kink on a cell boundary. Reporting and network grids can place
    # the same temperature a few ulps apart. Merge those cells before taking
    # finite differences of the independently evaluated material densities.
    grid = [T0]
    aliases = {}
    for target in sorted(set([transition, *temps])):
        span = math.log(target/grid[-1])
        if span < 1e-8:
            aliases[target] = grid[-1]
            continue
        subdivisions = math.ceil(span/.004)
        left = grid[-1]
        grid.extend(left*math.exp(span*i/subdivisions) for i in range(1, subdivisions))
        grid.append(target)
    k2 = (q/beta)**2
    u = DARK0
    start = matter(T0,q,nt)
    output = {}
    residual = at_kink = 0.
    for t1,t2 in zip(grid,grid[1:]):
        mid = math.sqrt(t1*t2)
        s = q if mid > transition else 0.
        dx = math.log(t2/t1)
        middle,end = matter(mid,q,nt),matter(t2,q,nt)

        def slope(m, field):
            return m.cooling/(1+s)*(k2*(m.rho+field)+s*m.trace)

        l1 = slope(start,u)
        l2 = slope(middle,u+dx*l1/2)
        l3 = slope(middle,u+dx*l2/2)
        l4 = slope(end,u+dx*l3)
        new = u+dx*(l1+2*l2+2*l3+l4)/6

        def enthalpy(m, field):
            return m.cooling/(1+s)*(4*m.rho-m.trace+k2*(m.rho+field))

        # Cubic Hermite midpoint for U, independent of the source used for B.
        umid = (u+new)/2 + dx*(l1-slope(end,new))/8
        work = dx/6*(enthalpy(start,u)+4*enthalpy(middle,umid)+enthalpy(end,new))
        err = abs((end.rho-start.rho)+(new-u)-work)/work
        residual = max(residual,err)
        if transition in (t1,t2):
            at_kink = max(at_kink,err)
        kinetic = k2*(end.rho+new)/6
        h = (1+(q if t2>transition else 0.))*H_UNIT*math.sqrt(end.rho+new)/end.A
        output[t2] = (h,end.h_std,end.A,new/end.radiation,kinetic/end.radiation)
        start,u = end,new
    for target, source in aliases.items():
        output[target] = output[source]
    return output, {"max_cell":residual,"adjacent_to_transition":at_kink}


def validate(temps, standard_h):
    standard = bbn.integrate(temps,standard_h)
    delta = .01
    runs = [bbn.integrate(temps,[h*math.exp(d/2) for h in standard_h]) for d in (-delta,delta)]
    rows = {}
    for el,code,unit,tol in zip(ELEMENTS,(status.PRIMAT,status.GP),(1.,1e-5),(.01,.05)):
        ref = unit*status.standard(code,el,"as published")[0]
        slope = math.log(runs[1][el]/runs[0][el])/(2*delta)
        target = status.SENS[el]["G"]
        rows[el] = {"standard":standard[el],"reference":ref,"relative_error":standard[el]/ref-1,
                    "G_slope":slope,"reference_slope":target,"relative_slope_error":slope/target-1}
        if abs(standard[el]/ref-1)>tol or abs(slope/target-1)>.10:
            raise ValueError(f"Standard expansion validation failed for {el}: {rows[el]}")
    born = bbn.integrate(temps, standard_h, coulomb=False)
    return standard, {"bare_Born_Y_p":born["Y_p"], "elements":rows,"log_G_half_step":delta,"baryon_residual":standard["baryon_residual"]}


def measurements(code,treatment,helium,deuterium):
    """Use the status analysis in its original log-rate coordinates.

    Dividing the network log abundance by alpha here only changes coordinates.
    The model abundance shift itself comes entirely from integration.
    """
    baseline,est = {},{}
    for el,obs in zip(ELEMENTS,(status.HELIUM[helium],status.DEUTERIUM[deuterium])):
        x,err = status.standard(code,el,treatment)
        v = obs["value"]
        baseline[el] = x
        est[el] = status.estimate(v[0],status.side(v,x),x,err,status.SENS[el]["G"])
    return baseline,est,status.baryon_cov(code,treatment)


def likelihood(data, ratios):
    baseline,est,cov = data
    pulls,prediction = {},{}
    for el in ELEMENTS:
        shift = math.log(ratios[el])/status.SENS[el]["G"]
        pulls[el] = (shift-est[el][0])/est[el][1]
        prediction[el] = ratios[el]*baseline[el]
    y,d = (pulls[el] for el in ELEMENTS)
    corr = cov/(est["Y_p"][1]*est["D/H"][1])
    chi2 = (y*y+d*d-2*corr*y*d)/(1-corr*corr)
    return {"prediction":prediction,"signed_sigma":pulls,"chi2":chi2}


def profile(grid, data):
    """Interpolate log yields locally and invert the one-parameter likelihood."""
    keys = sorted(grid)

    def chi(q):
        i = min(max(bisect.bisect_left(keys,q)-2,0),len(keys)-4)
        nodes = keys[i:i+4]
        weights = [math.prod((q-k)/(x-k) for k in nodes if k!=x) for x in nodes]
        ratios = {el:math.exp(sum(w*math.log(grid[x][el]) for w,x in zip(weights,nodes))) for el in ELEMENTS}
        return likelihood(data,ratios)["chi2"]

    lo,hi = keys[0],keys[-1]
    for _ in range(58):
        a,b = (2*lo+hi)/3,(lo+2*hi)/3
        if chi(a)<chi(b):
            hi = b
        else:
            lo = a
    best = (lo+hi)/2
    target = chi(best)+4
    bounds = []
    for outside in (keys[0],keys[-1]):
        if chi(outside)<=target:
            raise ValueError("q confidence interval extends beyond the network grid")
        inside = best
        for _ in range(50):
            mid = (outside+inside)/2
            if chi(mid)>target:
                outside = mid
            else:
                inside = mid
        bounds.append((inside+outside)/2)
    return {"best":best,"chi2_min":chi(best),"two_sigma":bounds}


def analyse():
    registered = json.loads(status.P14_OUTPUT.read_text())
    q = registered["registered_parameters"]["q"]
    zt = registered["registered_parameters"]["z_transition"]
    epochs = {e["epoch"]:e["G_over_G0"] for e in registered["prediction"]["epochs"]}
    temps = bbn.temperatures(STEPS)
    nt = -math.log1p(zt)
    standard_h = [matter(t,0,nt).h_std for t in temps]
    standard,validation = validate(temps,standard_h)

    def yields(background, ts):
        return bbn.integrate(ts,[background[t][0] for t in ts])

    def ratios(result, reference=standard):
        return {el:result[el]/reference[el] for el in ELEMENTS}

    # Choose reporting temperatures explicitly, independently of the ODE mesh.
    samples = sorted(set([10**(1-i/10) for i in range(31)]+[.03]),reverse=True)
    all_t = sorted(set(temps+samples))
    bg,conservation = history(all_t,q,zt)
    physical = yields(bg,temps)
    predictions = {"standard":{el:1. for el in ELEMENTS},"physical":ratios(physical)}
    predictions["kinematic network"] = ratios(bbn.integrate(temps,[(1+q)*bg[t][2]*bg[t][1] for t in temps]))
    for label,factor in (("G/G0",1.),("(1+q)^2 G/G0",(1+q)**2)):
        predictions[label] = {el:(factor*epochs[name])**status.SENS[el]["G"]
                              for el,name in zip(ELEMENTS,("weak_freeze_out","nucleosynthesis"))}
    expansion = []
    for t in samples:
        h,hs,a,field,kinetic = bg[t]
        expansion.append({"T_MeV":t,"H_atomic_over_standard":h/hs,"G_over_G0":a*a,
                          "kinematic_H_squared":((1+q)*a)**2,"physical_H_squared":(h/hs)**2,
                          "field_over_radiation":field,"kinetic_over_radiation":kinetic,
                          "potential_over_radiation":field-kinetic})
    peak_t = max((t for t in temps if .01 <= t <= 10),key=lambda t:bg[t][3])
    # Differential grid convergence (same inputs with twice the step).
    coarse = temps[::2]
    coarse_ratios = ratios(yields(bg,coarse),bbn.integrate(coarse,standard_h[::2]))
    validation["step_halving_relative_change_in_ratio"] = {el:predictions["physical"][el]/coarse_ratios[el]-1 for el in ELEMENTS}
    validation["physical_baryon_residual"] = physical["baryon_residual"]
    grid = {0.:predictions["standard"]}
    for i in (-4,-3,-2,-1,1,2,3,4):
        trial = i*.0005
        background,_ = history(temps,trial,zt)
        grid[trial] = ratios(yields(background,temps))
    fits,comparisons = [],[]
    for code in (status.GP,status.PRIMAT,status.GP_SPA):
        for treatment in status.treatments_for(code):
            for he in status.HELIUM:
                for d in status.DEUTERIUM:
                    data = measurements(code,treatment,he,d)
                    cases = {k:likelihood(data,r) for k,r in predictions.items()}
                    for row in cases.values():
                        row["likelihood_standard_over_model"] = math.exp((row["chi2"]-cases["standard"]["chi2"])/2)
                    info = {"rates":code,"baryon_density":treatment,"helium":he,"deuterium":d}
                    comparisons.append({**info,"cases":cases})
                    if he==status.PRIMARY_HELIUM and d==status.PRIMARY_DEUTERIUM:
                        fits.append({**info,**profile(grid,data)})
    fit = fits[0]
    data = measurements(status.GP,"as published",status.PRIMARY_HELIUM,status.PRIMARY_DEUTERIUM)
    validation["direct_delta_chi2_at_GP_limits"] = [
        likelihood(data,ratios(yields(history(temps,trial,zt)[0],temps)))["chi2"]-fit["chi2_min"]
        for trial in fit["two_sigma"]]
    # Same A, a smaller coupling needs a faster field. Illustrate the freedom
    # by matching the pure-radiation attractor to H_std at the D epoch.
    a = bg[.1][2]
    beta_example = abs(q)/math.sqrt(4*(1-((1+q)*a)**2))
    example,_ = history(all_t,q,zt,beta_example)
    alternative = {"beta":beta_example,"field_over_radiation_at_0.1_MeV":example[.1][3],
                   "H_ratio_at_0.1_MeV":example[.1][0]/example[.1][1],
                   "abundance_ratios":ratios(yields(example,temps))}
    return {"status":"Diagnostic abundance calculation","q":q,"z_transition":zt,"early_abs_beta":1.,
            "unscreened_force_over_tensor_early":1+2*1.**2,
            "N_eff":status.N_EFF_SM,"omega_b":bbn.OMEGA_B,"eta":bbn.ETA,"tau_n_s":bbn.TAU,
            "T0_K":jf.T_CMB,"h_today":PLANCK["h"],"omega_m":OMEGA_M,"steps":STEPS,
            "T_bounds_MeV":[temps[-1],temps[0]],"recombination_G_shift_percent":100*(epochs["recombination"]-1),
            "validation":validation,"conservation":conservation,"expansion":expansion,
            "peak_field":{"T_MeV":peak_t,"field_over_radiation":bg[peak_t][3]},
            "network_physical":physical,"abundance_ratios":predictions,"comparisons":comparisons,
            "q_profiles":fits,"q_grid":[{"q":x,"abundance_ratios":r} for x,r in sorted(grid.items())],
            "alternative_coupling":alternative}


def render_markdown(r):
    v = r["validation"]
    rows = [row for row in r["comparisons"] if row["helium"] == status.PRIMARY_HELIUM
            and row["deuterium"] == status.PRIMARY_DEUTERIUM]
    gp = rows[0]["cases"]
    lr = "likelihood_standard_over_model"
    phy = gp["physical"]
    kin = gp["(1+q)^2 G/G0"]
    peak = r["peak_field"]
    sample = {row["T_MeV"]:row for row in r["expansion"]}
    fit = r["q_profiles"][0]
    alt = r["alternative_coupling"]
    lines = [
        "<!-- GENERATED by analyses/p14_physical_model.py from analyses/p14_physical_model.json. Do not edit by hand. -->",
        "",
        "# A conserving completion of P14 during nucleosynthesis",
        "",
        f"**For the reference coupling, making P14 conserve energy leaves its abundance tension essentially unchanged.** "
        f"The scalar peaks at {peak['field_over_radiation']:.2e} of the radiation density near "
        f"{peak['T_MeV']:.3f} MeV. Slower expansion lets more neutrons decay and burns more deuterium. "
        f"With the published Planck baryon density and Gaussian-process rates, standard expansion is "
        f"{phy[lr]:.1f} times as likely as the physical model, compared with {kin[lr]:.1f} for the two-epoch clock proxy. "
        "This diagnostic uses the registered mass history. Its field energy and abundance likelihood depend on the chosen completion.",
        "",
        "## Action and reconstruction",
        "",
        "Use a flat FLRW solution of the Einstein-frame action, with reduced Planck mass M and all material species "
        "(including cold dark matter) coupled to the atomic metric.",
        "",
        r"$$S=\int d^4x\sqrt{-g}\left[\frac{M^2}{2}R-\frac12(\nabla\phi)^2-V(\phi)\right]"
        r"+S_m[\psi,A^2(\phi)g_{\mu\nu}].$$",
        "",
        f"Write N = ln a_E, N_t = −ln(1+z_t), with z_t = {r['z_transition']:g}. "
        f"The registration fixes q = {r['q']}, ln A = q min(N−N_t, 0), and a_atomic = A a_E. "
        f"Choose the early coupling magnitude β = {r['early_abs_beta']:g} and the monotonic trajectory "
        "φ/M = k(N−N_t), k = |q|/β. Then ln A(φ) = sign(q) β min(φ/M, 0). "
        "A is constant on the late branch while the field continues to roll. The q = 0 limit is a constant field and vacuum density.",
        "",
        "Let B and p be the Einstein-frame material density and pressure, Θ = B−3p, U = φ̇²/2+V and "
        "α = d ln A/dφ. Dots use Einstein proper time and primes below use N.",
        "",
        r"$$3M^2H_E^2=B+U,\qquad \ddot\phi+3H_E\dot\phi+V_{,\phi}=-\alpha\Theta,"
        r"\qquad B'+3(B+p)=s\Theta,\qquad s=(\ln A)'.$$",
        "",
        r"$$U'+k^2 U=-k^2 B-s\Theta,\qquad K=\frac{k^2}{6}(B+U),\qquad V(\phi)=U(N)-K(N),"
        r"\qquad N=N_t+\phi/(kM).$$",
        "",
        "These formulas specify a single-valued potential by quadrature. Use the integrating factor exp(k²N) and "
        f"set U(today) by flatness with h = {r['h_today']} and ω_m = {r['omega_m']}. "
        "The trajectory, coupling strength and present vacuum density are choices. Once they are set, "
        "the field equation fixes the potential along the trajectory. The exact kink in A and V gives finite one-sided forces. "
        "U, φ̇ and H_E are continuous across it. Atomic H has the registered one-sided clock-rate step.",
        "",
        "With P_tot = p+K−V, the exchange terms cancel in (B+U)′ = −3(B+U+P_tot). "
        "The numerical check differences the endpoint total densities and independently integrates the total enthalpy over each cell. "
        f"The maximum absolute discrepancy divided by the integrated enthalpy term is {r['conservation']['max_cell']:.2e} "
        f"from today through BBN and {r['conservation']['adjacent_to_transition']:.2e} in the cells touching the transition.",
        "",
        "## Expansion at fixed atomic temperature",
        "",
        f"Electromagnetic entropy conservation gives a_atomic = (T₀/T)[2/g_s(T)]^(1/3) with T₀ = {r['T0_K']} K. "
        "Integrating the equilibrium electron–positron phase space supplies both g_s and the pair trace. "
        f"Free-streaming neutrinos have Tν/T = (g_s/5.5)^(1/3), with N_eff = {r['N_eff']} in their energy density. "
        "B and Θ are A⁴ times their atomic values. Dust and the pairs source the field. Photons and massless neutrinos have zero trace. "
        "Atomic clocks measure H_atomic = (1+s)H_E/A. Both proxies in the table are squared expansion rates.",
        "",
        "| T (MeV) | H_atomic/H_std | Physical H²/H²_std | G/G₀ | (1+q)² G/G₀ | K/ρ_rad | V/ρ_rad | U/ρ_rad |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for t in (10,1,.1,.03,.01):
        row = sample[t]
        lines.append(f"| {t:g} | {row['H_atomic_over_standard']:.7f} | {row['physical_H_squared']:.7f} | "
                     f"{row['G_over_G0']:.7f} | {row['kinematic_H_squared']:.7f} | {row['kinetic_over_radiation']:.3e} | "
                     f"{row['potential_over_radiation']:.3e} | {row['field_over_radiation']:.3e} |")
    lines += [
        "",
        "The JSON samples the full temperature range. The registered epoch redshifts are approximate temperature labels. "
        "The expansion table uses entropy to convert temperature to redshift. The abundance proxy comparison below uses "
        "the actual registered epoch redshifts, as the earlier analysis did.",
        "",
        "## Network validation",
        "",
        f"At ω_b = {r['omega_b']}, the late baryon/photon ratio is {r['eta']:.5e}. Before annihilation the code multiplies "
        "this by g_s/2. The weak rates integrate E p Eν² dE with Fermi occupation and final-state blocking for beta decay, "
        "lepton captures and their inverses. Both the thermal and vacuum integrals include the leading electron–proton "
        f"Coulomb factor. Pure Born rates give Yₚ = {v['bare_Born_Y_p']:.5f}, outside the helium validation tolerance. "
        f"The vacuum integral sets the normalization to τ_n = {r['tau_n_s']} s. "
        "The neglect of recoil and the remaining radiative corrections limits the absolute helium accuracy. "
        "[Weak rates and normalization, Pitrou et al.](https://arxiv.org/abs/1801.08023)",
        "",
        "The nuclear network evolves n, p, D, ³H, ³He and ⁴He by an implicit second-order backward difference in −ln T. "
        "Reverse nuclear rates use detailed balance with nuclear masses, spin weights and identical-pair factors. "
        f"It starts in weak equilibrium at {r['T_bounds_MeV'][1]:g} MeV and follows residual burning to "
        f"{r['T_bounds_MeV'][0]:g} MeV. Nuclear reactions start above the deuterium bottleneck, after the high-temperature weak-only phase.",
        "",
        "| Reaction | Forward rate |",
        "|---|---|",
        "| p(n,γ)d | [Ando et al.](https://arxiv.org/abs/nucl-th/0511074) with the high-temperature branch in "
        "[AlterBBN](https://github.com/espensem/AlterBBN/blob/master/src/bbnrate.c) |",
        "| d(p,γ)³He, d(d,n)³He, d(d,p)³H | Maxwell averages of the fitted S factors in "
        "[Pisanti et al., Appendix A](https://arxiv.org/abs/2011.11537) |",
        "| ³H(d,n)⁴He, ³He(d,p)⁴He | [Bosch & Hale, Eq. 12 and Table VII](https://doi.org/10.1088/0029-5515/32/4/I07), "
        "with the [Serpico et al.](https://arxiv.org/abs/astro-ph/0408076) tritium fit above the Bosch–Hale range |",
        "| ³He(n,p)³H | [Serpico et al.](https://arxiv.org/abs/astro-ph/0408076) |",
        "| d(n,γ)³H | Wagoner (ApJS 18, 247), as tabulated in [AlterBBN](https://github.com/espensem/AlterBBN/blob/master/src/bbnrate.c) |",
        "",
        f"Constant-G derivatives use two standard-background integrations at ln(G/G₀) = ±{v['log_G_half_step']}. "
        "The reference abundances are PRIMAT helium and Planck Gaussian-process deuterium. "
        "[Published inputs and errors](p14_bbn_status.md) · [Fields et al. sensitivities](https://arxiv.org/abs/1912.01132)",
        "",
        "| Element | Standard run | Reference | Relative error | d ln X/d ln G | Fields et al. |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for el,val in v["elements"].items():
        lines.append(f"| {el} | {val['standard']:.6g} | {val['reference']:.6g} | {100*val['relative_error']:+.2f}% | "
                     f"{val['G_slope']:.4f} | {val['reference_slope']:.3f} |")
    lines += ["",f"The largest baryon-number residual in the physical run is {v['physical_baryon_residual']:.2e}. "
              f"Halving the step to {r['steps']} intervals changes the two model/standard ratios by at most "
              f"{max(map(abs,v['step_halving_relative_change_in_ratio'].values())):.2e} in relative terms.",
              "", "## Abundances and likelihood", "",
              "Apply each network model/standard ratio to the published standard abundance. The two historical proxies instead "
              "use the Fields sensitivities at the representative epochs. The kinematic network uses (1+q)A throughout BBN and "
              "isolates the effect of the field energy. Signed distances are model minus measurement in the original log-abundance "
              "likelihood. The likelihood ratios include the shared baryon-density covariance.", "",
              "| Planck GP, published | Yₚ ratio | D/H ratio | LBT helium (σ) | PDG deuterium (σ) | L_std/L_model |",
              "|---|---:|---:|---:|---:|---:|"]
    for label,ratio in r["abundance_ratios"].items():
        case = gp[label]
        lines.append(f"| {label} | {ratio['Y_p']:.7f} | {ratio['D/H']:.7f} | {case['signed_sigma']['Y_p']:+.2f} | "
                     f"{case['signed_sigma']['D/H']:+.2f} | {case[lr]:.2f} |")
    lines += ["","| Physical model | Baryon density | Yₚ | D/H (10⁻⁵) | LBT (σ) | PDG (σ) | L_std/L_model | 2σ q interval (10⁻³) |",
              "|---|---|---:|---:|---:|---:|---:|---|"]
    for row,interval in zip(rows,r["q_profiles"]):
        case = row["cases"]["physical"]
        y,d = (case["prediction"][el] for el in ELEMENTS)
        lo,hi = interval["two_sigma"]
        lines.append(f"| {row['rates']} | {row['baryon_density']} | {y:.5f} | {d:.4f} | {case['signed_sigma']['Y_p']:+.2f} | "
                     f"{case['signed_sigma']['D/H']:+.2f} | {case[lr]:.2f} | [{lo*1000:.3f}, {hi*1000:.3f}] |")
    lines += [
        "",
        f"The Planck GP best fit is q = {fit['best']:.2e}. The abundance-only interval uses Δχ² = 4 for a single signed q, "
        "holding β fixed and reconstructing V at each q. The code interpolates the log yields of full network runs and checks "
        f"the endpoints by direct integration (Δχ² = {v['direct_delta_chi2_at_GP_limits'][0]:.6f}, "
        f"{v['direct_delta_chi2_at_GP_limits'][1]:.6f}). The registered exponent lies outside the published-density interval. "
        "The JSON also gives the likelihood for the other helium and deuterium measurements in the earlier analysis.",
        "",
        "## What the registration leaves free",
        "",
        "For traceless radiation, the early particular solution gives U/B = k²/(4−k²). A specified mass drift fixes the "
        "product of coupling and field velocity. It leaves their individual values free. The pairs give a further contribution "
        "near annihilation. As an illustration, choose β by requiring the pure-radiation expression to cancel the clock and "
        f"mass suppression at {sample[.1]['T_MeV']:g} MeV. With β = {alt['beta']:.5f} the same registered mass history has "
        f"U/ρ_rad = {alt['field_over_radiation_at_0.1_MeV']:.4f} there. The integrated H ratio is {alt['H_ratio_at_0.1_MeV']:.5f}, "
        f"and the helium and deuterium ratios become {alt['abundance_ratios']['Y_p']:.5f} and {alt['abundance_ratios']['D/H']:.5f}. "
        "This choice illustrates degeneracy and has no independent calibration.",
        "",
        "## Limits",
        "",
        f"A full CMB spectrum fit with perturbations would determine the baryon density and its uncertainty for a model with "
        f"a {abs(r['recombination_G_shift_percent']):.2f}% decrease of G in atomic units at recombination. The published and "
        "widened treatments show the dependence on that missing information. The network transfers fractional changes computed "
        "at one baryon density to each published prediction. It omits heavier nuclides, finite-temperature QED, neutrino transport "
        "and nuclear-rate uncertainty propagation. The uncertainties in the likelihood come from the published analyses.",
        "",
        "The exact freeze is an imposed kink. This construction establishes a homogeneous solution. Its initial-condition "
        "stability, structure formation and scalar-mediated forces require separate tests. A² measures the tensor coupling "
        "in atomic units. On scales shorter than the scalar range, unscreened scalar exchange multiplies the Newtonian force "
        f"by 1+2β² = {r['unscreened_force_over_tensor_early']:g} on the early branch. These abundance data "
        "test the cosmological expansion. They do not score the registration.",
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
        problems = jf._compare(result,saved)
        if REPORT.read_text(encoding="utf-8") != render_markdown(saved):
            problems.append("Markdown differs from the JSON rendering")
        for problem in problems[:10]:
            print("DIFFERS",problem)
        print("P14 physical model " + ("differs" if problems else "reproduces its output"))
        return int(bool(problems))
    OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(render_markdown(result),encoding="utf-8")
    print(f"Wrote {OUTPUT.name} and {REPORT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
