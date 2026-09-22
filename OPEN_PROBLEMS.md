# Open problems

This package was reorganized without changing any registered prediction or number: every frozen pipeline
output is byte-identical to its registered version. Problems that are already known are recorded here instead
of being silently fixed, because fixing them changes predictions — and a changed prediction must be registered
as a new entry, not edited into an old one ([METHOD.md](METHOD.md)).

The numbers below come from a deterministic diagnostic, [analyses/p_role_consistency.py](analyses/p_role_consistency.py)
(output: [analyses/p_role_consistency.json](analyses/p_role_consistency.json)). It is evidence for this page,
not a registered prediction.

---

## 1. Which sector carries the canonical parameter?

**In plain words.** If every scale in nature shrank together, nothing could ever be measured — that is exactly
what tier T1 says. The one registered deviation from standard cosmology (the +0.417% BAO ruler shift, P1)
therefore needs *something* that does not shrink along with everything else. The register never says what.

**What the diagnostic finds.**

- The only reading that reproduces P1's sign and size is a drift of particle masses relative to the Planck
  mass — the gauge function of Canuto-type scale-covariant theories. At the canonical p it gives a BAO shift of
  −0.47% to −0.49% in D/r_d (P1's heuristic: −0.415%).
- That reading has an unavoidable local signature today: the gravitational coupling G m²/ħc drifts by
  8.3×10⁻¹⁴ per year. Lunar laser ranging measures (−5.0 ± 9.6)×10⁻¹⁵ per year (arXiv:2012.12032), which
  excludes the canonical value at about **9σ**. Paper A §4.4 states that lunar ranging does not constrain p;
  that statement is flagged as wrong.
- Allowed by lunar ranging at 3σ: q < 1.73×10⁻⁴, which gives a BAO shift of only −0.14% — below the precision
  of the current DESI data.

**History repeats.** Canuto & Owen (ApJS 41, 301, 1979) derived G ∝ 1/t in atomic units, a drift at the Hubble
rate. Viking lander ranging (Hellings et al., PRL 51, 1609, 1983) measured the atomic-versus-dynamical clock drift
as (0.1 ± 0.8)×10⁻¹¹ per year, far below that prediction. The steady-drift form of P1 fails the same test,
now about a thousand times more precise.

**A coherent variant exists.** If the masses drifted only in the early universe (before z ≈ 10, the first
~500 million years) and have been frozen since, the diagnostic finds (q′ = 8.65×10⁻⁴):

| Quantity | Value |
|---|---|
| BAO shift (P1) | −0.415% in D/r_d at every redshift — reproduced exactly |
| G drift today (lunar ranging, K2) | exactly 0 |
| Exact nulls P9, P11, P12, P13 | all exact (P13 exact for sources below z = 10) |
| G/G₀ in atomic units at recombination | 0.992 |
| G/G₀ in atomic units at nucleosynthesis | 0.970 (like ΔN_eff ≈ −0.18 during nucleosynthesis) |
| CMB acoustic angle at fixed parameters | +0.41% (Planck precision: 0.03%) |
| d_L(GW)/d_L(EM) at z = 20 / z = 50 | 0.9994 / 0.9987 |

**Pressure from published data.**

- Ooba et al. 2017 (arXiv:1702.00742) bound G_rec/G₀ − 1 < 1.9×10⁻³ (95%) with Planck and BAO. Their
  harmonic-attractor models only allow G *larger* in the past, the opposite sign, so the bound does not apply
  directly. But it shows the data are sensitive at the ~0.2% level, and this variant needs −0.8%.
- Ballardini, Finelli & Sapone 2022 (arXiv:2111.09168): G today differs from the radiation era by less than 3%
  (95%). This variant sits at that edge.
- Alvey et al. 2020 (arXiv:1910.10730): G_BBN/G₀ = 0.99 +0.06/−0.05 (2σ). Compatible.

**The joint fit (v20.1).** [analyses/joint_fit.md](analyses/joint_fit.md) fits the variant, with the cosmological
parameters free, to the Planck 2018 CMB distance priors and the DESI DR2 BAO data. The variant survives:
Δχ² = −0.09 relative to ΛCDM. P1's signature does not. The fit absorbs the variant into H₀, which falls from
68.5 to 67.9 km/s/Mpc, and after the refit D/r_d differs from ΛCDM by less than 0.005% at every DESI redshift.
The same degeneracy leaves the exponent almost unconstrained by these data. Nucleosynthesis bounds it to
−1.4×10⁻³ < q < 1.8×10⁻³ (2σ), which caps the H₀ this variant can reach at 67.3–69.5 km/s/Mpc: it does not
address the Hubble tension.

**What remains distinct.** Only early-universe gravity. At the P1-tuned value, G in atomic units is 0.992 of
today's at recombination and 0.970 at nucleosynthesis, tied by ln(G_BBN/G₀) = 3.80 × ln(G_rec/G₀). Compressed CMB
priors cannot see this; a full-spectrum CMB fit and tighter nucleosynthesis bounds can. The closest published
measurement, Lamine et al. (A&A 2025, doi:10.1051/0004-6361/202451602, arXiv:2407.15553), determines a single
cosmological G from Planck PR4, DESI DR1 BAO and the nucleosynthesis helium fraction to 1.8%, consistent with the
laboratory value. The variant's shifts are of the same order, so current data do not decisively test it, and a
few-fold improvement would. The comparison is indicative only: that analysis assumes one G at all epochs, while
the variant's G changes with time. This content is registered as P14 (v20.1, problem 5).

## 2. The P8 revision r2 history is not "the same p as P1"

The P8 r2 pipeline uses the history H(z) = H_ΛCDM(z)·(1+z)^p and its texts call this "the same metrology
modulation P1 applies". Computed consistently, that history moves the BAO ruler in the **opposite** direction
(+0.47% in D/r_d instead of −0.42%). The *conclusion* of P8 r2 — the redshift drift is indistinguishable from
ΛCDM's — holds in every coherent reading (the early-transition variant of problem 1 gives exactly ΛCDM's drift
below z = 10). The description of its history does not. Flagged; the registered output is unchanged. The joint fit of
problem 1 adds that this history, at the canonical p, fits the CMB and BAO data worse than ΛCDM (Δχ² = +2.5); the
data prefer the opposite sign of p.

