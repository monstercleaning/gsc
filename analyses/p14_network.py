"""Thermal background and six-species BBN network for p14_physical_model.

Energies in atomic-frame MeV, seconds for time, abundances in nuclei/baryon.
Nuclear rates are N_A <sigma v> in cm^3 mol^-1 s^-1. No abundance calibration.
"""
import math
from functools import lru_cache
from typing import NamedTuple

from p14_bbn_status import N_EFF_SM

ME, DELTA, TAU = 0.51099895, 1.29333236, 878.4
HBAR, HBAR_C = 6.582119569e-22, 1.973269804e-11  # MeV s, MeV cm
MPL = 1.22089e22  # unreduced Planck mass in MeV
NA = 6.02214076e23
OMEGA_B = 0.02237
ETA = 273.78e-10 * OMEGA_B  # late-time eta, for T0 = 2.7255 K
PHOTONS = 2 * 1.20205690316 / math.pi**2
MASS = (939.56542, 938.27209, 1875.61294, 2808.92113, 2808.39161, 3727.37941)
SPIN = (2, 2, 3, 2, 2, 1)
BARYONS = (1, 1, 2, 3, 3, 4)


def gauss(n):
    """Gauss-Legendre nodes and weights on [0,1]."""
    nodes = []
    for k in range(1, n + 1):
        z = math.cos(math.pi * (k - 0.25) / (n + 0.5))
        for _ in range(10):
            p, prev = z, 1.
            for j in range(2, n + 1):
                p, prev = ((2*j-1)*z*p - (j-1)*prev)/j, p
            deriv = n*(prev-z*p)/(1-z*z)
            dz = p/deriv
            z -= dz
            if abs(dz) < 2e-15:
                break
        nodes.append(((1+z)/2, 1/((1-z*z)*deriv**2)))
    return nodes


QUAD = gauss(48)


class Plasma(NamedTuple):
    rho: float
    trace: float
    entropy_dof: float
    tnu: float
    cooling: float  # -d ln a_atomic / d ln T


@lru_cache(None)
def plasma(t):
    """Ideal Fermi gas, separately conserved electromagnetic and neutrino entropy."""
    x = ME/t
    energy = trace = heat = 0.
    if x < 60:
        for node, weight in QUAD:
            p = 44*node  # momentum/T
            e = math.hypot(x, p)
            f = 1/(1+math.exp(e))
            measure = 44*weight*2/math.pi**2*p*p*f
            energy += measure*e
            trace += measure*x*x/e
            heat += measure*e*e*(1-f)  # d rho_e/dT in T^3 units
    photon = math.pi**2/15
    enthalpy = (4*(photon+energy)-trace)/3
    gs = enthalpy*45/(2*math.pi**2)
    tnu = t*(gs/5.5)**(1/3)
    nu = 7/8 * photon * N_EFF_SM * tnu**4
    return Plasma((photon+energy)*t**4+nu, trace*t**4, gs, tnu,
                  (4*photon+heat)/(3*enthalpy))


def fermi(energy, temp):
    e = math.exp(-abs(energy/temp))
    return (e if energy > 0 else 1)/(1+e)


def coulomb_factor(energy, momentum):
    x = 2 * math.pi / 137.035999084 * energy / momentum
    return x / -math.expm1(-x)


def weak_integrals(t, tnu, coulomb=True):
    """Allowed Born phase space E p E_nu^2 dE, including all three inverse pairs.

    The signed neutrino energy in the electron branch includes beta decay and
    inverse decay. Splitting at its zero resolves cold neutrino blocking.
    """
    forward = backward = 0.
    for lower, upper, positron in ((ME, DELTA, False), (DELTA, DELTA+42*t, False),
                                   (ME, ME+42*t, True)):
        for node, weight in QUAD:
            e = lower+(upper-lower)*node**2
            enu = e+DELTA if positron else e-DELTA
            momentum = math.sqrt((e-ME)*(e+ME))
            phase = 2*(upper-lower)*node*weight*e*momentum*enu**2
            if positron:
                forward += phase*fermi(e,t)*fermi(-enu,tnu)
                backward += phase*fermi(-e,t)*fermi(enu,tnu)
            else:
                # Leading electron-proton Coulomb (Fermi) factor, also in vacuum.
                if coulomb:
                    phase *= coulomb_factor(e, momentum)
                forward += phase*fermi(-e,t)*fermi(enu,tnu)
                backward += phase*fermi(e,t)*fermi(-enu,tnu)
    return forward, backward


