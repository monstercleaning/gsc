# GSC Project — Consolidated Roadmap & Advisory Document

**Version:** 2.8 (Final)  
**Date:** February 2026  
**Scope:** Actionable roadmap based on five independent reviews of GSC v10.1.1-phase3-m137  
**Audience:** Project lead (Dimitar Baev) — non-physicist working with AI assistance  
**Changelog v2.8:** Paper 2: added redshift re-mapping (z_obs modified if ε≠0, Rydberg constant evolves) and Chandrasekhar mass (M_Ch ∝ G⁻³/²) as explicit Level 3 example. Paper 1: added dual structure (Proposition A analytic + Proposition B data-dependent), BAO dimensionless formulation note, drift experiment landscape (ESPRESSO/VLT, SKA, ANDES/ELT). Task 4A.−0: clarified c_s²=1 for canonical quintessence vs general EFT. Escape routes 12 (IDE/interacting dark sectors, breaks ρ_m∝a⁻³) and 13 (phantom/WEC violation). Added assumption (4) standard matter conservation to analytical bound. Route 2: added attractor/least-coupling as third suppression mechanism (Damour & Polyakov 1994). Atomic clock precision: 10⁻¹⁷–10⁻¹⁸/yr range (Rosenband et al. 2008). arXiv policy: concrete date + strategies. DESI: DR1 baseline + DR2 robustness. Prior art: added drift experiments, IDE, attractor mechanism, phantom references. Part M: 13 escape routes.  
**Changelog v2.7:** Referee-hardening pass. MICROSCOPE, ESPRESSO/VLT, DESI, PRD Letters, Ω_m₀ bound precision, Triangle 1, Paper 2/3 referee-proofing, escape routes 10-11, tone fixes.
**Changelog v2.5:** Strengthened Task 4A.−0 with stability constraints (w ≥ −1, c_s² ≥ 0). Strengthened escape route 6 with quasar spectroscopy constraint. Added Webb/Murphy references.  
**Changelog v2.4:** Added pre-check tasks 4A.−1 and 4A.−0. Added escape routes 6-9. Reordered start sequence.  
**Changelog v2.3:** Fixed ε-pair error in DM Option D, updated DESI likelihood status (DR1 published April 2024), replaced unrealistic Nature Astronomy target for Paper 4, corrected Scenario 1 logic (Paper 3 only constrains escape route 2), moved arXiv endorsement to Paper 0 context, resolved E.5 internal contradiction, added Paper 0 success criteria, corrected Paper 0 "foundation" claim, made Paper 4 success criterion realistic.  
**Changelog v2.2:** Fixed 6 factual errors (false number precision, convexity claim, unsubstantiated ε magnitude, outdated WEP bound, Wetterich date, attractor regime ambiguity). Fixed 5 logical issues (consistency triangle dependencies, Paper 1 scope, Paper 1→2 motivational link, arXiv endorsement, DESI WG accessibility). Added 4 missing items (Paper 0, duplication risk for Paper 3, AI disclosure policy, GSC name explanation).  
**Changelog v2.1:** Added collaborator strategy, contingency planning, frame invariance prerequisite, consistency triangles formalization, ε-framework readiness assessment, computational resources, escape-to-theory mapping, and adjusted timelines for realistic solo+AI execution.

**Note on project name:** GSC stands for "Gravitational Structural Collapse." The name reflects the original conceptual framing (gravity as structural collapse of physical scales rather than spacetime expansion). As the project evolved toward measurement model formalism and precision testing, the name became somewhat misleading. For external publications, consider whether the GSC name or a more descriptive title better serves each paper's content.

---

## Part A: Honest Assessment — What GSC Is and Is Not

### A.1 What exists today (facts, not opinions)

The repository contains approximately 125,000 lines of Python across 510 files, with 311 test files. All Phase-3 m137 tests pass. (Verified from repo snapshot: 510 Python files, 125,423 lines, 311 test files.) The infrastructure includes SHA256-verified artifacts, JSON schema validation, a claim ledger with automated overclaim linting, deterministic reproducibility, Docker containers for CAMB/CLASS, and automated referee-pack generation.

This engineering layer is unusually strong for a single-team alternative cosmology codebase, with full reproducibility artifacts and claim management. This assessment is based on comparison with published alternative cosmology codebases.

### A.2 What the physics actually is (no sugarcoating)

**SigmaTensor-v1** is a canonical scalar field with exponential potential in Einstein frame:

```
S = ∫ d⁴x √(-g) [½R - ½(∂φ)² - V₀e^{-λφ}] + S_matter + S_radiation
```

This is standard quintessence, studied since Ratra & Peebles (1988) and Wetterich (1988). In the scalar-field-dominated regime, the attractor solution gives power-law expansion a(t) ∝ t^{2/λ²}, which maps to H(z) = H₀(1+z)^p with p = λ²/2. (In the tracker regime, where the scalar follows the background equation of state, the dynamics are different — the document should specify which regime SigmaTensor-v1 operates in.)

The freeze-frame reinterpretation (shrinking matter instead of expanding space) is a conformal frame choice. Under field redefinition, it produces identical observables to the standard Einstein-frame description. This is well-known physics, not a deficiency — but it means the frame choice alone does not generate new predictions.

The RG running ansatz G(k) = G_IR/(1-(k/k*)²) is a phenomenological parametrization. The k↔σ identification (k ∝ 1/σ) is explicitly labelled as a working ansatz, not a derivation. The pole-like form contradicts asymptotic safety (which predicts a UV fixed point, not a pole).

### A.3 The E2 no-go result (the most important finding in the project)

The Early-Time E2 synthesis demonstrates:

- Under all tested deformation families, **no region exists** with simultaneously drift_sign_ok=True in z~2-5 AND strict CHW2018 CMB closure (χ² ~ O(1))
- Even at drift amplitude → 0⁺ (barely positive), χ²_cmb ≈ 1.54×10⁴
- The dominant bottleneck is D_M(z*) — comoving distance to last scattering
- Neutrino-sector adjustments mainly shift r_s(z*) without removing the distance closure requirement

This is the project's most valuable scientific finding. It is not a failure — it is a result.

**Critical clarification (from independent numerical verification):** Positive drift at z ∈ [2,5] was never a prediction of the base SigmaTensor-v1 theory. It was an artifact of the G(k) pole ansatz, which is acknowledged as unphysical (see E.2). For standard matter with Ω_m₀ ≈ 0.315, an analytical bound shows that positive drift at redshift z requires Ω_m₀ < 1/(1+z) — for Ω_m₀ = 0.315 this fails at z ≳ 2.2, and is deeply violated across the entire z ∈ [2,5] range. **Explicit assumptions of this bound:** (1) spatially flat FLRW (Ω_k = 0); (2) standard Friedmann equation (GR); (3) all energy components have non-negative energy density (ρ_DE ≥ 0, ρ_r ≥ 0) — i.e., the weak energy condition holds; (4) standard matter conservation (ρ_m ∝ (1+z)³) — i.e., no energy exchange between dark matter and dark energy. If any of these is relaxed (negative curvature, modified gravity, phantom DE, or interacting dark sectors), the bound may weaken or fail. The E2 no-go is therefore a valuable *general* result for the cosmology community (no smooth H(z) model with standard matter, flat geometry, and non-negative DE can produce positive drift at z ≳ 2.2), but it is not a crisis for GSC specifically. The project's core novelty (measurement model formalism, ε-parametrization, kill-test methodology) is entirely independent of the drift sign question.

### A.4 Why drift-distance trade-off is structural

The Sandage-Loeb formula: ∂z/∂t₀ = H₀(1+z) − H(z)

For positive drift everywhere in z∈[2,5]: H(z) < H₀(1+z) for all z in that range.

But distance observables (BAO angular scales, SN luminosity distances, CMB compressed priors) are integrals of 1/H(z). If H(z) is systematically lower than ΛCDM in z∈[2,5], distance integrals grow, creating catastrophic mismatch with precision measurements (BAO measured at ~1-2% level to z~2).

