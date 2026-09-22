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

**What decides it.** A joint CMB + BAO fit of the early-transition variant. If it survives, the framework gains
its first coherent, distinguishable prediction: weaker gravity (relative to atoms) in the early universe, tied
to the BAO ruler and to nucleosynthesis. If it fails, see problem 5.

## 2. The P8 revision r2 history is not "the same p as P1"

The P8 r2 pipeline uses the history H(z) = H_ΛCDM(z)·(1+z)^p and its texts call this "the same metrology
modulation P1 applies". Computed consistently, that history moves the BAO ruler in the **opposite** direction
(+0.47% in D/r_d instead of −0.42%). The *conclusion* of P8 r2 — the redshift drift is indistinguishable from
ΛCDM's — holds in every coherent reading (the early-transition variant of problem 1 gives exactly ΛCDM's drift
below z = 10). The description of its history does not. Flagged; the registered output is unchanged.

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

## 5. What this means for the kill conditions

Of the five forward tests in kill condition K0: P8 is ΛCDM-degenerate, P2 probably is, P12 is an exact null
shared with ΛCDM, P10 tests a separate T4 module, and P1 depends on problem 1. If the early-transition variant
fails its joint fit, the physics case has no remaining content distinct from ΛCDM, and the conformal-reduction
clause K0.4 applies: GSC stands as an exact re-description of standard cosmology with a verification method
attached. This possible outcome is recorded here before the computation is done.

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