# Vacuum beta-decay integral in the same variable and quadrature as above.
@lru_cache(None)
def vacuum_integral(coulomb=True):
    integral = 0.
    for node, weight in QUAD:
        energy = ME + (DELTA - ME) * node**2
        momentum = math.sqrt((energy - ME) * (energy + ME))
        phase = energy * momentum * (DELTA - energy)**2
        if coulomb:
            phase *= coulomb_factor(energy, momentum)
        integral += 2 * (DELTA - ME) * node * weight * phase
    return integral


def polynomial(x, coefficients):
    value = 0.
    for c in reversed(coefficients):
        value = value*x+c
    return value


def charged_rate(t, reduced_mass, coefficients):
    """Maxwell average of the Pisanti et al. (2021) Appendix A S(E) in MeV barn."""
    gamow = 2*reduced_mass*(math.pi/137.035999084)**2
    integral = 0.
    for node, weight in QUAD:
        x = 40*node  # E/T
        integral += weight * polynomial(x*t, coefficients) * math.exp(-x-math.sqrt(gamow/(x*t)))
    return 40 * NA*2.99792458e10*1e-24*math.sqrt(8/(math.pi*reduced_mass*t))*integral


# Reactant and product indices; photons are in equilibrium with zero chemical potential.
N, P, D, T, H3, H4 = range(6)
REACTIONS = (((N,P),(D,)), ((D,P),(H3,)), ((D,D),(N,H3)), ((D,D),(P,T)),
             ((T,D),(N,H4)), ((H3,D),(P,H4)), ((H3,N),(P,T)), ((D,N),(T,)))
STOICH = [tuple((i, b.count(i)-a.count(i)) for i in sorted(set(a+b))
                if b.count(i)!=a.count(i)) for a,b in REACTIONS]


def bosch_hale(t, barrier, mass, c1, c2, c3, c4, c5, c6, c7):
    """Bosch & Hale (1992), eq. 12 and Table VII, temperature in keV."""
    kev = t*1000
    theta = kev/(1-kev*(c2+kev*(c4+kev*c6))/(1+kev*(c3+kev*(c5+kev*c7))))
    xi = (barrier**2/(4*theta))**(1/3)
    return NA*c1*theta*math.sqrt(xi/(mass*kev**3))*math.exp(-3*xi)


def nuclear_rates(t):
    u = t/0.08617333262  # T9
    # Ando et al. (2006) rational fit below T9=1.5, high-T SKM branch in AlterBBN.
    if u <= 1.5:
        npd = 44216*polynomial(u,(1,3.75191,1.92934,.746503,.0197023,.00000300491))
        npd /= polynomial(u,(1,5.4678,5.62395,.489312,.00747806))
    else:
        npd = 47420*polynomial(math.sqrt(u),(1,-.8504,.4895,-.09623,.008471,-.00028))
    dp = charged_rate(t, MASS[D]*MASS[P]/(MASS[D]+MASS[P]), (.2121,5.975,5.463,-1.665))*1e-6
    ddn = charged_rate(t, MASS[D]/2, (.05225,.3655,-.1799,.05832,-.007393))
    ddp = charged_rate(t, MASS[D]/2, (.05520,.2151,-.02555))
    # Serpico et al. (2004 preprint, 2005 JCAP), central fits as in AlterBBN.
    if t > .1:
        v = u**(1/3)
        td = 6.2265733e8*math.exp(-.49711597/u)/u**.56785403
        td += math.exp(-.23309803*u*u-1.342742/v)/v**2*polynomial(u,
            (-8.1144927e7,2.2315324e9,-2.9439669e9,1.8764462e9,-6.0511612e8,9.5196576e7,-5.2901086e6))
    else:
        td = bosch_hale(t,34.3827,1124656,1.17302e-9,.0151361,.0751886,.00460643,.01350,-.00010675,.00001366)
    hd = bosch_hale(t,68.7508,1124572,5.51036e-10,.00641918,-.00202896,-.000019108,.000135776,0,0)
    hn = polynomial(math.sqrt(u),(7.064935e8,-4.92736677238425e8,6.733213571736319e8,
        -1.3659670893994067e9,1.7181155480346258e9,-6.629932739639357e8,-4.5367658146835446e8,
        4.834951929033479e8,-1.2216728981712557e8))
    dn = 66.2*(1+18.9*u)  # Wagoner (1969)
    return npd, dp, ddn, ddp, td, hd, hn, dn