The drift-positivity constraint (H(z) < H₀(1+z) ∀z∈[2,5]) and the distance constraints (integrals of 1/H(z) fixed by BAO/SN/CMB) impose competing demands on H(z) that cannot be simultaneously satisfied under the tested assumptions. The drift constraint pushes H(z) systematically below H₀(1+z), which inflates distance integrals beyond observational tolerance. This can be formalized as an incompatibility result (see note in Part C, Paper 1). **Technical caveat:** the distance-allowed region is not strictly convex in H-space (since distance depends on 1/H, which is nonlinear in H). The precise mathematical formulation — whether as a separation theorem in an appropriate function space or as a quantitative bound — must be worked out carefully in Paper 1.

---

## Part B: What Is Genuinely Novel in GSC

Three elements survive the critical analysis as genuinely novel contributions:

### B.1 Measurement Model as Explicit Theoretical Layer

Standard cosmology treats the measurement model implicitly: FLRW + GR + constant masses → standard ruler/candle definitions → H(z), D_L(z), etc. This layer is not typically parametrized separately.

GSC's measurement_model.md makes this layer explicit: what clocks measure, what rulers measure, how raw measurements map to cosmological observables. The ε-parametrization (ε_EM, ε_QCD for sector-dependent departures from universal scaling) allows systematic variation of measurement model assumptions.

**Why this matters:** If measurement model assumptions are varied, the same raw data maps to different inferred cosmological parameters. This creates a "measurement model space" M = {M_standard, M_ε, ...} and allows systematic sensitivity analysis. To our knowledge, no widely adopted framework treats the measurement model as an explicit, parameterized layer across EM/QCD/gravity sectors and propagates it through cosmological inference in a unified way.

**Connection to current tensions:** H₀ tension (CMB vs. local) and S₈ tension (CMB vs. weak lensing) could partially reflect measurement model mismatch between EM-based observables (SN, Cepheids), gravity-based observables (lensing, GW sirens), and QCD-based observables (BAO sound horizon). The ε-parametrization provides a framework to test this systematically.

### B.2 Kill-Test-First Methodology

The combination of claim ledger + automated overclaim linting + no-go documentation + risk register + SHA256-verified artifacts has no close parallel in published alternative cosmology projects that we are aware of. This is a methodology that can be exported to any alternative theory project.

### B.3 Precision Null-Test Framework

The ε-parametrization + precision constraints translator provides a unified framework mapping arbitrary departures from universal scaling → sensitivity coefficients → combined bounds from all precision tests (WEP, atomic clocks, Oklo, lunar laser ranging, CMB). More systematic than existing varying-constants literature, which typically tests one constraint at a time.

---

## Part C: Publication Strategy (4 Papers + existing late-time paper)

### Paper 0 (existing): Late-time framework paper

The project has a near-complete late-time paper (`GSC_Framework_v10_1_FINAL.md/pdf/tex`). This should be submitted **regardless of the roadmap decisions below.** It documents the freeze-frame framework, measurement model (Option 2), and late-time observational confrontation as a self-contained contribution.

**Action:** Finalize and submit Paper 0 as the first arXiv posting. This serves as:
- Proof of competence and seriousness for potential collaborators
- Citable reference for Papers 1-4
- The "calling card" for arXiv endorsement requests

**Differentiation from Wetterich (2014):** Paper 0 must NOT be positioned as simply "freeze-frame cosmology" or "universe without expansion" — Wetterich already covered the conformal transformation mathematics. Paper 0's unique contribution is the **explicit measurement model layer**: how local standards of length and time are defined in an evolving-scales metric, and how this affects the mapping from raw observables to inferred cosmological parameters. The abstract and introduction must focus on "metrology of cosmology" as the central novelty, not on the conformal frame mathematics.

**Note:** Paper 0 should be reviewed against the Frame Invariance Document (4A.0) before submission to ensure claims are frame-invariant and prior art (especially Wetterich 2014) is properly cited.

**arXiv endorsement:** Paper 0 is the first planned arXiv submission. First-time submitters need endorsement from an existing arXiv author in the target section (astro-ph.CO or gr-qc). **Policy update (21 Jan 2026):** arXiv has tightened endorsement requirements — institutional email alone no longer suffices for new authors (see arXiv blog). **Safest path:** have a physicist collaborator or co-author serve as submitting author for the first preprint. **Fallback:** post on Zenodo/GitHub with DOI while seeking endorsement. Without endorsement, Paper 0 cannot be posted and the entire visibility strategy stalls. (See also Part K.)

### Paper 1: "Drift-Distance No-Go Theorem for Scale-Covariant Cosmologies"

**Target:** Physical Review D (Letter) or JCAP (standard article)  
**Timeline:** 4-8 months (with collaborator; see Part K)  
**Requires collaborator:** Yes — mathematical cosmologist for analytical proof  
**Can start solo (AI-assisted):** Numerical illustration, escape route catalog, paper structure

**Content:**

1. Define the model class formally: smooth monotonic H(z) parametrizations satisfying H(z) < H₀(1+z) in z∈[2,5] (positive drift condition).

2. State and prove the no-go result:
   - Lemma 1: Positive drift ∀z∈[2,5] implies a lower bound on ∫₀ᶻ dz'/H(z') excess relative to ΛCDM
   - Lemma 2: BAO + SN distance constraints imply an upper bound on allowed excess in ∫₀ᶻ dz'/H(z')
   - Result: The two bounds are incompatible under tested assumptions
   
   **Scope clarification:** The E2 numerical scans tested specific parametric families (polynomial, exponential, Padé deformations). The analytical proof must clearly define the model class it covers. If the proof covers all smooth monotonic H(z), it is stronger than the numerical result. If it requires additional regularity assumptions, state them. The paper should clearly separate: (a) the analytical result (which class is excluded), (b) the numerical illustration (which specific families were tested), and (c) whether the analytical class is broader or narrower than what was numerically scanned.

3. Quantify the gap: how much would distance measurement precision need to degrade for a viable region to exist?

4. Illustrate with numerical scans (existing E2 infrastructure).

5. State explicit assumptions. Each assumption defines an escape route.

**Important honesty note on "theorem" vs. "quantitative bound":** The analytical argument depends on current BAO/SN measurement precision. If the margins between the drift lower bound and the distance upper bound are tight and data-dependent, the result may be better framed as a **strong quantitative bound** ("at current data precision, the gap is X σ") rather than a pure mathematical theorem. Both are publishable and valuable, but the paper must be honest about which one it delivers. A clean theorem says "impossible regardless of data precision"; a quantitative bound says "impossible at current precision, and here is how much precision must degrade for a window to open." The second is actually more informative and practical.

**Escape Route Catalog** (publish as appendix):

