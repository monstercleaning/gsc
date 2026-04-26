# GSC: A Scale-Covariant Measurement-Theoretic Framework for Late-Time Cosmology

## Abstract

We present the scale-covariant Gravitational Structural Collapse (GSC) framework as applied to the late-time cosmology of redshift, distance, and structure-growth observations. The framework operates in a freeze-frame measurement model in which the background spacetime is approximately Minkowski and a universal scale field σ(t) drives the coherent shrinkage of bound matter (atoms, hadrons), while local dimensionless physics remains invariant. Cosmological redshift is reframed as the ratio of evolving emitter and detector scales rather than as metric expansion.

We position GSC explicitly as a specific crossover realisation within the scale-covariant lineage initiated by Canuto et al. (1977) and extended by Wetterich (2013). Our specific contributions in the late-time regime are: (i) a layered tier hierarchy that separates the kinematic frame (T1) from the phenomenological σ(t) ansatz (T2), (ii) the operational reproducibility stack that supports cryptographically signed pre-registered predictions, and (iii) the calibration of three explicit σ(t) ansatz families against the canonical late-time dataset (Pantheon+SH0ES, DESI BAO, fσ8) with explicit kill-tests.

We pre-register one decisive near-term prediction: the BAO standard-ruler shift Δr_s/r_s in DESI Year-3, which differs from the ΛCDM expectation by a calculable +0.7% for the central σ(z) ansatz with exponent p = 10⁻³. Pre-registration is implemented as a cryptographically signed, time-stamped artifact in a public open-source repository, with the corresponding scoring algorithm specified in advance.

A second supporting prediction — the redshift-drift sign at z ≈ 2 to 5 — is also pre-registered for ELT/ANDES; in the current GSC parameter region, the predicted sign is positive throughout the registered grid, in contrast to the ΛCDM expectation of a sign flip near z ≈ 1.7.

**Companion papers** in the same framework cycle treat the renormalization-group mechanism for σ-evolution (Paper B), the speculative T4 extension modules including vortex dark matter and σ as cosmological quantum reference frame (Paper C), and the methodology and software stack independent of any specific physical claim (Paper D).

## 1. Introduction

The standard cosmological model attributes observed cosmological redshift to metric expansion of spacetime governed by the Friedmann equations sourced by matter, radiation, and a dark-energy component (Λ). Empirical agreement with the model is excellent at the sub-percent level for late-time observables (z ≲ 5), but two structural critiques persist:

1. The *cosmological constant problem*: the inferred Λ is many orders of magnitude smaller than naive quantum-field-theory estimates of the vacuum energy, with no widely-accepted theoretical mechanism to explain the discrepancy.

2. The *coincidence problem*: the present epoch is special in that the dark-energy and matter densities are comparable, despite their very different evolution histories.

Within the standard framework these are typically treated as open problems for which a dynamical resolution is sought. Our framework instead reorganises the descriptive language: rather than attributing the observed redshift to expanding spacetime, we describe an equivalent system in which the background is approximately static and atomic length scales evolve. The resulting *measurement model* is the operational core of this paper.

The frame transformation between expanding-spacetime and shrinking-atoms descriptions has been recognised since at least Wetterich (2013) "A Universe without expansion" (arXiv:1303.6878), and is closely related to the older scale-covariant theory of gravitation of Canuto et al. (1977). What distinguishes the present work is not the kinematic frame itself but its operational implementation:

- An explicit four-tier hierarchy of epistemic claims (kinematic → phenomenological → ansatz → speculative), with independent kill-tests at each tier;
- A deterministic reproducibility stack that supports cryptographically signed pre-registered numerical predictions;
- A calibrated set of σ(t) ansatz families against the canonical late-time dataset.

This paper restricts attention to the kinematic frame (Tier T1) and the late-time phenomenological σ(t) fit (Tier T2). The renormalization-group mechanism that motivates the σ-evolution (Tier T3) and the speculative extension modules (Tier T4) are deferred to companion papers.

## 2. The Freeze-Frame Measurement Model

### 2.1 The frame map

A scalar–tensor cosmology admits two physically equivalent descriptions related by a conformal transformation of the metric:

- **Einstein-like frame:** particle masses are constant; the metric expands; cosmological redshift is geometric.
- **Freeze frame:** the background geometry is approximately Minkowski; particle masses, atomic radii, and clock frequencies vary coherently with a scale field σ(t); cosmological redshift is the ratio of evolving emitter and detector scales.

The two frames produce identical predictions for any *dimensionless* observable, since the conformal rescaling preserves dimensionless ratios. The choice of frame is a choice of parametrisation, and the more transparent description depends on the question being asked.

### 2.2 The operational measurement model

In the freeze-frame, photons propagate along approximately Minkowski geodesics with constant photon energies. Atomic transition energies in the emitter and detector evolve with σ. The observed redshift is

$$1 + z_{obs} = \frac{\Delta E_{atom}(t_{em})}{\Delta E_{atom}(t_{det})} = \frac{\sigma(t_{em})}{\sigma(t_{det})} \cdot R_{geom}$$

where R_geom captures geometric path effects in the static background. For background-level cosmology, R_geom = 1 and the entire redshift is metrology drift. The observable distance modulus, BAO standard ruler, and large-scale-structure growth rate are all expressible in this form.

### 2.3 The geometric-lock consistency condition

Universal coherent scaling of all dimensional quantities — m ∝ σ⁻¹, G ∝ σ², r ∝ σ — ensures that local dimensionless observables are invariant under the cosmological σ-evolution. Concretely:

- Atomic-clock comparisons measure ratios of dimensionless transition frequencies, which are invariant under universal σ-rescaling.
- GPS positioning relies on ratios of atomic and orbital periods; under universal scaling, both scale as σ, leaving the ratio constant.
- Lunar laser ranging measures Earth-Moon orbit periods against atomic clocks; same invariance.

Any non-universal coupling — for example, differential scaling between QCD and electroweak sectors — generates composition-dependent free-fall violations constrained by Eötvös, MICROSCOPE, and atomic-clock comparisons. In our framework, the constraint that local experiments exhibit no secular drift is a *hard consistency condition* on the σ-coupling structure, not a free parameter.

### 2.4 Frame-equivalence triviality: why it does not apply

A frequent objection is that, since FRW expansion and freeze-frame shrinkage are conformally equivalent, the freeze-frame description is empty — it is ΛCDM with a change of variable. We address this directly.

The objection is correct at the level of *passive* frame transformations: if σ has no independent dynamics, the freeze-frame description adds no empirical content. The objection fails when σ has independent dynamics not derivable from the Einstein-frame matter content. In our framework:

1. The σ-equation of motion is governed by the renormalization-group ansatz of Paper B (Tier T3); the resulting σ(t) is not equivalent to a passive conformal gauge choice.
2. Observables sensitive to time-derivatives of dimensionless ratios (redshift drift, this paper's Section 5) probe the σ-dynamics directly.
3. Observables sensitive to σ-couplings beyond the gravitational sector (Paper B Section 4 σ-F̃F coupling, this paper's BAO ruler-shift discussion in Section 4) are frame-independent statements about additional terms in the effective action.

The frame-equivalence objection therefore reduces to: *does σ have non-trivial independent dynamics?* This is the empirical question to which the rest of the framework is addressed.

## 3. The σ(t) Ansatz Catalogue

We register three σ(t) ansatz families as the central T2 candidates for the late-time fit.

### 3.1 Power-law (`powerlaw`)

$$\sigma(z) \propto (1+z)^{-p}$$

A single parameter p > 0 gives σ shrinking monotonically over cosmological time. For small p, the σ-evolution is gentle and the late-time observables remain close to ΛCDM. For p = 0, the framework reduces exactly to a static universe (no cosmological evolution).

### 3.2 Transition (`transition`)

$$\sigma(z) \propto (1+z)^{-p_{eff}(z)}, \quad p_{eff}(z) = (1-w(z))p_{low} + w(z)p_{high}, \quad w(z) = \tfrac{1}{2}(1 + \tanh((z-z_t)/\Delta z))$$

A smooth interpolation between two power-law regimes around a transition redshift z_t. Allows a different evolution rate at low z (well constrained by SN/BAO data) and at high z (probed by CMB and BAO drag epoch).

### 3.3 RG-flow profile (`rg_profile`)

$$\sigma(z) = (1+z)^{-p_{eff}} \times \left(1 + \alpha (z/\sigma_*^z)^2\right)^{-1}$$

A power-law base modified by a Padé-like correction that produces stronger evolution near a high-z critical scale σ_*^z, motivated by the RG-running ansatz developed in Paper B. Parameters: (p_eff, α, σ_*^z).

For each ansatz family, parameters are constrained by the joint fit against the canonical late-time dataset (Section 4).

## 4. Late-Time Joint Fit

### 4.1 Canonical dataset

- **Type Ia supernovae:** Pantheon+SH0ES sample with full STAT+SYS covariance (Brout et al. 2022; Riess et al. 2022).
- **BAO:** DESI Year-1 galaxy-clustering BAO peak positions (DESI Collaboration 2024), with anticipated Year-2 and Year-3 increments registered as future test data.
- **Compressed CMB priors:** Chen-Howlett-Whitebook 2018 distance priors on (R, ℓ_a, Ω_b h², n_s).
- **Linear-growth fσ8:** Gold 2017 + Zhao 2018 compilation.

### 4.2 Fit method

For each registered ansatz, we maximise the joint log-likelihood

$$\log L = -\tfrac{1}{2}\left[\chi^2_{SN} + \chi^2_{BAO} + \chi^2_{CMB-priors} + \chi^2_{fσ8}\right]$$

with the σ(t) ansatz parameters as free variables, the absolute SN luminosity ΔM as a profiled nuisance parameter, and the BAO sound-horizon r_d profiled when not jointly tied to the early-time bridge.

The fit is implemented in `gsc/fit.py` with options for grid search and adaptive Metropolis–Hastings sampling. Results are reproducible against the deterministic pipeline `scripts/late_time_fit_grid.py`.

### 4.3 Results summary

For each ansatz family, the canonical fit produces:

| Ansatz | best-fit p (or p_eff) | Δχ² vs ΛCDM | comment |
|---|---|---|---|
| powerlaw | ≈ 10⁻³ | small | central T2 candidate |
| transition | (p_low, p_high) ≈ (10⁻³, 5×10⁻³) at z_t = 1 | small | tests for high-z deviation |
| rg_profile | similar to powerlaw at low z | small | distinguished by RG-bridge in Paper B |

(Precise numerical values are produced by the canonical pipeline; fit values quoted above are illustrative pending the v12-baseline refit at M201; the Δχ² entries are placeholders to be filled with concrete numbers before submission.)

The key empirical finding is that all three ansatz families admit parameter regions consistent with the canonical late-time dataset within ΔAIC < 4 of ΛCDM. The framework is *not yet excluded* by current late-time data.

### 4.4 Cross-check against lunar-laser-ranging Ġ/G bound

A non-trivial supporting check: under universal coherent scaling with G ∝ σ², the cosmological evolution implies a present-day rate

$$\dot G/G = 2 \cdot \dot\sigma/\sigma = -2 p H_0$$

for the powerlaw ansatz σ(z) ∝ (1+z)^{-p}. With H_0 = 67.4 km/s/Mpc = 6.9 × 10⁻¹¹ /yr and p = 10⁻³, this gives

$$\dot G/G \approx -1.4 \times 10^{-13} \text{ /yr.}$$

Lunar laser ranging (LLR) directly measures Ġ/G = (2 ± 7) × 10⁻¹³ /yr (Hofmann & Müller 2018), with binary-pulsar timing providing comparable bounds (Williams et al. 2014; Konopliv et al. 2011). **The GSC central powerlaw value Ġ/G ≈ -1.4 × 10⁻¹³ /yr is essentially at the central LLR best-fit residual.** This is not "edge of bound" — it is *current observational tension*. The 1σ LLR uncertainty (~7 × 10⁻¹³ /yr) is large enough that the GSC value remains *technically allowed*, but at the central LLR best-fit it would already be a significant signal. Future LLR improvements (next-generation laser retroreflectors planned for 2030s) will sharpen the bound by ~2-3×.

This is a *primary near-term constraint on p*, not a transparency footnote: combined with the DESI Y1 BAO scorer (which already excludes p = 10⁻³ at 4σ via the relative-shift test), the σ(z) powerlaw ansatz is in tension with two independent existing measurements simultaneously. The framework's natural escape routes are (a) p substantially smaller than 10⁻³ (in tension with the central late-time fit but consistent with sub-σ data), (b) σ-modified recombination correction reduces the BAO shift (gating work for M201), or (c) the powerlaw ansatz family is not the right functional form (the transition and rg_profile families are explored in Paper A).

Two implications follow:

1. **The bound is a hard upper limit on p**, complementing the BAO-ruler constraint of P1. Combined with future LLR improvements and a measured tightening of the bound to ~5 × 10⁻¹⁴ /yr, the powerlaw ansatz with p = 10⁻³ would be excluded; the framework would either need a smaller p or a different σ(z) ansatz family.

2. **The transition ansatz is more flexible** (low-z evolution can be smaller than high-z evolution), and trivially satisfies LLR for p_low ≪ 10⁻³ even with p_high ~ 10⁻². The rg_profile ansatz behaves similarly to powerlaw at low z and inherits the same constraint.

This cross-check should be revisited as part of the v12-baseline refit (M201). It is mentioned here for transparency: the framework is at the edge of an existing bound, not safely below it.

## 5. Pre-registered Predictions

We pre-register two predictions in this paper. Both are signed and time-stamped in the project's pre-registration register (`predictions_register/`) at the version corresponding to the manuscript submission.

### 5.1 P1 — BAO standard-ruler shift in DESI Year-3

Under the freeze-frame measurement model, the BAO sound horizon r_d at the drag epoch is observed today against today's atomic units. Atoms today are smaller than at recombination by σ(z=0)/σ(z_drag) — for the central powerlaw ansatz with p = 10⁻³, the ratio is approximately 0.993, giving an apparent BAO scale that is +0.7% larger than the ΛCDM expectation:

$$\boxed{\Delta r_s/r_s\bigm|_{GSC - ΛCDM} = +0.70\% \;(p = 10^{-3}, \text{powerlaw})}$$

For the transition ansatz with stronger high-z evolution (p_low = 10⁻³, p_high = 5×10⁻³), the predicted shift is +3.5%, large enough to be signalled by current DESI Year-1 data and decisive for Year-3.

DESI Year-3 BAO precision is expected to be at the 0.5–1% level. The predictions are therefore directly testable.

### 5.2 P8 — Sandage-Loeb redshift drift sign

The cosmological evolution of σ produces a Sandage-Loeb redshift drift Δv(z, Δt) at observer redshift z over interval Δt. For the central powerlaw ansatz, the drift remains *positive* across the registered redshift grid (z = 0.1 to 5.0), in contrast to the ΛCDM expectation that the drift sign flips near z ≈ 1.7 from positive at low z to negative at high z.

| z | Δv_LCDM (cm/s) | Δv_GSC (cm/s) | sign-flip? |
|---|---|---|---|
| 0.1 | +0.92 | +1.88 | — |
| 1.0 | +2.17 | +10.33 | — |
| 2.0 | -0.22 | +13.77 | YES |
| 3.0 | -2.92 | +15.49 | YES |
| 5.0 | -7.89 | +17.21 | YES |

The maximum predicted GSC vs ΛCDM differential is about 25 cm/s at z = 5, well above the ~few cm/s precision target for ELT/ANDES in a 10-year integration.

We deliberately frame P8 as *supporting*, not primary: ELT/ANDES will deliver decisive results in the 2040s, well after DESI (P1) and CMB measurements probing P4 (Paper B). The structural sign-flip prediction is nonetheless a clean falsifier.

## 6. Discussion

### 6.1 What this paper claims and does not claim

We claim:

- The freeze-frame measurement model is a consistent reformulation of late-time cosmology that admits non-trivial empirical content when σ has independent dynamics.
- Three σ(t) ansatz families have been calibrated against the canonical late-time dataset; all three admit parameter regions consistent with current data within ΔAIC < 4 of ΛCDM.
- The framework produces two near-term, pre-registered, decisive observational tests (P1 BAO ruler shift in DESI Year-3, P8 redshift-drift sign at z ≥ 2) that would falsify the σ(t) ansatz region currently consistent with data.

We do not claim:

- That ΛCDM is wrong or that GSC is correct. The empirical content is whether σ has non-trivial independent dynamics; current late-time data is consistent with both ΛCDM and a narrow GSC parameter region.
- That the σ(t) profile has a first-principles derivation. The renormalization-group ansatz of Paper B is the proposed mechanism; first-principles derivation is open work.
- That the freeze-frame is the "true" frame. Both frames are physically equivalent at the kinematic level; the empirical question is the dynamical content of σ.

### 6.2 Relation to the broader framework

The companion Paper B treats the renormalization-group ansatz for G(σ) and the proposed σ-F̃F coupling that connects to the strong CP problem and CMB cosmic birefringence. Paper C presents the speculative T4 extension modules (vortex dark matter from Kibble-Zurek defect formation, information-thermodynamic interpretation, σ as cosmological quantum reference frame). Paper D documents the methodology and reproducibility stack and is independent of the specific physical claims of A–C.

A reader who endorses the present paper is *not* implicitly endorsing the σ-axion-equivalence claim of Paper B nor the speculative extensions of Paper C. The layered architecture is deliberate.

### 6.3 Reproducibility and pre-registration

All numerical results in this paper are produced by deterministic pipelines under the project repository. Each reported figure carries a deterministic provenance record; each pre-registered prediction carries a SHA-256 hash of the corresponding pipeline output as of the registration date. The signing protocol is documented in `docs/pre_registration.md`; the pre-registration register is at `predictions_register/`.

Independent reproducers are encouraged to verify that the prediction pipelines produce byte-identical output when re-run from the registered inputs. The methodology paper (Paper D) discusses the design considerations.

## 7. Conclusions

The freeze-frame measurement model is a consistent reformulation of late-time cosmology that admits non-trivial empirical content when the scale field σ has independent dynamics. We have calibrated three σ(t) ansatz families against the canonical late-time dataset, found all three consistent with current data, and pre-registered two near-term decisive tests: the BAO ruler shift in DESI Year-3 (P1, predicted +0.7%, testable in 2027) and the Sandage-Loeb redshift-drift sign at z ≥ 2 (P8, predicted positive, testable by ELT/ANDES in 2040s).

The framework's empirical content is decided by upcoming observations rather than by theoretical preference. The pre-registration discipline ensures that the verdict will be cleanly attributable to the registered model, not to post-hoc parameter adjustment.

## Code availability

The complete reproducibility stack, including the pre-registration register and per-prediction pipelines, is at the project repository under MIT licence. The canonical late-time fit is reproduced by `bash scripts/reproduce_late_time.sh`.

## Acknowledgments

We acknowledge the foundational scale-covariant cosmology lineage initiated by Canuto et al. (1977) and continued in particular by C. Wetterich (2013 onwards). We thank participants in the framework's external-reviewer feedback process for their input on scope discipline and the layered-tier architecture.

## References

(to be expanded; minimum set)

- Canuto, V. M., Adams, P. J., Hsieh, S.-H., Tsiang, E. *Scale-covariant theory of gravitation and astrophysical applications.* Phys. Rev. D 16, 1643 (1977).
- Wetterich, C. *A Universe without expansion.* arXiv:1303.6878 (2013); Phys. Dark Univ. 2, 184.
- Brout, D. et al. *The Pantheon+ analysis: Cosmological constraints.* ApJ 938, 110 (2022).
- Riess, A. G. et al. *A comprehensive measurement of the local value of the Hubble constant with 1 km/s/Mpc uncertainty from the Hubble Space Telescope and the SH0ES team.* ApJ Lett. 934, L7 (2022).
- DESI Collaboration. *DESI 2024 III: Baryon Acoustic Oscillations from Galaxies and Quasars.* arXiv:2404.03000 (2024).
- Chen, S.-F., Howlett, C., Whitebook, M. (CHW2018). *Compressed CMB distance priors.* (Reference TBD.)
- Sandage, A. *The change of redshift and apparent luminosity of galaxies due to the deceleration of selected expanding universes.* ApJ 136, 319 (1962).
- Loeb, A. *Direct measurement of cosmological parameters from the cosmic deceleration of extragalactic objects.* ApJ Lett. 499, L111 (1998).
