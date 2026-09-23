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
universe (problem 1), plus the T3 θ-trajectory behind P5. None of K0's five forward tests probes the first; under
K0.3 it counts only as a new forward prediction, and it was registered as P14 in v20.1, with the clause that its
failure triggers K0.4. The registered late-time content of the core is observationally indistinguishable from
ΛCDM, which is the situation the conformal-reduction clause K0.4 addresses. It does not fire, because P14 and the
T3 and T4 modules remain testable. The earlier text of this problem recorded the possibility before the
computation was done.

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

## 9. A gravitational cause for the changing standards: timescape tested against DESI

**The idea.** GSC's intuition is that what changes is not space but the standards measured with matter. Problem 1
showed that a universal change is only a change of units, so the change must differ from place to place, and a
known force should cause it. The published theory that does exactly this is Wiltshire's timescape cosmology: in a
lumpy universe, clocks and rulers in galaxies are calibrated differently from the volume average, which
fast-expanding voids dominate, and reading the data with our local clocks mimics cosmic acceleration without dark
energy. It uses ordinary general relativity only. With Pantheon+ supernovae it was reported to fit better than ΛCDM
(Seifert et al., MNRAS Letters 537, L55, 2025).

**The test (v20.1).** [analyses/timescape_fit.md](analyses/timescape_fit.md) implements the model's tracker
solution from Wiltshire, PRD 80, 123512 (2009), reproduces the numbers published there, and fits it to the DESI
DR2 BAO data with the BAO scale left free, so that only the shape of the distance–redshift relation is tested.
Timescape fits much worse than ΛCDM with the same number of parameters: χ² = 62.4 against 10.5 for 13 data points
(Δχ² = +52). The calibration-free Alcock–Paczyński ratio alone gives Δχ² = +45, and the mismatch is a property of
the model's shape rather than of its parameter: at z = 0.93 the ratio is 1.34–1.38 for any void fraction, where
DESI measures 1.22 ± 0.02. The result holds with DESI's other compression (Δχ² = +57) and without the worst-fitting
bin (Δχ² = +16). At the void fractions preferred by supernovae (0.737) and by the CMB (0.627), the BAO fit is worse
still.

**What this does and does not show.** The most developed theory in which gravity replaces dark energy through
the calibration of matter-based standards is strongly disfavoured by DESI's radial BAO measurements, in the form
its author published. Two caveats remain. DESI compresses its data with a fiducial ΛCDM cosmology, and a model this
far from the fiducial may need a dedicated reanalysis; and the tracker solution is the simplest version of
timescape. The redshift drift would decide cleanly: timescape changes sign at z ≈ 0.7–1.5, ΛCDM at z ≈ 2.1. It is
not registered, because the model is already disfavoured by existing data.

## 10. A gravitational source for dark energy: black holes coupled to the expansion

**The idea.** The second published way to replace dark energy with gravity. If black holes have interiors of vacuum
energy, general relativity can couple them to the expansion, so that each one grows as m ∝ a³ (Farrah et al., ApJL
944, L31, 2023). A population of them then keeps a constant density and acts like a cosmological constant, and dark
energy grows as massive stars collapse into black holes, consuming baryons (Croker et al., JCAP 10 (2024) 094;
Ahlen et al., PRL 135, 081003, 2025).

**The expansion-history test (v20.1).** [analyses/ccbh_fit.md](analyses/ccbh_fit.md) implements Ahlen et al.'s
equations with the Madau star-formation histories and fits the same CMB + BAO data as problem 1. With the same number
of free parameters it fits almost as well as ΛCDM: Δχ² = +1.7 and +2.6 for the two star-formation histories, with
H₀ ≈ 70.3 and about half the baryons converted. The published analysis, with the full Planck likelihood, finds
H₀ = 70.03, half the baryons converted and Δχ² = +6.1 for the same histories, and no penalty with a JWST-based
history. The model fits the CMB almost exactly and the BAO less well than ΛCDM.

**The local tests are unfavourable.** Every black hole must have grown by (1+z)³ since it formed, which the black
holes we can weigh contradict:

- Gaia BH1 and BH2 (Andrae & El-Badry, A&A 673, L10, 2023): 70% and 77% probability that they formed below
  2.2 M_⊙, the maximum neutron-star mass.
- The globular cluster NGC 3201 (Rodriguez, ApJL 2023, doi:10.3847/2041-8213/acc9b6): both black holes would have
  to be seen almost face-on (probability ≤ 10⁻⁴), or one formed below 2.2 M_⊙.
- LIGO–Virgo–KAGRA mergers (Amendola et al., MNRAS 528, 2024): k < 2.1 at 2σ if black holes form above 2 M_⊙;
  k = 3 needs formation masses below 0.5 M_⊙.
- Merger rates (Ghodla et al., 2023): they would exceed the observed rate by orders of magnitude.
- JWST quasars (Lei et al., Sci. China Phys. Mech. Astron. 67, 229811, 2024): about 2σ tension.