| # | Assumption | Escape if relaxed | New constraints | Feasibility | Links to Phase 4C |
|---|---|---|---|---|---|
| 1 | Smooth monotonic H(z) | Feature/bump at z ≳ 5 (between drift range and recombination) | Future high-z BAO, Lyman-α forest, CMB lensing | Speculative, not excluded | Multi-field / phase transition model |
| 2 | Standard recombination | Varying m_e or α at z~1100 | Oklo, clocks, BBN | Highly constrained. **Cannot work as standalone smooth evolution** without a late-time suppression mechanism: requires either Route 1 (sharp phase transition), Route 6 (density-dependent screening), or a dynamical attractor/least-coupling mechanism (Damour & Polyakov 1994) that naturally drives couplings toward GR at late times. Otherwise Oklo (Δα/α < 10⁻⁸ over 2 Gyr) and atomic clocks kill it. | Weyl geometry with varying α → 4C.2 (only viable with suppression mechanism) |
| 3 | Compressed CMB priors | Full Boltzmann hidden degeneracies | Full TT/TE/EE spectrum | Requires CLASS/CAMB mod | CLASS modification → 4C.7 |
| 4 | Standard matter content | Non-standard N_eff or ν masses | BBN, CMB damping tail | Moderately constrained | Extended neutrino sector |
| 5 | Single-field background | Multi-field or phase transition | Theoretical consistency | Open territory | Entirely new model class |
| 6 | Universal screening (ε same everywhere) | Density-dependent screening: ε(z) large at low cosmic density (recombination), suppressed in high-density environments (Earth, solar system) via Chameleon/Symmetron mechanism | MICROSCOPE, **quasar absorption spectra (DLA systems)**, SN through voids, ISW | **Severely constrained.** Chameleon-type screening responds to *local density*, not epoch. Intergalactic voids today (ρ ~ 10⁻³¹ g/cm³) are *less* dense than the z=1100 average (ρ ~ 10⁻²¹ g/cm³), so ε in voids today would *exceed* ε at recombination. **Critical falsifier:** quasar absorption spectra (Damped Lyman-α systems) probe gas in low-density environments at z ~ 1-3 and constrain Δα/α < 10⁻⁵. If ε reached 10⁻² in voids, absorption lines would be shifted by orders of magnitude beyond observed limits. This constraint is stronger than MICROSCOPE for this specific mechanism. Requires extreme and potentially impossible fine-tuning. | Weyl geometry + screening → 4C.2 + 4C.6 (only if quasar constraint can be navigated) |
| 7 | Etherington distance duality (D_L = (1+z)²D_A) | Photon non-conservation (opacity, photon-axion conversion, non-metricity) decouples SN distances from BAO/CMB distances | Distance duality tests, CMB spectrum, SZ effect | Tested and constrained, but not at the level needed to rule out all models. Risky direction. | New observable mapping |
| 8 | FLRW homogeneity-isotropy | LTB voids, backreaction (Buchert, Wiltshire) — drift and distance formulae both change in non-FLRW geometry | CMB isotropy, kinematic SZ, galaxy number counts | Legitimate research direction, but becomes a different theory entirely. Massive work required (light-cone averaging + perturbations). | Entirely new framework |
| 9 | Standard drift formula (Sandage-Loeb with universal time) | If atomic clock time ≠ cosmological time (due to evolving masses/couplings), additional terms appear in drift formula | Varying constants bounds (Δα/α ~ 10⁻¹⁷–10⁻¹⁸/yr locally, depending on clock comparison; Rosenband et al. 2008 Al⁺/Hg⁺ at ~10⁻¹⁷/yr, newer optical lattice clocks approaching 10⁻¹⁸/yr) | Clock drift correction is ~10⁻¹⁷–10⁻¹⁸/yr but drift signal is ~10⁻¹⁰/yr — 7-8 orders of magnitude gap. Cannot flip drift sign. Dead as standalone mechanism. | Only viable if combined with screening (route 6) |
| 10 | Spatial flatness (Ω_k = 0) | If Ω_k < 0 (closed universe), the curvature term subtracts from H², potentially lowering H(z) enough for positive drift | Planck 2018 + BAO: Ω_k = 0.001 ± 0.002 | Does not help quantitatively: even Ω_k = −0.01 shifts the critical z by < 0.1. Effectively dead for z ∈ [2,5] at realistic curvature bounds. | Not a viable direction |
| 11 | Standard Friedmann equation (GR background dynamics) | If background dynamics differ from GR (f(R), braneworld, effective G_eff(a), scalar-tensor), the H²(z) ≥ H₀²Ω_m₀(1+z)³ bound may weaken | Solar system tests, GW propagation, ISW, growth rate | Legitimate and broad class. The Ω_m₀ analytical bound explicitly assumes standard Friedmann. Modified gravity with G_eff(z) < G₀ at z > 2 could in principle lower H(z). | Phase 4C (non-minimal coupling → 4C.2) |
| 12 | Standard matter conservation (ρ_m ∝ a⁻³) | **Interacting Dark Energy (IDE):** if DM decays into DE or exchanges energy with it, matter density at high z is lower than (1+z)³ scaling predicts → H²(z) can be lower → drift may flip sign | CMB perturbations (ISW, lensing), LSS growth rate, galaxy cluster counts | Active research area with viable parameter space. The Ω_m₀ analytical bound explicitly assumes ρ_m ∝ (1+z)³; IDE breaks this. Models exist (e.g., Gavela et al. 2009, Salvatelli et al. 2014) with coupling strengths that are observationally allowed. | Coupling SigmaTensor to DM sector; requires perturbation theory (Phase 4C) |
| 13 | Non-negative energy density / weak energy condition (ρ_DE ≥ 0) | Phantom dark energy (w < −1) or transient negative ρ_DE at high z can lower H²(z) below the matter-only floor | Ghost/gradient instabilities, EFT consistency, vacuum decay | Theoretically risky (ghosts, instabilities). Forbidden for canonical quintessence (SigmaTensor-v1 has w ≥ −1 by construction). Only relevant if model is extended beyond canonical scalar field. | Requires non-canonical kinetic terms (k-essence, ghost condensate) — new model class |

**Why valuable beyond GSC:** Applies to ANY alternative cosmology attempting positive drift at intermediate redshifts. Service to the entire field. **Note:** Since SigmaTensor-v1 does not predict positive drift (see 4A.−1 preliminary result and A.3 clarification), Paper 1 is framed as a general impossibility result, not as a self-falsification of GSC. The analytical bound (Ω_m₀ < 1/(1+z) for positive drift) strengthens the paper: the no-go is not just numerical but has an analytical core.

**Positioning warning:** Do NOT sell Paper 1 as "a theorem that positive drift is impossible" — this sounds trivially obvious to experts who know ΛCDM drift is negative at z > 2. Instead, position it as: (a) a **quantitative bound** on the drift-distance gap (how much must measurement precision degrade for a window to open?), (b) a **systematic escape-route taxonomy** with explicit theory links, and (c) a **service paper** for upcoming drift experiments (ELT/ANDES, ESPRESSO/VLT precursor program, SKA 21cm drift channel): "what classes of modifications could flip sign and what else they would break." This framing preserves novelty and utility.

**Internal structure: two distinct results.** Paper 1 contains two logically independent propositions that should be clearly separated:
- **Proposition A (analytic, assumption-based):** The sign bound. Under GR + FLRW + flat + WEC + standard matter conservation, positive drift at z requires Ω_m₀ < 1/(1+z). This is *purely dynamical* and uses no observational data (no BAO, no SN). Its strength is generality; its weakness is that it has 5 explicit assumptions that each define an escape route.
- **Proposition B (data-dependent, quantitative):** The drift-distance gap. Even if some assumptions of Prop A are relaxed, *how much* must H(z) change to flip drift sign, and what does that cost in distance fit quality? This uses SN/BAO/CMB data and quantifies the gap.
If these are conflated, a referee will say "the analytic part is trivial and the numerical part is model-dependent." Separating them makes each defensible on its own terms.

**BAO/SN formulation note for Paper 1:** Work with dimensionless E(z) = H(z)/H₀ and compare shape constraints from SN. BAO constraints are on D_M(z)/r_d and H(z)·r_d, so r_d must be treated as nuisance (or anchored from CMB/BBN) — state this explicitly in Paper 1's methodology.

**Drift experiment landscape (strengthens "service paper" framing):** The ESPRESSO Redshift Drift Experiment (Cristiani et al. 2025, A&A) on VLT has published a null result and estimated the timeline to detection. SKA 21cm drift observations provide an independent radio channel (Kloeckner et al. 2015). ELT/ANDES remains the primary high-precision optical path (Marconi et al. 2024). Citing these active programs makes Paper 1 immediately relevant to ongoing experimental efforts, not just future ones.

---

### Paper 2: "Measurement Model Dependence in Cosmological Parameter Inference"

**Motivational link to Paper 1:** Paper 1 shows that drift-sign discrimination fails under standard measurement model assumptions. This naturally raises the question: what if the measurement model itself is a hidden degree of freedom? If different physical sectors (EM, QCD, gravity) scale slightly differently, the standard "single H(z)" inference is an assumption, not a fact. Paper 2 tests this assumption systematically.

**Target:** Physical Review D or MNRAS  
**Timeline:** 6-12 months (with collaborator; see Part K)  
**Requires collaborator:** Strongly recommended — observational cosmologist with likelihood code experience  
**Can start solo (AI-assisted):** Formalism, ε-framework development, sensitivity formulae derivation

**Prerequisite:** ε-framework assessment and upgrade (see Part D, task 4A.9)

**Content:**

1. Formalize: What is a measurement model M? How do raw observables (photon counts, frequencies, time intervals, GW strain amplitudes) map to inferred quantities (H(z), D_L, fσ₈) under different M?

2. Parametrize M using ε-parameters:
   - ε_EM: departure of EM-sector scaling from universal
   - ε_QCD: departure of QCD-sector scaling from universal
   - Show: inferred H(z) from SN (EM clocks) differs from inferred H(z) from BAO (QCD rulers) when ε_EM ≠ ε_QCD

3. Compute sensitivity: ∂H₀/∂ε_EM, ∂σ₈/∂ε_QCD, cross-terms.