## 3. P2's amplification factor is not derived

The P2 pipeline multiplies the σ change by an amplification factor K_σ = 50 and predicts an absorption trough
8.66% deeper than ΛCDM at z = 17. Nothing derives that factor. Under universal scaling the relevant
dimensionless rates do not change at all; in the early-transition variant, G at z = 17 differs from today by
0.085%. P2 is therefore probably indistinguishable from ΛCDM too.

## 4. The CMB acoustic-angle assumption

P1's convention, and the w₀wₐ diagnostic built on it ([analyses/w0wa_rd_shift.md](analyses/w0wa_rd_shift.md)),
assume the CMB acoustic angle θ* is unchanged. In the only reading that reproduces P1 it moves by +0.41% at
fixed parameters. The conclusions of that diagnostic therefore hold only for the heuristic convention; the joint
fit of problem 1 supersedes them.

**Resolved by the joint fit (v20.1).** With the acoustic scale in the likelihood, the coherent reading restores
θ* by lowering H₀ by 0.9%, where the heuristic convention had found a +0.42% bias. The w₀wₐ diagnostic's
conclusions do not carry over to the coherent reading.

## 5. What this means for the kill conditions

Of the five forward tests in kill condition K0: P8 is ΛCDM-degenerate, P2 probably is, P12 is an exact null
shared with ΛCDM, and P10 tests a separate T4 module. The joint fit (problem 1, v20.1) settles P1: its only
coherent reading survives, but P1's registered statistic cannot tell it from ΛCDM, because the shift is absorbed
into H₀ once the cosmological parameters are refitted (the flag on P1 explains why the statistic would even fail
spuriously at fine enough precision). The kill-condition scope and threshold are left unchanged.

What still distinguishes the GSC core from ΛCDM is therefore weaker gravity, relative to atoms, in the early
universe (problem 1), plus the T3 θ-trajectory behind P5. None of the forward tests probes the first. Under K0.3
it counts only if registered as a new forward prediction. Until then, the registered late-time content of the
core is observationally indistinguishable from ΛCDM, which is the situation the conformal-reduction clause K0.4
addresses. It does not fire outright, because the early-gravity content and the T3 and T4 modules remain
testable. The early-gravity prediction was registered as P14 in v20.1, under K0.3, with the clause that its
failure triggers K0.4. The earlier text of this problem recorded the possibility before the computation was done.

## 6. Registered pipeline descriptions name modules that were never built

The pipeline sections of the registered statements P1–P7 describe dedicated modules — for example a cosmic-dawn
module with recombination, spin-temperature and heating components (P2), a birefringence integrator fed by an FRG
calculation (P4), or a string-network evolver (P6). None of these was ever written. Each registered output comes
from a single simplified script in `pipelines/`, often parametric (see problem 3). The registered statements are
kept as written and each carries an editorial flag; the claim checker lists the unbuilt module paths explicitly
rather than exempting them by pattern. A reader should treat the physics of P2–P7 as parametric sketches, not as
the computations their statements describe.

## 7. Long-standing gaps

Not new, listed in [THEORY.md](THEORY.md) §9: no derivation of σ_*; compressed CMB priors only; linear
perturbations only; the σ–F̃F, defect and quantum-reference-frame modules lack their calculations; cryptographic
signing of the register is specified but not yet executed.

## 8. Paper A's late-time fit is not reproduced in this package

Paper A §4 states that the three σ(t) families fit the late-time data (supernovae, BAO, compressed CMB priors,
fσ8) within ΔAIC < 4 of ΛCDM, and Paper B builds on that calibration. The values in Paper A's fit table are
illustrative and its Δχ² entries are placeholders, as the paper itself notes; the earlier fitting code is not part
of this package (it remains in the project's git history, tag `v12.7-final`). No registered prediction depends on
the fit: the canonical parameter comes from the P1 pipeline's scan against the DESI DR1-era precision
([gsc/canonical_params.py](gsc/canonical_params.py)). What decides it: a refit of the three families with code
shipped in the package, ideally together with the joint CMB + BAO fit that problem 1 calls for. Until then the
statement is flagged in both papers.