Proponents argue that coupled black holes need not obey the neutron-star mass limit. Unless that is shown, the
growth that dark energy requires conflicts with the black holes we can measure.

**The same pattern as GSC.** The expansion history can be fitted; the local signature of the mechanism is the
problem, as lunar laser ranging is for GSC's canonical parameter. Not registered.

## 11. A cosmic origin for the dark-matter scale: does Milgrom's a0 follow the expansion rate?

**The idea.** In galaxies, dark matter shows up only where the acceleration falls below about
a0 = 1.2 × 10⁻¹⁰ m/s², the scale of the radial acceleration relation (Milgrom's constant). a0 is close to
c H₀ / 2π, the speed of light times today's expansion rate, a coincidence noted since Milgrom's first papers. In
GSC's reading H is the rate at which the matter-based standards shrink. If the coincidence is physical, the
simplest link ties a0 to that rate at every epoch, a0(z) = a0(0) H(z)/H₀, three to four times today's value at
z = 2–2.5, and the dark-matter phenomenon would be set by the shrinking itself. THEORY.md §6.2 proposes such an
evolving scale.

**What was already known.**

- Milgrom (arXiv:1703.06110), from six rotation curves at z = 0.9–2.4: a value about four times today's at
  z ≈ 2 is all but excluded.
- Tully–Fisher data to z = 1.2 exclude, within their formal errors, both a0 ∝ c H(z) and a constant tied to dark
  energy; allowing for systematics, they marginally favour the constant (Limbach, Psaltis & Özel,
  arXiv:0809.2790).
- Ciocan et al. (A&A 709, L16, 2026) find a0 rising over z = 0.33–1.44 in 79 lower-mass galaxies, to 2.2–2.6 at
  z ≈ 1 depending on the mass model.
- A ΛCDM simulation shows a rise of the same kind, a factor of about 3 from z = 0 to 2 (Mayer et al.,
  arXiv:2206.04333), so a rise alone would not point to new physics.
- Even the local value depends on the sample: 1.20 ± 0.24 from SPARC, 1.50 ± 0.05 from HI-selected galaxies out to
  z = 0.09, with no evolution over that short range (Vărăşteanu et al., arXiv:2608.03576).

**Our test (v20.1).** [analyses/a0_evolution.md](analyses/a0_evolution.md) fits the evolution to the 100 massive
star-forming disks of RC100 (Nestor Shachar et al., ApJ 944, 78, 2023) at z = 0.6–2.5. For each galaxy, their
Table 3 gives the circular velocity and the dark-matter fraction at the effective radius, from the authors' mass
models, and the radial acceleration relation then fixes a0. The table was transcribed by hand and checked against
the statistics the paper quotes and against an independent machine reading ([data/README.md](data/README.md)).
For a0(z) = A (H/H₀)^p the fit gives p = −0.55 (1σ: −0.83 to −0.27). p = 1 is 5.1σ away, a constant is 2.0σ away,
and a constant fits with a0 = 1.18, today's value. At z ≈ 2.2, 41 galaxies give a0 = 0.91 (0.80–1.04), where the
link predicts 3.5–4.0. Across nine variants (interpolating function, fixed intrinsic scatter, data cuts) p = 1 is
excluded at 2.8σ to 5.4σ; the weakest case fixes the intrinsic scatter at the large value Ciocan et al. find.
Mocks with the table's errors show that the fit is unbiased and that a sample like this separates p = 0 from p = 1
by about 3.5–4σ.

**The data disagree with each other.** In Ciocan et al.'s own MOND fits, the rise follows H(z) almost exactly,
within 4% of 1.20 H(z)/H₀ over their range; with dark-matter halos it is somewhat faster, which is what the
authors report. But where the two samples overlap, at z ≈ 0.8, RC100 gives 1.45 against their 2.0–2.4, and their
trend continued to z ≈ 2.2 gives 3.7–4.7 against RC100's 0.91. No single a0(z), constant or evolving, fits both
at face value. ΛCDM allows that, because there the scale emerges from galaxy formation and can differ between
populations. A universal constant does not, whether it is fixed or tied to the expansion.

**What this does and does not show.** The simplest link between the dark-matter scale and the cosmic rate fails
its strongest available test: at z ≈ 2, where it predicts the largest effect, the rotation curves show none. The
caveats are real. The dark-matter fractions come from mass models with dark-matter halos, the error correlations
are not published, and beam smearing and pressure support grow with redshift. To allow a0 ∝ H(z), the median
dark-matter fraction at z ≈ 2.2 would have to be 0.55 instead of 0.26. What would revive the idea is a
measurement at z ≥ 2 of the kind Ciocan et al. made below z = 1.5, finding a0 ≈ 1.2 H(z)/H₀, together with a
reason why RC100's fractions are too low. A link to the cosmological constant instead, with a0 constant, is
Milgrom's long-standing proposal, not a GSC prediction. Not registered.
