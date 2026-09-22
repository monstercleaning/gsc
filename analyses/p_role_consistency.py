#!/usr/bin/env python3
"""p_role_consistency.py — DIAGNOSTIC behind OPEN_PROBLEMS.md problems 1–4 (not a registered prediction).

Question: where can the canonical T2 exponent p live? A universal rescaling of
every scale is unobservable, so the registered BAO shift of P1 needs a specific
non-universality. This script makes two readings explicit and computes what
each implies, next to P1's registered heuristic (ruler multiplied by
(1+z_drag)^p, distances untouched):

  Model A — particle masses drift relative to the Planck mass (the gauge
            function of Canuto-type scale-covariant theories). Einstein frame,
            G fixed, all particle masses m = m0 g(z_E), photons conformal.
            Observed redshift 1+z = (1+z_E)/g. Recombination at fixed T/m, i.e.
            at fixed observed z. Matter density scales with g.
            Local signature today: d ln(G m^2/hbar c)/dt = 2 d ln m/dt.
  Model B — the modulated history used by the P8 revision r2:
            H(z) = H_LCDM(z) (1+z)^p with the standard redshift mapping.

Also: an "early transition" variant of Model A (masses drift only above z_t),
tuned to reproduce P1's registered shift, and the amplification the P2 pipeline
assumes versus what Model A implies at z = 17.

Deterministic, standard library only. Writes analyses/p_role_consistency.json.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gsc.canonical_params import CANONICAL_P  # noqa: E402

C = 299792.458
H0 = 67.4
H_FRAC = H0 / 100.0
OMEGA_M_H2, OMEGA_B_H2 = 0.1430, 0.02237
OMEGA_M = OMEGA_M_H2 / H_FRAC ** 2
OMEGA_G_H2 = 2.469e-5 * (2.7255 / 2.725) ** 4
OMEGA_R = OMEGA_G_H2 * (1 + 0.2271 * 3.046) / H_FRAC ** 2
OMEGA_L = 1 - OMEGA_M - OMEGA_R
R_B0 = 3 * OMEGA_B_H2 / (4 * OMEGA_G_H2)
Z_DRAG = 1020.7158      # observed-z drag epoch used by the P1 pipeline
Z_STAR = 1089.92
Z_BBN = 4.3e8
BAO_Z = (0.51, 0.93, 2.33)
H0_PER_YR = H0 / 3.0857e19 * 3.1557e7
LLR_CENTRAL, LLR_SIGMA = -5.0e-15, 9.6e-15      # Biskupek, Müller & Torre 2021
Z_TRANSITION = 10.0
P2_K_SIGMA = 50.0                               # amplification registered by the P2 pipeline


def simpson(f, a, b, n=4000):
    n += n % 2
    h = (b - a) / n
    s = f(a) + f(b) + sum((4 if i % 2 else 2) * f(a + i * h) for i in range(1, n))
    return s * h / 3


class ModelA:
    """Masses drift relative to the Planck mass: m(z_E)/m0 = g(z_E)."""

    def __init__(self, g, dlng):
        self.g, self.dlng = g, dlng

    def HE(self, zE):
        x = 1 + zE
        return H0 * math.sqrt(OMEGA_R * x ** 4 + OMEGA_M * self.g(zE) * x ** 3 + OMEGA_L)

    def zobs(self, zE):
        return (1 + zE) / self.g(zE) - 1

    def zE(self, zo):
        lo, hi = 0.0, zo * 1.01 + 1
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if self.zobs(mid) < zo else (lo, mid)
        return 0.5 * (lo + hi)

    def cs(self, zE):
        return C / math.sqrt(3 * (1 + R_B0 / (1 + self.zobs(zE))))

    def sound_horizon(self, z_obs):
        u0, u1 = math.log1p(self.zE(z_obs)), math.log(1e8)
        return simpson(lambda u: self.cs(math.expm1(u)) * math.exp(u) / self.HE(math.expm1(u)), u0, u1)

    def DM(self, zo, n=2000):
        return simpson(lambda z: C / self.HE(z), 0, self.zE(zo), n)

    def DH(self, zo):
        zE = self.zE(zo)
        dzo_dzE = (1 + self.zobs(zE)) / (1 + zE) * (1 - self.dlng(zE))
        return C / (dzo_dzE * self.HE(zE))


class ModelB:
    """P8 r2 history: H_LCDM(z) (1+z)^p, standard redshift mapping."""

    def __init__(self, p):
        self.p = p

    def H(self, z):
        x = 1 + z
        return H0 * math.sqrt(OMEGA_R * x ** 4 + OMEGA_M * x ** 3 + OMEGA_L) * x ** self.p

    def sound_horizon(self, z_obs):
        cs = lambda z: C / math.sqrt(3 * (1 + R_B0 / (1 + z)))
        return simpson(lambda u: cs(math.expm1(u)) * math.exp(u) / self.H(math.expm1(u)),
                       math.log1p(z_obs), math.log(1e8))

    def DM(self, z, n=2000):
        return simpson(lambda zz: C / self.H(zz), 0, z, n)

    def DH(self, z):
        return C / self.H(z)


LCDM = ModelA(lambda z: 1.0, lambda z: 0.0)
RD0 = LCDM.sound_horizon(Z_DRAG)
BASE = {z: (LCDM.DM(z) / RD0, LCDM.DH(z) / RD0) for z in BAO_Z}


def bao_shifts(model):
    rd = model.sound_horizon(Z_DRAG)
    out = {"r_d_change_percent": round(100 * (rd / RD0 - 1), 3)}
    for z in BAO_Z:
        out[f"z={z}"] = {
            "DM_over_rd_change_percent": round(100 * ((model.DM(z) / rd) / BASE[z][0] - 1), 3),
            "DH_over_rd_change_percent": round(100 * ((model.DH(z) / rd) / BASE[z][1] - 1), 3),
        }
    return out


def powerlaw(q):
    return ModelA(lambda z: (1 + z) ** (-q), lambda z: -q)


def early(qp):
    return ModelA(lambda z: 1.0 if z < Z_TRANSITION else ((1 + z) / (1 + Z_TRANSITION)) ** (-qp),
                  lambda z: 0.0 if z < Z_TRANSITION else -qp)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=str(REPO_ROOT / "analyses" / "p_role_consistency.json"))
    args = ap.parse_args(argv)
    p = CANONICAL_P
    p1_shift = 100 * (1 / (1 + Z_DRAG) ** p - 1)
    rate = 2 * p * H0_PER_YR
    q_llr = (LLR_CENTRAL + 3 * LLR_SIGMA) / (2 * H0_PER_YR)

    lo, hi = 1e-4, 2e-3
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if bao_shifts(early(mid))["z=0.93"]["DM_over_rd_change_percent"] > round(p1_shift, 3) else (lo, mid)
    qp = round(0.5 * (lo + hi), 7)
    tr = early(qp)
    g = tr.g
    theta_tr = (tr.sound_horizon(Z_STAR) / tr.DM(Z_STAR, 20000)) / (LCDM.sound_horizon(Z_STAR) / LCDM.DM(Z_STAR, 20000))
    delta_sigma_17 = 1 - 18 ** (-p)
    g17 = early(qp).g(early(qp).zE(17.0)) ** 2

    record = {
        "tool": "p_role_consistency.py",
        "status": "DIAGNOSTIC — evidence for OPEN_PROBLEMS.md; not a registered prediction",
        "canonical_p": p,
        "p1_registered_heuristic": {"DM_over_rd_change_percent_all_z": round(p1_shift, 3)},
        "model_A_powerlaw_canonical": {
            "bao": bao_shifts(powerlaw(p)),
            "local_dln_alphaG_dt_per_yr": float(f"{rate:.3e}"),
            "llr_z_score": round((rate - LLR_CENTRAL) / LLR_SIGMA, 1),
        },
        "model_B_p8r2_history": {"bao": bao_shifts(ModelB(p))},
        "llr_3sigma_edge": {"q_max": float(f"{q_llr:.3e}"), "bao": bao_shifts(powerlaw(q_llr))},
        "model_A_early_transition": {
            "z_transition": Z_TRANSITION,
            "q_prime_tuned_to_p1": qp,
            "bao": bao_shifts(tr),
            "local_dln_alphaG_dt_per_yr": 0.0,
            "G_over_G0_atomic_at_recombination": round(g(tr.zE(Z_STAR)) ** 2, 4),
            "G_over_G0_atomic_at_bbn": round(g(tr.zE(Z_BBN)) ** 2, 4),
            "theta_star_change_percent_at_fixed_parameters": round(100 * (theta_tr - 1), 3),
            "dL_gw_over_dL_em": {f"z={z}": round(g(tr.zE(z)), 5) for z in (1, 5, 20, 50)},
        },
        "p2_amplification_check": {
            "registered_K_sigma": P2_K_SIGMA,
            "registered_depth_change_percent_at_z17": round(100 * P2_K_SIGMA * delta_sigma_17, 2),
            "model_A_early_transition_G_change_percent_at_z17": round(100 * (1 - g17), 3),
        },
    }
    out = Path(args.output)
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    print(f"wrote {out}  SHA-256 {hashlib.sha256(payload.encode()).hexdigest()[:16]}…")
    print(json.dumps({k: record[k] for k in ("p1_registered_heuristic", "model_A_powerlaw_canonical")}, indent=1)[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