4. Apply to current tensions:
   - For a given ε_EM − ε_QCD, compute the implied H₀ shift. Determine what magnitude of ε-difference would be required to explain the ~10% H₀ tension.
   - Check: is that required ε-magnitude compatible with laboratory precision bounds (Paper 3)?
   - Does H₀ tension pattern correlate with ε-structure?
   - Does S₈ tension correlate with gravity-sector vs. EM-sector mismatch?
   
   **Critical self-test:** The required ε to explain tensions may turn out to be orders of magnitude larger than what precision bounds allow. If so, this is a null result for measurement model explanation of tensions — still publishable as a systematic exclusion. (See Part J, Scenario 2.)

5. **Consistency triangles** (formalized from second reviewer's recommendation):
   Define cross-checks between independent observable types:
   - Triangle 1: (SN luminosity distances) ↔ (BAO angular scale) ↔ (CMB acoustic scale θ*) — **computable now** with existing data (Pantheon+, DESI DR1, Planck)
   - Triangle 2: (GW siren distances) ↔ (EM distances) ↔ (Planck mass running) — **requires Phase 4C** (non-minimal coupling needed for α_M ≠ 0); include as forecast only in Paper 2
   - Triangle 3: (lensing mass) ↔ (dynamical mass) ↔ (growth rate) — **requires perturbation theory** (Phase 4C.3); include as forecast only in Paper 2
   - **Redshift drift triangle:** (SN distances) ↔ (BAO angular scale) ↔ (redshift drift) — computable in code but **not testable with current data** (drift measurement awaits ELT/ANDES, ~2040s). Include as future forecast only.
   
   For Paper 2: fully compute Triangle 1; for Triangles 2-3, derive the ε-dependence analytically and show what future data would be needed to test them. This honestly separates "what we can do now" from "what requires Phase 4C."

6. Predict: future GW standard sirens (LISA, Einstein Telescope) test the gravity-sector measurement model independently.

**Key technical steps:**
- Step 1: Write measurement model translator (raw observable + ε-vector → inferred parameter)
- Step 2: Run standard inference (e.g., Pantheon+ likelihood) with ε as free parameter
- Step 3: Show posterior on ε given current data
- Step 4: Compute implied shifts in H₀, σ₈ as function of ε
- Step 5: Compare with observed tension pattern
- Step 6: Compute consistency triangle diagnostics

**Critical: Levels of ε intervention (must be explicit in paper):**
Pantheon+ is not raw data — it is a processed construction (light-curve fits, calibrations, K-corrections). If ε means "EM clocks/rulers scale differently," this could affect not just the μ(z) cosmological mapping but also SN Ia standardization (stretch/color parameters), K-corrections, time dilation interpretation, and even intrinsic luminosity evolution (if varying constants affect Ni56 yield/opacity). Paper 2 must distinguish:
1. **Inference-level ε** (only in μ(z) mapping; minimal, conservative) — Paper 2 implements this as minimum viable test
2. **Lightcurve-level ε** (enters SALT2/SALT3 standardization) — future work
3. **Astrophysics-level ε** (affects SN physics itself) — future work. **Key example:** Chandrasekhar mass M_Ch ∝ G⁻³/². If ε_gravity evolves, M_Ch at z = 1 was different, changing the Ni-56 yield and peak luminosity of SN Ia. This is the deepest astrophysical coupling and must be explicitly named (even if not modeled in Paper 2) to show referee awareness.
Without this distinction, a referee will ask: "at what level does ε enter your pipeline?"

**Critical: Redshift re-mapping.** If ε_EM ≠ 0, atomic energy levels (Rydberg constant ∝ α² m_e) evolve. But spectroscopic redshift z_obs is measured from atomic line wavelengths. Therefore, if constants vary, the relation between z_obs and the cosmological scale factor a(t) is modified: 1 + z_obs = (1/a(t)) × f(ε_EM(t)), where f encodes the shift in atomic energy levels. Paper 2's measurement model translator MUST include this redshift re-mapping, otherwise a referee will say: "you vary atomic clocks but use z defined by constant atoms — internally inconsistent." At inference level (Level 1), this effect may be negligible for small ε, but it must be explicitly bounded and stated.

**Critical: BAO and the sound horizon degeneracy:**
BAO observables are D_M(z)/r_d and H(z)·r_d, not H(z) in absolute units. If ε_QCD changes the QCD/EM scale ratio, the most natural effect is through r_d (the early-time sound horizon ruler), which is the well-known "sound horizon degeneracy" central to the H₀ tension. Paper 2 must explicitly state: (i) whether r_d is treated as a nuisance parameter calibrated by CMB/BBN, and (ii) that ε can act both on inferred late-time distances and on r_d itself. If this is not addressed, a referee will say: "this is just r_d freedom, not measurement-model novelty."

**Computational note:** Steps 2-3 require MCMC sampling with modified likelihoods. For Pantheon+ alone (1701 SNe, ~7 parameters + ε), this is feasible on a modern laptop (hours to days with emcee or cobaya). For combined Pantheon+ + DESI BAO, budget ~1-3 days per chain on a multi-core machine. Cloud compute (e.g., Google Colab Pro, ~$10/month) is sufficient if local resources are limited.

**Why valuable:** Opens a genuinely underexplored analysis direction. The question "how much of the tension is inference artifact from measurement model assumptions?" has not been systematically addressed in the literature with a unified ε-parametrization across sectors.

---

### Paper 3: "Null-Test Cartography for Universal Scaling Frameworks"

**Target:** Physical Review D  
**Timeline:** Parallel with Paper 2; 4-8 months  
**Requires collaborator:** Helpful but not essential — literature survey + computation  
**Can start solo (AI-assisted):** Most of the work (bounds compilation, mapping, visualization)

**Content:**

1. Full mapping in ε-space: for every point (ε_EM, ε_QCD, ε_gravity, ...), compute combined bound from:
   - Weak equivalence principle: η(Ti,Pt) = [−1.5 ± 2.3(stat) ± 1.5(syst)] × 10⁻¹⁵, i.e. no violation at the ~2.7×10⁻¹⁵ level (MICROSCOPE satellite, Touboul et al. 2022; supersedes earlier Eöt-Wash torsion balance bound of ~10⁻¹³)
   - Atomic clock comparisons: Δα/α ~ 10⁻¹⁷–10⁻¹⁸/yr (Rosenband et al. 2008 at ~10⁻¹⁷/yr; newer optical lattice clocks approaching 10⁻¹⁸/yr)
   - Oklo natural reactor: Δα/α < 10⁻⁸ over 2 Gyr
   - Lunar laser ranging: Ġ/G < 10⁻¹³/yr
   - BBN light element abundances
   - CMB spectral distortions (FIRAS bound)

2. Show combined viable region in ε-space.

3. For each viable point, compute cosmological effects (H₀ shift, σ₈ shift, drift sign/amplitude).

4. Identify which future experiments close which regions (ACES, VLT/ESPRESSO, ELT/ANDES, LISA).

5. Provide public code/tables.

**Why valuable:** Unifies varying-constants phenomenology with cosmological inference, currently fragmented across atomic, gravitational, nuclear, and cosmology communities.

**Critical: Combined bounds are model-conditional.** Combining WEP (η), atomic clocks (d ln α/dt), Oklo (Δα/α), LLR (Ġ/G), and BBN/CMB into a single ε-space map is NOT automatically valid. It requires an explicit coupling model that specifies: (a) which scalar field(s) carry the variation, (b) how they couple to different matter compositions (Damour-Donoghue type), (c) how they evolve locally vs cosmologically (screening vs no screening), and (d) how they map to observable dimensionless drifts. Paper 3 must define this coupling model as a framework assumption and present all combined bounds as conditional on it. Without this, a referee will say "you are mixing apples and oranges."

**Estimated effort:** Moderate. Individual bounds exist in literature. Innovation is systematic combination + cosmological mapping. Existing precision_constraints_translator provides starting infrastructure (after upgrade — see 4A.9).

---

### Paper 4: "Kill-Test-First Methodology for Alternative Cosmological Frameworks"

**Target:** Astronomy & Computing (research article) or Journal of Open Source Software (JOSS, for CosmoFalsify package) or RAS Techniques and Instruments. Note: Nature Astronomy perspectives are typically invited — unsolicited submission from a non-academic first author is unlikely to succeed.  
**Timeline:** Parallel with Papers 1-3; 3-6 months  
**Requires collaborator:** No — this is primarily the project lead's own contribution  
**Can do solo (AI-assisted):** Yes, entirely

**Content:**

1. The problem: alternative models lack systematic falsification infrastructure.
2. The methodology: claim ledger, kill tests, no-go documentation, reproducibility pipeline, overclaim linting.
3. Case study: GSC v10.1.1 — how claim ledger evolved, how E2 no-go was documented, how kill tests were defined prospectively.
4. Software release: standalone open-source package ("CosmoFalsify").

**Why valuable:** Methodological innovation applicable to any field testing alternative models.

**Estimated effort:** Low-to-moderate. Infrastructure exists; paper is description + contextualization + packaging. This paper is the most natural starting point for a non-physicist lead, since it is about the methodology you built, not about deriving physics.

---

## Part D: Technical Roadmap

### Phase 4A: Immediate (Q1-Q3 2026)

**Pre-check tasks (before all else — estimated 2-5 days total):**

| ID | Task | Solo/Collab | Depends on | Output |
|---|---|---|---|---|
| **4A.−1** | **Base Theory Drift Sign Diagnostic.** Calculate Sandage-Loeb drift for pure SigmaTensor-v1 (canonical quintessence, exponential potential, NO G(k) pole) across the viable range of λ. **Preliminary result (from independent review):** For w_φ₀ ∈ [−0.999, −0.7] and λ ∈ [0, 2] with Ω_m₀ ≈ 0.315, drift is strictly negative at z = 2, 3, 4, 5 in all tested configurations. **Analytical bound:** Standard matter gives H²(z) ≥ H₀²Ω_m₀(1+z)³. Positive drift requires H(z) < H₀(1+z), which implies Ω_m₀ < 1/(1+z). At z = 5 this gives Ω_m₀ < 0.166, far below the observed ~0.315. This is a *structural* result: standard matter alone forbids positive drift at z ≳ 2.2 for realistic Ω_m₀, regardless of dark energy model, given 4 assumptions: (1) flat FLRW, (2) GR Friedmann equation, (3) ρ_DE ≥ 0, (4) standard matter conservation (ρ_m ∝ (1+z)³). See A.3 for full assumption list and escape routes 10-13 for what happens when each is relaxed. **Action:** Formally verify with the existing solver (sigmatensor_v1.py + measurement_model.py:z_dot_sandage_loeb). Document the analytical bound. **Decision gate:** If confirmed → reframe E2 no-go as general field contribution (applies to *any* model claiming positive drift at z > 2), not GSC-specific crisis. The base GSC theory never predicted positive drift without the invalidated G(k) pole. Paper 1 narrative shifts from "our theory fails" to "we prove a useful general impossibility result." | Solo+AI | — | 1-page memo with drift(z) plot for λ-grid + analytical bound derivation. **Estimated effort: 1 day (verification of existing result).** |
| **4A.−0** | **Optimal Control CMB Repair Diagnostic.** (Only if 4A.−1 shows positive drift is possible — **likely moot** given preliminary negative result.) Formulate CMB closure as inverse problem: find minimal deformation A(z) to H(z) needed to close distance integrals while preserving drift positivity. **Three mandatory constraints:** (1) A(z) must be a smooth function (spline with ≤5 knots or Gaussian bump) — scalar fields cannot produce sharp features. (2) The implied effective equation of state w(z) must satisfy w ≥ −1 everywhere — phantom crossing is forbidden for canonical quintessence (SigmaTensor-v1). (3) **Stability:** For canonical quintessence, c_s² = 1 identically and the no-ghost condition is equivalent to ρ_DE + p_DE > 0 (i.e., 1+w > 0 for ρ_DE > 0), which is automatically satisfied by constraint (2). However, if the deformation is interpreted more broadly as a single-field EFT (k-essence or beyond), then c_s² ≥ 0 must be imposed separately — negative c_s² produces gradient instabilities. State which interpretation applies. If unconstrained optimization finds a solution but it violates (2) or (3), the solution is mathematically valid but physically forbidden for this model class. **Decision gate:** If minimal smooth, stable A ~ O(1%) → escape routes are realistic. If minimal smooth, stable A ~ O(20%) → structural impossibility. If no solution exists satisfying all three constraints → definitive no-go for quintessence-type models. **Alternative use if drift is negative:** Still valuable for Paper 1 (Proposition B) — run as "how much would H(z) need to change for drift to flip sign, and is that compatible with distances?" This quantifies the no-go gap. | Solo+AI | 4A.−1 | Assessment memo: required A amplitude + w(z) and c_s²(z) profiles + comparison with known bounds. **Estimated effort: 1-3 days.** |

**Main tasks:**

| ID | Task | Solo/Collab | Depends on | Output |
|---|---|---|---|---|
| **4A.0** | **Frame Invariance Document:** Write "Frame/Units Invariance & Non-Trivial Predictions" — which quantities are physically measurable invariants, which predictions survive frame changes, which don't | Solo+AI | — | 2-5 page document (prerequisite for all papers) |
| **4A.0b** | **Finalize and submit Paper 0 (existing late-time paper):** Review against 4A.0, check prior art citations (especially Wetterich 2014), submit to arXiv | Solo+AI | 4A.0 | arXiv preprint (calling card for collaborator search) |
| 4A.1 | Formalize no-go result: numerical bound + analytical argument sketch. **Note:** 4A.−1 and 4A.−0 results inform the framing: if SigmaTensor-v1 doesn't predict positive drift, Paper 1 is a general field contribution, not GSC-specific. | Solo+AI for numerics; Collab for analytical | E2 synthesis, 4A.−1/−0 results | Theorem or quantitative bound statement |
| 4A.2 | Write escape route catalog with theory links | Solo+AI | 4A.1 | Appendix table (see Part C, Paper 1) |
| 4A.3 | Draft Paper 1 | Collab needed | 4A.0, 4A.1, 4A.2 | arXiv preprint |
| 4A.4 | Package claim ledger + linter as standalone tool | Solo | Existing code | GitHub repository |
| 4A.5 | Draft Paper 4 (methodology) | Solo+AI | 4A.4 | arXiv preprint |
| 4A.6 | Formalize 4-level claim matrix (fit / kill-test / unification / QM bridge) | Solo | claim_ledger.json | Updated claim ledger |
| 4A.7 | DM Decision Memo | Solo | — | 1-2 page document |
| 4A.8 | Prior art matrix | Solo+AI | — | Reference table (Part G) |
| **4A.9** | **ε-framework readiness assessment:** Audit current precision_constraints_translator and ε-parametrization code. Determine: is it conceptual sketch or working code? What needs upgrading to support Papers 2-3? Estimate effort to reach production quality. | Solo | Existing code | Assessment memo + gap list + effort estimate |

**Recommended start order:**
1. **4A.−1 (Drift diagnostic) — FIRST. Takes 1 day (verification of existing result). Preliminary answer is already in: drift is negative for all tested parameters, with analytical bound confirming structural impossibility. Formal verification confirms the reframing.**
2. 4A.−0 (Optimal control) — likely moot for original purpose, but repurpose as "quantify the no-go gap" for Paper 1. Takes 1-3 days.
3. 4A.0 (Frame Invariance) — prerequisite for papers, clarifies thinking
4. 4A.0b (Paper 0 submission) — submit existing late-time paper as calling card
5. 4A.5 + 4A.4 (Paper 4 + CosmoFalsify) — can do solo, builds visibility for finding collaborators
6. 4A.6 + 4A.7 + 4A.8 (Claim matrix, DM memo, Prior art) — housekeeping, solo
7. 4A.9 (ε-framework audit) — determines feasibility of Papers 2-3
8. 4A.1 + 4A.2 + 4A.3 (Paper 1) — requires collaborator for analytical rigor

### Phase 4B: Near-term (Q3 2026 - Q2 2027)

| ID | Task | Solo/Collab | Depends on | Output |
|---|---|---|---|---|
| 4B.1 | Measurement model translator module | Solo+AI | 4A.9 (ε audit) | Python module with tests |
| 4B.2 | Sensitivity: ∂H₀/∂ε, ∂σ₈/∂ε (analytical formulae first, then numerical) | Solo+AI for formulae; Collab for validation | 4B.1 | Sensitivity matrix |
| 4B.3 | Pantheon+ with ε as free parameter | Collab recommended | 4B.1 | Posterior on ε |
| 4B.4 | DESI BAO DR1 with ε free | Collab recommended | 4B.1 | Posterior on ε |
| 4B.5 | Consistency triangles computation | Solo+AI | 4B.2 | Diagnostic results |
| 4B.6 | Tension pattern comparison | Collab recommended | 4B.3, 4B.4, 4B.5 | Paper 2 draft |
| 4B.7 | Combined ε-space mapping (null-test cartography) | Solo+AI | 4A.9 | Viable region map |
| 4B.8 | Future experiment forecasts | Solo+AI | 4B.7 | Paper 3 draft |

### Phase 4C: Strategic (2027+)

| ID | Task | Solo/Collab | Depends on | Output |
|---|---|---|---|---|
| 4C.1 | Theory decision memo: which escape route to pursue | Solo | Papers 1-3 results | Decision document |
| 4C.2 | If Weyl geometry: action with ξ ≠ 0 | Collab required | 4C.1 | Solver with α_M, α_B |
| 4C.3 | Linear perturbation theory | Collab required | 4C.2 | Stability analysis |
| 4C.4 | Growth rate fσ₈(z) | Collab required | 4C.3 | DESI/Euclid confrontation |
| 4C.5 | GW-EM distance ratio | Collab required | 4C.2 | LISA/ET forecast |
| 4C.6 | Screening analysis | Collab required | 4C.3 | Viable parameter space |
| 4C.7 | If escape route 3: CLASS/CAMB modification | Collab required | 4C.1 | Full Boltzmann pipeline |

**Escape Route → Theory mapping for 4C.1 decision:**

| Escape route (from Paper 1) | Motivated theory direction | Key reference | Difficulty |
|---|---|---|---|
| 1: Non-smooth H(z) | Multi-field model or cosmological phase transition | Assorted EDE literature | High |
| 2: Non-standard recombination | Weyl-geometric model with varying α, m_e via ε ≠ 0. **Cannot work standalone** — requires Route 1 (phase transition) or Route 6 (screening) to suppress variation at z = 0. | Ghilencea (2019-2024) | Medium-high (only viable combined with Route 1 or 6) |
| 3: Full Boltzmann beyond compressed priors | CLASS/CAMB modification for scale-covariant models | Zumalacárregui "hi_class" | High (code-intensive) |
| 4: Non-standard neutrino sector | Extended ν physics + scale covariance | Assorted ν-cosmology | Medium |
| 5: Multi-field | Entirely new model class | Open | Very high |
| 6: Density-dependent screening | Weyl geometry / scalar-tensor with Chameleon/Symmetron screening. **Severely constrained** by quasar DLA spectroscopy (Δα/α < 10⁻⁵ in voids). | Jain & Khoury (2010), Burrage & Sakstein (2018), Murphy et al. (2003) | Very high (may be impossible without extreme fine-tuning) |
| 7: Distance duality violation | Photon-axion conversion or non-metricity models | Bassett & Kunz (2004), Avgoustidis et al. (2010) | Medium-high |
| 8: Non-FLRW (backreaction) | Buchert averaging, Wiltshire timescape | Buchert (2008), Wiltshire (2007) | Very high (different framework entirely) |
| 9: Modified drift formula | Only viable combined with route 6 (standalone: 8 orders of magnitude short) | — | Dead as standalone; adjunct to route 6 only |
| 10: Spatial curvature Ω_k ≠ 0 | Not a viable direction | Planck curvature constraints | Dead (effect too small at realistic Ω_k) |
| 11: Modified Friedmann / non-GR background | f(R), braneworld, scalar-tensor with G_eff(z) | Assorted modified gravity literature | High (the Ω_m₀ analytical bound assumes GR; this is the broadest escape) |
| 12: Interacting Dark Energy (IDE) | DM-DE energy exchange models (Gavela et al. 2009, Salvatelli et al. 2014) | CMB perturbation + LSS growth literature | Medium-high (active research area, viable parameter space exists; breaks ρ_m ∝ a⁻³) |
| 13: Phantom / WEC violation (ρ_DE < 0) | k-essence, ghost condensate, non-canonical kinetic terms | EFT consistency, ghost-freedom literature | Medium (theoretically risky but not observationally excluded; forbidden for canonical quintessence) |

The decision at 4C.1 should be informed by: (a) which escape routes are least constrained by Paper 3 results, (b) which have the lowest barrier to entry for the team's skills and available collaborators, and (c) which connect most naturally to the measurement model framework (Papers 2-3).

---

## Part E: What To Stop Doing

**E.1 Stop treating drift sign as primary falsifier — it was never a prediction of the base theory.** The E2 no-go result proves that positive drift at z > 2 is structurally impossible for standard matter content (Ω_m₀ > 1/(1+z)). Since SigmaTensor-v1 without the G(k) pole does not predict positive drift, E2 is a contribution to the field, not a self-falsification. Replace drift sign with the multi-observable consistency network (consistency triangles in Paper 2) as the primary discriminator.

**E.2 Stop using pole-like G(k).** Replace with bounded crossover families or let running emerge from dynamics.

**E.3 Stop labelling Weyl geometry as "speculative ToE-track."** It is more grounded than the current ansatz. If escape route 2 is pursued, these notes become the theoretical foundation.

**E.4 Stop expanding infrastructure without new physics.** Infrastructure is production-grade. Bottleneck is physics.

**E.5 Stop deferring perturbation theory without a committed timeline.** It is a prerequisite for DM, S₈, lensing, growth, and any serious confrontation beyond background. The roadmap places it in Phase 4C (2027+), which is acceptable — but only if this timeline is treated as a firm commitment, not an indefinitely receding horizon. If no collaborator for perturbation theory is found by end of Phase 4B, reassess whether the physics program can continue.

---

## Part F: Dark Matter — Decision Required

Four options:

**Option A:** No particle DM — modified gravity/inertia. Extremely demanding (rotation curves + lensing + Bullet Cluster + LSS). Only pursue with specific mechanism + collaborator with galaxy dynamics expertise.

**Option B:** Effective DM from scaling gradients. Speculative, requires perturbation theory not yet developed. Natural follow-on from Phase 4C if pursued.

**Option C:** DM remains particles; contribution is DE/measurement model only. Simplest, honest. Recommended baseline.

**Option D:** DM signals partially measurement model artifacts. If ε_EM ≠ ε_QCD ≠ ε_gravity, then EM-based mass estimates (from luminosity), QCD-based estimates (from BAO-inferred distances), and gravity-based estimates (from lensing, dynamical measurements) can disagree systematically. Novel, testable, natural extension of Paper 2.

**Recommendation:** Option C as baseline. Investigate Option D in Paper 2. Only pursue A/B with specific mechanism from Phase 4C.

**Action:** Write DM Decision Memo (1-2 pages) stating chosen option, explicit non-claims, must-pass tests, and failure criteria.

---

## Part G: Prior Art Map

### Conformal cosmology / varying scales
- **Wetterich (2014)** "Hot big bang or slow freeze?" [arXiv:1401.5313] — Closest prior art. GSC must explicitly state what it adds.
- **Dicke (1962)** "Mach's Principle and Invariance under Transformation of Units" — Frame equivalence origin.
- **Fujii & Maeda (2003)** "The Scalar-Tensor Theory of Gravitation" — Standard reference.

### Measurement model / metrology
- **Uzan (2003, 2011)** "Fundamental constants and their variation" — Varying constants review.
- **Martins (2017)** "The status of varying constants: a review of the physics, searches, and implications" — More recent comprehensive review. Paper 3 must differentiate from this.
- **Will (1993, 2014)** "Theory and Experiment in Gravitational Physics" — PPN framework.
- **Touboul et al. (2022)** MICROSCOPE final result — η(Ti,Pt) no violation at ~2.7×10⁻¹⁵ level (1σ quadrature of stat+syst).

### Modified GW propagation
- **Belgacem et al. (2018)** "GW luminosity distance in modified gravity" — Ξ₀ parametrization.
- **Baker et al. (2017)** "Strong constraints from GW170817" — GW speed.

### EFT of dark energy
- **Bellini & Sawicki (2014)** "Maximal freedom at minimum cost" — α-functions.
- **Zumalacárregui et al. (2017)** "hi_class" — Modified Boltzmann solver.

### Redshift drift
- **Sandage (1962)** / **Loeb (1998)** — Original proposals.
- **Liske et al. (2008)** — ELT forecast.
- **Cristiani et al. (2025)** "The ESPRESSO Redshift Drift Experiment" (A&A) — VLT precursor program, published null result with timeline-to-detection estimates. Critical reference for Paper 1 "service paper" framing.
- **Marconi et al. (2024)** "ANDES, the high resolution spectrograph for the ELT" — Primary future optical drift instrument.
- **Kloeckner et al. (2015)** — SKA 21cm redshift drift as alternative radio channel.

### Tensions (context)
- **Di Valentino et al. (2021)** "In the Realm of the Hubble tension."
- **Schöneberg et al. (2022)** "The H₀ Olympics."

### Weyl geometry (Phase 4C)
- **Ghilencea (2019-2024)** — Weyl geometry and cosmology.
- **Almeida et al. (2014)** — Brans-Dicke to Weyl-integrable mapping.

### Asymptotic safety
- **Reuter & Saueressig (2012)** — Standard reference.
- **Platania (2020)** — RG-improved cosmology review.

### Screening mechanisms (Phase 4C, escape route 6)
- **Jain & Khoury (2010)** "Cosmological tests of gravity" — Screening overview.
- **Burrage & Sakstein (2018)** "Tests of chameleon gravity" — Comprehensive review of screening constraints.
- **Brax et al. (2012)** "Systematic simulations of modified gravity" — Void effects.

### Varying constants — spectroscopic constraints (escape route 6 falsifier)
- **Webb et al. (2001, 2011)** "Further evidence for cosmological evolution of the fine structure constant" — Quasar absorption spectra.
- **Murphy et al. (2003)** "Limit on Δα/α from DLA systems" — Δα/α < 10⁻⁵ at z ~ 1-3. This is the primary observational constraint that makes large ε in voids untenable.

### Varying constants — recent updates (2025-2026, critical for Paper 3 novelty positioning)
- **Martins (2025)** "Varying fundamental constants cosmography" — Directly adjacent to Paper 3's systematic approach. Paper 3 must differentiate.
- **ALMA/radio sub-ppm constraints (2025)** — New sub-ppm upper limits on Δα/α from radio absorption. Must be included as anchor constraints in Paper 3.
- **"Future Dark Energy Constraints from Atomic Clocks" (2025)** — Clock drifts at 10⁻¹⁷–10⁻¹⁸ yr⁻¹ level; directly relevant to Paper 3 forecasts.
- **Davis & Hamdan** — Oklo bound: ~1.1×10⁻⁸ (95% CL). Cite for specific Oklo number.
- **LLR Ġ/G:** Typically cited as (2±7)×10⁻¹³ yr⁻¹. Use specific value in Paper 3.

### Interacting Dark Energy / Dark Sectors (escape route 12)
- **Gavela et al. (2009)** "Dark coupling" — Early constraints on DM-DE energy exchange.
- **Salvatelli et al. (2014)** — IDE models with observationally allowed coupling strengths.
- **Di Valentino et al. (2020)** "Interacting dark energy in the early 2020s" — Review of IDE as route to H₀ tension resolution. Relevant context for Paper 1 escape route.

### Dynamical attractor / least-coupling mechanisms (escape route 2 suppression)
- **Damour & Polyakov (1994)** "The string dilaton and a least coupling principle" — Dynamical mechanism for scalar couplings to matter to be attracted toward zero at late times, without phase transition or environmental screening. Relevant as third suppression mechanism for Route 2.

### Phantom / WEC violation (escape route 13)
- **Caldwell (1999)** "A phantom menace? Cosmological consequences of a dark energy component with super-negative equation of state" — Foundational phantom DE paper.
- **Cline et al. (2004)** — Ghost/instability analysis of phantom models.

**Action:** Build prior art matrix: for each reference, document overlap / difference / constraints on GSC claims.

---

## Part H: Risk Register Update

| Risk | Severity | Mitigation |
|---|---|---|
| "Just a frame transformation" | High | 4A.0 Frame Invariance Document + Paper 2 (measurement model ≠ frame) |
| E2 no-go read as failure | High | Paper 1 (formalize as theorem/bound — contribution, not failure) |
| DM overclaim | Medium | DM Decision Memo (Option C baseline) |
| Competition with large collaborations | Medium | Focus on measurement model (no competition) |
| Infrastructure without physics | Medium | Redirect effort to physics (Part E.4) |
| Pole G(k) misinterpreted | Medium | Replace with bounded families |
| Perturbations deferred indefinitely | High | MVP as Phase 4C.3 |
| Paper rejected as known physics | Medium | Prior art map (Part G) + 4A.0 |
| Single-person sustainability | Medium | CosmoFalsify release + methodology paper to build visibility |
| **ε-framework not production-ready** | **Medium** | **4A.9 audit before committing to Papers 2-3 timeline** |
| **No-go is bound, not theorem** | **Low** | **Paper 1 framed honestly as either theorem or quantitative bound** |
| **Collaborator not found** | **Medium** | **Paper 4 first (solo) builds visibility; direct outreach to specific groups; arXiv preprint as calling card** |
| **Paper 3 perceived as duplicating Uzan/Martins reviews** | **Medium** | **Explicit differentiation: Uzan (2011) and Martins (2017) compile bounds on individual constants; Paper 3 maps the full ε-space simultaneously and connects to cosmological parameter inference (H₀, σ₈). The "cartography + cosmological mapping" combination is the novelty, not the individual bounds. State this clearly in the introduction.** |
| **arXiv endorsement not obtained** | **Medium** | **Seek endorser early; collaborator (if found) can endorse; alternatively post on Zenodo/GitHub with DOI as fallback** |
| **E2 no-go irrelevant to GSC: base theory doesn't predict positive drift** | **High (confirmed preliminarily)** | **4A.−1 preliminary result: drift is negative for all tested SigmaTensor-v1 parameters. Analytical bound: Ω_m₀ < 1/(1+z) required for positive drift, structurally violated at z > 2 for observed Ω_m₀ ≈ 0.315. Reframe Paper 1 as general field contribution. Project narrative shifts to measurement model formalism (Papers 2-3) as core novelty.** |
| **Optimal control gives unphysical solutions** | **Low** | **Smoothness constraint on A(z): spline with ≤5 knots or Gaussian bump. If unconstrained solution requires sharp features, scalar field cannot produce them.** |

---

## Part I: Success Criteria

**Paper 0:** Frame-invariant claims verified against 4A.0 + prior art properly cited (especially Wetterich 2014) + arXiv endorsement obtained + posted to arXiv + no referee-fatal overclaims.

**Paper 1:** Rigorous no-go (theorem or quantitative bound, honestly labelled) + numerical illustration + escape catalog with theory links + journal acceptance.

**Paper 2:** Public code + sensitivity matrix for Pantheon+/DESI + consistency triangles + at least one tension quantified against ε + journal acceptance.

**Paper 3:** ≥5 precision tests combined in ε-space + viable region map + ≥3 future experiment forecasts + public tables/code.

**Paper 4:** CosmoFalsify on GitHub with documentation, tests, and example usage + journal acceptance. Stretch goal: at least one external adoption.

**Phase 4C:** Specific action + stability proof + ≥1 prediction distinguishable from ΛCDM at 2σ + solar system safe.

---

## Part J: Contingency — What If All Results Are Null

This must be addressed honestly. There are three "null" scenarios:

### Scenario 1: No-go is proven and no viable escape route is found

Paper 1 proves the no-go. Subsequent investigation of escape routes yields no viable path:
- Escape route 2 (varying α, m_e) closed by Paper 3 ε-bounds
- Escape routes 1, 3, 4, 5 closed by other means (e.g., route 1 excluded by future high-z data, route 3 found to have no hidden degeneracies after CLASS/CAMB analysis, etc.)

**Important:** Paper 3 alone only constrains escape route 2 (sector-dependent scaling). Escape routes 1 (non-smooth H(z)), 3 (full Boltzmann), 4 (non-standard ν), and 5 (multi-field) are structurally independent of ε-bounds and require separate investigation. "All escape routes closed" is therefore a multi-year, multi-paper outcome — not something Paper 3 alone delivers.

**What GSC is then:** A completed negative result — a proof that scale-covariant cosmologies of this class are excluded. Still publishable (Papers 1 + 3), still valuable (saves others from pursuing dead ends), but the physics program ends here.

**What survives:** Paper 4 (methodology) + CosmoFalsify are independent of physics results.

### Scenario 2: ε-effects are too small to explain tensions

Paper 2 shows that viable ε-values (allowed by Paper 3 bounds) produce H₀ shifts and σ₈ shifts orders of magnitude smaller than the observed tensions.

**What GSC is then:** A measurement model framework that confirms the standard assumption (ε ≈ 0 is correct). Paper 2 is still publishable as "we checked systematically and the effect is negligible — standard measurement model is safe." This is a useful null result.

**What survives:** Papers 1, 3, 4 are independent. The methodology stands.

### Scenario 3: Everything is null

No-go proven, escape routes closed, ε-effects negligible, methodology paper published.

**What GSC is then:** Three contributions:
1. A no-go theorem/bound for the field
2. A confirmation that standard measurement model is robust
3. A falsification methodology package

**This is a perfectly respectable outcome.** Many important scientific projects end with "we rigorously excluded X." The value is in the rigor, not in finding X.

**What the project lead should feel:** Not failure. The infrastructure was not wasted — it produced definitive results. The fact that the results are negative does not diminish the achievement of producing them with this level of rigor.

---

## Part K: Collaborator Strategy

### Why collaborators are needed

Baev is not a physicist or mathematician. The infrastructure is exceptional, but Papers 1-2 require domain expertise that AI assistance alone cannot reliably provide: analytical proofs, likelihood code validation, peer review navigation, and physical intuition for what "looks wrong" in a calculation.

### What Baev brings to a collaboration

This is important — it is not a one-sided ask:

1. **Production-grade infrastructure** that no academic group has. Offer it as a shared tool.
2. **CosmoFalsify / methodology** — co-authorship on methodology paper in exchange for physics collaboration.
3. **Systematic numerical scanning** capability (E2, Phase-3 pipeline) — computational resource that postdocs/students often lack.
4. **The no-go result itself** — a publishable finding that a collaborator could co-author.

### Who to look for

| Paper | Collaborator profile | Where to find | What to offer |
|---|---|---|---|
| Paper 1 | Mathematical cosmologist (postdoc level, familiar with dark energy phenomenology, H(z) constraints) | Recent JCAP/PRD author lists on w₀wₐ or modified gravity analyses; cosmology conference participant lists; DESI/Euclid published paper author lists (public) | Co-authorship + your numerical infrastructure + the no-go result |
| Paper 2 | Observational cosmologist with likelihood code experience (Pantheon+, DESI) | SN cosmology groups (Brout, Scolnic); BAO analysis groups | Co-authorship + ε-framework + measurement model formalism |
| Paper 3 | Atomic/nuclear physicist familiar with varying constants bounds | Uzan's group (Paris); Webb's group (UNSW); clock comparison experimentalists | Co-authorship + unified framework connecting their bounds to cosmology |
| Paper 4 | Solo (no collaborator needed) | — | — |

### How to make contact

1. **Post Paper 0 on arXiv first** (per start order 4A.0b). This is the physics calling card — it shows the framework, measurement model, and late-time confrontation. **Then post Paper 4 + CosmoFalsify** (per start order step 5). Paper 4 is the methodology paper and is lower-risk, but Paper 0 carries more physics weight for attracting collaborators. Together they give potential collaborators both "here is the physics" and "here is the infrastructure."
   - **arXiv endorsement:** Since January 2026, arXiv has tightened endorsement requirements — institutional email alone may no longer suffice for new authors (see arXiv blog, 21 Jan 2026). **Safest path:** have a physicist collaborator or co-author serve as submitting author for the first preprint. **Fallback:** post on Zenodo/GitHub with DOI while seeking endorsement through direct outreach to researchers whose work you cite. Without endorsement, the arXiv visibility strategy stalls.
2. **Write a 1-page "collaboration proposal"** for each target paper: what the project has, what it needs, what it offers.
3. **Email specific researchers** (not generic mailing lists) with the proposal + link to CosmoFalsify repo + link to arXiv preprint.
4. **Attend one virtual seminar/workshop** in the relevant community (Euclid Theory WG and some DESI talks have open attendance) to build familiarity.

### Realistic timeline adjustment

| Paper | With experienced collaborator | Solo + AI only |
|---|---|---|
| Paper 1 | 4-8 months | 8-18 months (risk: analytical proof may not be rigorous enough for referee) |
| Paper 2 | 6-12 months | 12-24 months (risk: likelihood code errors without expert validation) |
| Paper 3 | 4-8 months | 6-12 months (most feasible solo — primarily literature + computation) |
| Paper 4 | 3-6 months | 3-6 months (fully solo-feasible) |

---

## Part L: Computational Resources Assessment

### What is needed

| Task | Compute requirement | Feasible on laptop? | Alternative |
|---|---|---|---|
| Paper 1 numerical scans | Existing E2 infrastructure runs | Yes (already done) | — |
| Paper 2 MCMC with ε (Pantheon+ only) | ~7 params, 1701 SNe, emcee | Yes (hours-days) | — |
| Paper 2 MCMC with ε (Pantheon+ + DESI combined) | ~10 params, combined likelihood | Marginal (days-week) | Google Colab Pro ($10/mo) |
| Paper 3 ε-space mapping | Grid scan, no MCMC needed | Yes | — |
| Phase 4C CLASS/CAMB modifications | Boltzmann solver runs | Yes for individual runs; HPC for full grid | University HPC via collaborator |

### Software dependencies

| Tool | Purpose | Available? |
|---|---|---|
| emcee or cobaya | MCMC sampling | pip install |
| Pantheon+ likelihood | SN data | Public (github.com/PantheonPlusSH0ES) |
| DESI BAO likelihood | BAO data | Use DR1 as baseline (matches E2 synthesis context). DR1 public likelihoods available via GitHub org cosmodesi (e.g. desilike) and CobayaSampler/bao_data (files desi_2024_*). Add DR2 as robustness check once pipeline works (DR2 available in standard likelihood tooling as of late 2025). Implementation: Cobaya BAO likelihoods include DESI BAO bundles; desilike is the maintained DESI likelihood framework. |
| CLASS or CAMB | Boltzmann solver (Phase 4C only) | Public; Docker already in repo |

**Bottom line:** Papers 1, 3, 4 are computationally trivial. Paper 2 is feasible on a modern laptop or cheap cloud. Phase 4C may need HPC access (available through collaborator).

### AI disclosure policy

Since the project relies heavily on AI assistance, journal policies must be checked before submission:

- **Nature/Nature Astronomy:** AI tools must be disclosed in Methods; AI cannot be listed as author.
- **Physical Review (APS):** Authors must take responsibility for AI-generated content; disclosure expected.
- **MNRAS:** Similar to APS; AI use should be acknowledged.

**Recommendation:** Include a standard acknowledgment: "This work made use of AI-assisted tools for code development, literature review, and manuscript drafting. All scientific claims, calculations, and conclusions were verified by the authors." Ensure at least one human author (ideally a physicist collaborator) can take scientific responsibility for every claim.

---

## Part M: Summary — The Three Sentences

If someone asks "What is GSC?", the answer after executing this roadmap:

**1. What we proved:** A formal no-go result showing that no cosmological model with standard matter content (Ω_m₀ ≈ 0.3), flat spatial geometry, non-negative dark energy density, standard matter conservation, and smooth H(z) can produce positive redshift drift at z ≳ 2.2 while matching precision distance data — with an analytical bound (Ω_m₀ < 1/(1+z)), an explicit catalog of 13 assumptions/escape routes, and their theoretical implications. This is a general result for the field, not specific to GSC.

**2. What we built:** The first systematic framework for analyzing how measurement model assumptions (what clocks and rulers actually measure) affect cosmological parameter inference, with quantified sensitivity to sector-dependent scaling departures and cross-checks via consistency triangles.

**3. What we released:** An open-source falsification methodology and software package for testing alternative cosmological models with reproducible, overclaim-resistant infrastructure.

These three things are novel, defensible, and publishable — regardless of whether the physics results are positive, negative, or null. Paper 0 (the existing late-time framework paper) establishes the framework context and serves as the entry publication; Papers 1-4 extend the research program in independent directions.

---

*End of document.*