@lru_cache(None)
def coefficients(t, coulomb=True):
    gas = plasma(t)
    weak = tuple(r/(vacuum_integral(coulomb)*TAU) for r in weak_integrals(t, gas.tnu, coulomb))
    rates = []
    if t <= .16:
        nb = ETA*PHOTONS*t**3*gas.entropy_dof/2
        for (before,after), rate in zip(REACTIONS,nuclear_rates(t)):
            # Maxwell-Boltzmann detailed balance, including identical pairs.
            # n_i(eq) proportional to g_i (m_i T/2pi)^(3/2) exp[(mu_i-m_i)/T].
            forward = rate/NA/HBAR_C**3 / (2 if before[0] == before[1] else 1)
            qvalue = sum(MASS[i] for i in before)-sum(MASS[i] for i in after)
            partition = lambda i: SPIN[i]*(MASS[i]*t/(2*math.pi))**1.5
            balance = math.prod(partition(i) for i in before)/math.prod(partition(i) for i in after)
            reverse = forward*balance*math.exp(-qvalue/t)*nb**(len(after)-1)
            rates.append((forward*nb,reverse))
    return weak, rates


def solve(matrix):
    """Pivoted elimination on a six-by-seven augmented Jacobian."""
    for col in range(6):
        pivot = max(range(col,6),key=lambda i:abs(matrix[i][col]))
        matrix[pivot],matrix[col] = matrix[col],matrix[pivot]
        row = matrix[col]
        for i in range(col+1,6):
            target = matrix[i]
            factor = target[col]/row[col]
            for j in range(col+1,7):
                target[j] -= factor*row[j]
    delta = [0.]*6
    for i in reversed(range(6)):
        row = matrix[i]
        delta[i] = (row[6]-sum(row[j]*delta[j] for j in range(i+1,6)))/row[i]
    return delta


def step(base, y, dt, weak, rates):
    """Implicit BDF corrector; reaction fluxes and their analytic derivatives."""
    np, pn = weak
    for _ in range(12):
        mat = [[float(i==j) for j in range(6)]+[base[i]-y[i]] for i in range(6)]
        flux = np*y[N]-pn*y[P]
        for i,sign in ((N,-1),(P,1)):
            mat[i][6] += dt*sign*flux
            mat[i][N] -= dt*sign*np
            mat[i][P] += dt*sign*pn
        for ((a,b),products), change, (f,r) in zip(REACTIONS,STOICH,rates):
            flux = f*y[a]*y[b]
            derivatives = [(a,f*y[b]),(b,f*y[a])]
            c = products[0]
            if len(products)==1:
                flux -= r*y[c]
                derivatives.append((c,-r))
            else:
                d = products[1]
                flux -= r*y[c]*y[d]
                derivatives.extend(((c,-r*y[d]),(d,-r*y[c])))
            for i,count in change:
                scale = count*dt
                mat[i][6] += scale*flux
                for j,deriv in derivatives:
                    mat[i][j] -= scale*deriv
        update = solve(mat)
        y = [a+b for a,b in zip(y,update)]
        if all(abs(d) < 1e-17+1e-9*abs(v) for d,v in zip(update,y)):
            return y
    raise ArithmeticError("Network corrector did not converge")


def temperatures(n):
    return [10*math.exp(-i*math.log(10000)/n) for i in range(n+1)]


def integrate(temps, hubble, coulomb=True):
    """BDF2 on uniform -ln T; integrate beyond 10 keV to finish D burning."""
    dx = math.log(temps[0]/temps[-1])/(len(temps)-1)
    n = 1/(1+math.exp(DELTA/temps[0]))
    y = [n,1-n,0.,0.,0.,0.]
    old = None
    baryon_error = 0.
    for t, h in zip(temps[1:], hubble[1:]):
        dt = dx*plasma(t).cooling/h
        weak, rates = coefficients(t, coulomb)
        base = y if old is None else [(4*a-b)/3 for a,b in zip(y,old)]
        if old is not None:
            dt *= 2/3
        if rates:
            new = step(base,y,dt,weak,rates)
        else:
            n = (base[N]+dt*weak[1])/(1+dt*sum(weak))
            new = [n,1-n,0.,0.,0.,0.]
        if min(new) < -1e-17:
            raise ArithmeticError("Negative nuclear abundance at T=%g" % t)
        baryon_error = max(baryon_error,abs(sum(a*b for a,b in zip(new,BARYONS))-1))
        old,y = y,new
    return {"Y_p":4*y[H4],"D/H":y[D]/y[P],"baryon_residual":baryon_error}
