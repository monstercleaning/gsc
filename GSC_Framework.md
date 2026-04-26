# GSC Framework

## A Layered Scale-Covariant Cosmology with Pre-Registered Falsification

**Status:** Working research draft, April 2026.
**Audience:** Theoretical cosmology, gravitational physics, quantum gravity, scientific software methodology.
**Repository:** `github.com/morfikus/GSC`

> Predecessor framework drafts (provenance only) are retained at [archive/](archive/).

---

## Lineage statement (read first)

The core thesis of GSC — that observed cosmological redshift can be reframed as the coherent shrinkage of bound matter against an approximately static background — is not original to this work. The same observational equivalence was developed by **C. Wetterich**, *A Universe without expansion* (arXiv:1303.6878, 2013), and by his subsequent program identifying the cosmon-driven dark-energy evolution with asymptotic-safety renormalization-group flow. The "scale-covariant theory of gravitation" tradition extends back to **Canuto et al.** (Phys. Rev. D 16, 1643, 1977).

GSC positions itself within this lineage as a **specific crossover realization**: a phenomenologically constrained ansatz for the scale field σ(t) and the running gravitational coupling G(σ), supplemented by an explicit **layered claim hierarchy** and a **pre-registered falsification program** built on a deterministic reproducibility stack. The claims original to GSC are extensions and synthesis, not the underlying frame equivalence.

This honesty is not a weakness. It is the precondition for the layered-tier discipline that follows.

---

## Abstract

We present **GSC**, a scale-covariant cosmological framework structured as four explicitly-tiered layers of epistemic confidence:

- **Tier T1** — a measurement-theoretic framework (the *freeze frame*) in which cosmological observables are dimensionless ratios of evolving emitter, propagator, and detector scales;
- **Tier T2** — a phenomenological scale field σ(t) fitting late-time distance and growth observations;
- **Tier T3** — an effective renormalization-group ansatz for the gravitational coupling G(σ) with critical scale σ_* and proposed derivations from non-commutative ultraviolet/infrared mixing and asymptotic safety;
- **Tier T4** — independent physical extension modules (vortex dark matter from Kibble–Zurek defect formation; informational-thermodynamic interpretation; cosmological quantum reference frames; σ as solution to the strong CP problem).

Each tier carries an independent kill-test, so the failure of any T4 module does not propagate to the lower tiers. The framework is supported by a deterministic reproducibility stack (schema-validated artifacts, lineage DAGs, container-based reproducers) and a pre-registration register pinning numerical predictions before observational releases (DESI Year-3 BAO, LiteBIRD, HERA/SKA 21cm, neutron-lifetime experiments).

The eight central pre-registered predictions are:

1. **BAO standard-ruler shift** Δr_s/r_s in DESI Year-3, calculable from σ-evolution of c_s and t_rec.
2. **21cm Cosmic-Dawn signal** at z ≈ 15–25, distinct from ΛCDM expectation; testable with HERA Phase-II and SKA-Low.
3. **Neutron-lifetime environmental dependence** τ_n(beam) − τ_n(trap) ~ 9 s explained by σ-dependent β-decay rate in different matter densities.
4. **CMB cosmic birefringence** β consistent with Planck hint (~0.35°), enhanced precision by LiteBIRD.
5. **Strong-CP θ-bound** evolved by RG-driven σ-θ coupling; consistent with current nEDM limits, calculable cosmological evolution.
6. **Topological-defect spectrum** from σ_*-crossing as Kibble–Zurek phase transition (string density, gravitational-wave signature).
7. **GW-memory-induced atomic-clock-array shifts** correlated with LIGO/Virgo merger events.
8. **Redshift-drift sign and amplitude** at z ≈ 2–5 (now framed as supporting, not primary discriminator).

A four-paper publication strategy isolates the empirical contribution (Paper A), the theoretical ansatz (Paper B), the speculative extension modules (Paper C), and the software/pre-registration methodology (Paper D), so that adverse review of any layer does not compromise the others.

---

## 0. The Tier Hierarchy: Architectural Principle

Past versions of GSC oscillated between two failure modes:

- **v9.1 maximalism**: a unified bold thesis spanning twelve sections — vortex dark matter, information-thermodynamic gravity, holographic proton, neutrino-torsion oscillations, eleven testable predictions — but with quantitative errors (dimensional inconsistencies, numerical mismatches by tens of orders of magnitude) that left individual modules vulnerable, and a reviewer's veto of one module risked the whole.
- **v11 defensiveness**: a careful late-time fit wrapped in extensive *non-claim* documentation. Mathematically clean and reproducible, but with the original explanatory ambition removed; the central falsifier (redshift-drift sign) demoted; and the framework reduced to an effectively two-parameter dark-energy model with philosophical framing.

**The framework rejects this binary.** A scientific framework is not obligated to defend or abandon every module simultaneously. We instead introduce four tiers of epistemic status, each with explicit:

- *Claim content* — what is asserted;
- *Status* — derivation, ansatz, or phenomenological fit;
- *Kill-test* — observational or mathematical condition that would falsify the tier;
- *Independence* — which higher tiers (if any) survive the failure of this tier.

| Tier | Type | Example claim | Kill-test | If false, what survives |
|---|---|---|---|---|
| **T1** | Kinematic frame | Conformal equivalence of FRW expansion and freeze-frame shrinkage | Mathematical inconsistency in coordinate transformation (essentially impossible) | — |
| **T2** | Phenomenological fit | σ(t) reproduces SN, BAO, and structure data at acceptable χ² | χ²/dof > threshold across all reasonable σ(t) ansätze | T1 only |
| **T3** | Physical ansatz | G(σ) follows specific RG-running near σ_* | First-principles FRG derivation incompatible, or all parameter regions excluded | T1 + T2 |
| **T4** | Speculative extension | Vortex DM, holographic proton, σ-θ coupling, σ as QRF | Per-module observational kill-test | T1 + T2 + T3 |

This is not new defensive language. It is the explicit structure of the document. **Each subsequent section is labelled with its tier**, and reviewers and readers can immediately judge what they are committing to when they accept or reject a particular argument.

The publication strategy in §13 mirrors this: separate papers for separate tiers, so journal review acts at the appropriate granularity.

---

## 1. (T1) Measurement-Theoretic Framework: The Freeze Frame

### 1.1 The frame equivalence

Scalar–tensor cosmologies admit physically equivalent descriptions related by conformal rescaling. Two natural choices:

- **Einstein-like frame:** particle masses constant, metric expands as FRW with scale factor a(t).
- **Freeze frame:** background geometry approximately Minkowski; particle masses, atomic radii, and clock frequencies vary coherently with a single scale field σ(t).

Only **dimensionless ratios** of comparable quantities are observable. Hence the relevant claim is not that one frame is "true" and the other "false" — both reproduce identical predictions for any well-defined dimensionless observable. The choice of frame is a choice of *parametrization*, and the frame in which the dynamics are most transparent depends on the question being asked.

### 1.2 Addressing the conformal-frame triviality critique

The standard objection to scale-covariant cosmology is: *if FRW and freeze-frame are conformally equivalent, then the freeze-frame description is empty — it is ΛCDM with a change of variable.* This objection is partially correct and partially mistaken, and we address it directly here, in Section 1, rather than in a buried appendix.

**Where the objection is correct:** at the level of background kinematics for a *passive* scale parameter — one whose evolution is determined entirely by Einstein equations sourced by ordinary matter and dark energy — the two frames are observationally identical for any dimensionless observable. Choosing freeze-frame in this case adds only philosophical content.

**Where the objection fails:** if σ has *independent dynamics* not derivable from the Einstein-frame matter content, then the frames are no longer conformally equivalent in the relevant sense. In particular:

1. The map between Einstein and freeze frames depends on σ(t). A σ governed by an independent equation of motion (Section 3) defines a frame map that is not a free conformal gauge choice.
2. Observables sensitive to time-derivatives of dimensionless ratios (redshift drift) or to spatial gradients of σ (Section 6) probe the σ-dynamics directly and break the symmetry.
3. Observables sensitive to coupling between σ and gauge fields (Sections 7–8) are frame-independent statements about additional terms in the effective action.

The frame-equivalence critique therefore reduces to: *does σ have non-trivial independent dynamics?* This is the empirical content of GSC and the question to which the rest of the framework is addressed.

### 1.3 Operational measurement model

The measurement model — implemented in [gsc/measurement_model.py](gsc/measurement_model.py) and documented at [docs/measurement_model.md](docs/measurement_model.md) — encodes the freeze-frame as follows. Photons propagate in an approximately Minkowski background with constant photon energies along the worldline. Atomic transition energies in the emitter and detector evolve with σ. The observed redshift is

$$1 + z_{obs} = \frac{\Delta E_{atom}(t_{em})}{\Delta E_{atom}(t_{det})} = \frac{\sigma(t_{em})}{\sigma(t_{det})} \cdot R_{geom}$$

where R_geom captures geometric path effects in the static background. For background-level cosmology, R_geom = 1 and the entire redshift is metrology drift. The observable distance modulus, BAO standard ruler, and large-scale-structure growth rate are all expressible in this form.

The **geometric lock** ensures local experiments (GPS, atomic-clock comparisons, lunar laser ranging) do not exhibit secular drift, provided σ couples *universally* to all dimensional sectors. This is a hard consistency condition, not a free parameter (Section 5.2).

### 1.4 What T1 commits to

T1 alone commits only to:

- The validity of the freeze-frame as a parametrization;
- The observable being a dimensionless ratio of evolving scales;
- The geometric-lock consistency condition.

T1 does **not** commit to any specific σ(t) law, any particular running of G, or any extension module. T1 falls only if the conformal-frame mathematics is inconsistent — essentially impossible.

---

## 2. (T2) σ(t) and Late-Time Observations

### 2.1 Phenomenological ansatz

T2 commits to a specific functional form for σ(t) sufficient to fit late-time observables (z ≲ 5). The canonical v11 implementations include:

- **Power-law collapse:** σ(t) ∝ t^p with p < 0;
- **Transition collapse:** σ(t) interpolating smoothly between two power-law regimes around a transition redshift z_t;
- **RG-flow profile:** σ(t) numerically integrated from the G(σ) ansatz of Section 3.

All three are implemented in [gsc/histories/](gsc/histories/) and fit against the canonical late-time dataset:

- Pantheon+SH0ES Type Ia supernovae with full STAT+SYS covariance;
- DESI Year-1/Year-2 BAO measurements;
- Compressed CMB distance priors (CHW2018);
- Linear-growth fσ8 measurements.

### 2.2 Reproducible fit results

The canonical late-time fit results (carried forward from the immediate predecessor release; to be re-run and re-frozen as the current-cycle reference manifest in M201) are summarized below:

- ΛCDM baseline reproduces standard literature χ²;
- GSC power-law and transition variants achieve χ² within ΔAIC < 4 of ΛCDM on combined SN + BAO;
- The fit constrains σ(t) at z ~ 0.1–2 to within ±5% of canonical normalization.

### 2.3 Kill-test for T2

T2 falls if no σ(t) ansatz consistent with the geometric-lock condition (T1) achieves Δχ² < 50 vs. ΛCDM on combined late-time data. As of v11, T2 is comfortably alive.

T2 does **not** commit to any first-principles origin of σ(t); it is purely a phenomenological fit. Promotion to T3 requires a physical mechanism for σ-dynamics.

---

## 3. (T3) The Renormalization-Group Ansatz for G(σ)

### 3.1 Minimal RG-running hypothesis

The proposed physical mechanism for σ(t) is renormalization-group flow of the gravitational coupling. We adopt the minimal hypothesis:

1. There exists an effective gravitational coupling G(σ) that runs with a physical scale σ (dimensionally a length, equivalently a momentum scale k ~ 1/σ).
2. The running contains a rapid-growth regime near a critical scale σ_* of the order of a hadronic length.
3. As σ(t) decreases, G(σ) increases, driving accelerated collapse via a back-reaction on the σ-equation of motion.

An illustrative parametrization (Landau-pole form):

$$G(\sigma) = \frac{G_N}{1 - (\sigma_* / \sigma)^2}$$

This ansatz is **not** derived from first principles. It is a phenomenologically motivated guess inspired by Asymptotic Safety scenarios (Reuter, Wetterich, Percacci) and by the typical behaviour of effective couplings near non-Gaussian fixed points in functional renormalization group analyses.

### 3.2 Status of σ_*

A frequent and valid criticism of earlier GSC drafts was the treatment of σ_* ~ r_proton as a "prediction". The current framework adopts a disciplined posture:

- σ_* is an **effective critical scale parameter**, not a derived quantity at the level of T3;
- Numerical identification with hadronic scales is a *suggestive* phenomenological coincidence, not evidence for a specific microphysical mechanism;
- A first-principles derivation of σ_* is outstanding work; two candidate routes (non-commutative IR/UV mixing, holographic AdS/QCD warp factor) are explored in T3.5 and T4.1 below.

Honest acknowledgement: the RG running remains phenomenological at this stage. This does not invalidate the framework as a falsifiable hypothesis; it constrains the level of explanatory depth that can currently be claimed.

### 3.3 Coupling of σ to standard-model sectors

The geometric-lock requirement of Section 1.3 demands that σ couples *universally* to dimensional sectors at leading order. Concretely:

- Particle masses: m ∝ σ^{-1};
- Newton coupling: G ∝ σ^{2};
- Lengths: r ∝ σ.

This *strict* universal coherent scaling implies that **all dimensionless particle-physics ratios are σ-invariant** — the conformal-frame transformation that moves between FRW and freeze-frame is a symmetry of the dimensionless physics. As a consequence, in the strict T1 limit:

- μ = m_p/m_e is σ-invariant (P9 testable as null prediction);
- α (fine-structure constant) is σ-invariant;
- atomic-clock-measured β-decay rates τ_n are σ-invariant (P3 predicts NO σ-environmental anomaly);
- all branching ratios and cross-section ratios are σ-invariant.

#### 3.3.1 The non-universality question and its consistency

Several proposed extensions of the framework — the σ-F̃F coupling underlying the σ-axion-equivalence claim of Section 4 (P4, P5), and the σ-environmental coupling that *would* explain the neutron-lifetime beam-trap discrepancy (P3 non-universal mode) — necessarily *break* strict universality. They couple σ to a specific sector (gauge bosons in the F̃F case; weak-decay matrix elements in the β-decay case) more strongly than to others.

**Honest framework position**: non-universal extensions ARE admissible in the framework, but each one is a separate T3- or T4-level extension that carries its own observational bounds. Specifically:

- **Strict T1**: universal coherent scaling. Only σ-invariant observables predicted; μ̇/μ = 0, α̇/α = 0, σ-environmental τ_n shift = 0.
- **Non-universal extensions**: σ couples differently to different sectors. Each such extension has parameters bounded by:
  - MICROSCOPE / Eötvös for free-fall composition dependence;
  - Atomic-clock comparisons for spatial σ-gradients (currently 10⁻¹⁸ level for similar-altitude clocks);
  - LLR Ġ/G for cosmological σ̇/σ rate (Section 4.4 of Paper A);
  - Quasar-absorption isospin spectroscopy for high-redshift dimensionless-ratio drift.

**The σ-axion claim and the σ-environmental claim are therefore on the same footing as non-universal T3/T4 extensions.** P3's non-universal mode that would explain the τ_n beam-trap anomaly requires δσ/σ ≈ -1.05% between trap-wall and beam-vacuum environments — a magnitude likely excluded by atomic-clock comparison bounds, leading to its FAIL verdict. P4/P5 require non-universal σ-F̃F coupling at literature couplings g_CS ≈ 0.036 — currently in tension with Planck birefringence (P4 FAIL) but consistent with nEDM (P5 PASS), and additionally challenged by the de Brito-Eichhorn-Lino dos Santos 2022 obstruction (Paper B §3.2.1).

The internal consistency requirement: every prediction declared a "GSC prediction" must be either (a) consistent with strict T1 universal scaling, or (b) explicitly identified as a non-universal extension and bounded by the appropriate observational constraints. A prediction declared as the latter cannot be FAIL-classified solely on the grounds that it requires non-universality, because non-universality is admitted in the framework's extension scope.

The kill-tests of T1 (universal scaling holds), T3 (specific non-universal couplings consistent with bounds), and T4 (more speculative non-universal modules) operate at different layers and are independent.

### 3.4 Kill-test for T3

T3 falls if either:

- All viable G(σ) running profiles consistent with the σ(t) phenomenology of T2 are excluded by precision tests of equivalence-principle universality, dimensionless-constant variation (Oklo, atomic-clock comparisons of α and m_e/m_p), or solar-system bounds on Ġ/G;
- A first-principles FRG derivation produces a running incompatible with the form required by T2.

As of the current framework cycle, the surviving G(σ) parameter region is narrow but non-empty.

---

## 3.5 (T3) Two Candidate Derivations of σ_*

The following two candidate derivations are tier T3 because they make σ_* a derived quantity rather than a phenomenological parameter. Both are at the level of "promising structural claims requiring further work", not finished derivations.

### 3.5.1 σ_* from non-commutative IR/UV mixing

In non-commutative quantum field theory with non-commutativity scale θ_NC ~ ℓ_Planck², loop corrections produce an emergent infrared scale through UV/IR mixing (Minwalla, Van Raamsdonk, Seiberg 2000; recent cosmological constraint papers cited at [JHEP 02 (2026) 035](https://link.springer.com/article/10.1007/JHEP02(2026)035)). Heuristically:

$$\Lambda_{IR} \sim \frac{1}{\sqrt{\theta_{NC} \cdot \Lambda_{UV}^2}}$$

We **conjecture** (not yet proven): σ_* ≅ Λ_IR for the gravitational sector, identifying the GSC critical scale with the UV/IR mixing scale of a fundamentally non-commutative spacetime. If so, σ_* is computable from θ_NC and the UV cutoff — providing the missing first-principles derivation.

This is genuinely speculative. It is included here because:

- It would close the most prominent open gap in T3;
- It connects GSC to active QG research (UV/IR mixing in cosmology is a 2026 topic);
- The claim is concrete enough to be falsifiable: if a properly-defined non-commutative gravity FRG analysis yields σ_* incompatible with the late-time fit, this derivation route is closed.

Status: conjecture, derivation incomplete, kill-test specified.

### 3.5.2 σ_* from holographic AdS/QCD warp factor

A second route, present already in v8/v9.1 as Appendix J, identifies σ_* with the QCD confinement scale via the holographic warp factor in AdS/QCD models. The hierarchy

$$G_s/G_N \sim 10^{11}$$

at hadronic scales emerges from a warp factor of α ~ 0.5 in the appropriate AdS_5/QCD model. This is a structurally different derivation route from §3.5.1: it makes σ_* a property of the strong-interaction sector rather than of the gravitational vacuum.

Status: developed at the level of order-of-magnitude consistency in earlier framework drafts (see [archive/v9_1_changelog.md](archive/v9_1_changelog.md)); not yet integrated with the quantitative late-time pipeline. The current QCD↔gravity bridge in [bridges/phase4_qcd_gravity_bridge_v0.1/](bridges/phase4_qcd_gravity_bridge_v0.1/) is held as a diagnostic-only annex from the predecessor release; we promote it here to a candidate T3 derivation.

The two routes are not mutually exclusive: §3.5.1 produces a gravitational-vacuum scale and §3.5.2 produces a QCD-vacuum scale. Their compatibility — whether they yield the *same* σ_* — would itself be a test.

---

## 4. (T3) σ-Field Coupling to Topological Sectors: The Strong CP Connection

This is one of the most consequential structural claims of the framework and accordingly deserves careful presentation. We claim that the same RG flow that drives G(σ) running automatically generates a σ–F̃F coupling, providing a cosmological mechanism for θ-relaxation that obviates the need for a separate axion particle.

### 4.1 The argument

Asymptotic-safety analyses of gravity-matter systems indicate that the gravitational fixed point exerts non-trivial influence on the renormalization of dimension-4 operators in the matter sector (see e.g. [Asymptotic safety in the dark, JHEP 08 (2018) 147](https://link.springer.com/article/10.1007/JHEP08(2018)147)). The QCD topological term

$$\mathcal{L}_\theta = \frac{\theta_{eff}}{32\pi^2} \, \text{Tr} (F_{\mu\nu} \tilde F^{\mu\nu})$$

is dimension-4. If σ controls the gravitational fixed-point displacement, and the gravitational fixed point couples non-trivially to the renormalization of the F̃F operator, then σ-evolution induces a coupling of the form:

$$\mathcal{L}_{\sigma\theta} = \frac{\sigma(t)}{f_\sigma} \, \text{Tr}(F_{\mu\nu} \tilde F^{\mu\nu})$$

for some derived scale f_σ. The cosmological evolution of σ then drives a corresponding evolution of θ_eff = θ_bare + σ/f_σ towards an attractor solution θ_eff → 0, in direct analogy with the Peccei–Quinn axion mechanism — but **without introducing a separate axion field**.

### 4.2 Why this is genuinely new

A literature search did not find this specific identification. Standard solutions to the strong CP problem are:

- Massless up-quark (excluded);
- Spontaneous CP violation in supersymmetric flavor sectors;
- Parity-based left-right symmetric theories;
- Boundary-condition manipulations of the QCD generating functional;
- Soft Peccei-Quinn breaking;
- Standard axion (Peccei-Quinn).

None of these is "RG-flow of gravity automatically generates θ-relaxation channel via the same σ-field that drives dark energy". The closest neighbours in the literature are axion-dilaton models, in which the axion is a *separate* field; here σ does double duty as cosmological scale field and as effective axion.

### 4.3 What needs to be done

This is a structural conjecture, not a derivation. A complete development requires:

1. A consistent FRG calculation showing the coupling f_σ generated by the gravitational fixed point is non-zero and of the right order;
2. A cosmological computation of the evolution θ_eff(z) compatible with current nEDM bounds (|θ_eff| ≲ 10^{-10} today);
3. A prediction for the high-z behaviour of θ_eff, testable by quasar absorption spectroscopy sensitive to nuclear isospin breaking, and by cosmic birefringence measurements via the σ-F̃F Chern-Simons coupling.

### 4.4 The bonus prediction: CMB cosmic birefringence

The σ-F̃F coupling, restricted to the photon sector via the chiral anomaly, predicts a **non-zero CMB cosmic birefringence angle**

$$\beta = \int \frac{\sigma(z)}{f_\sigma} \, c \, \frac{dt}{dz} \, dz$$

The Planck team has reported tentative detection of β ~ 0.35° ± 0.14° (Minami & Komatsu 2020). The σ-field amplitude required to match this signal is calculable from the late-time fit, providing a *consistency check* between two completely different observables: dark-energy expansion history and CMB B-mode rotation. LiteBIRD and CMB-S4 will measure β to ~0.05° precision, sharpening this test.

A coherent story: one σ-field, dark energy, strong CP, CMB birefringence. If the numbers work, this is the framework's cover-story.

### 4.5 Kill-tests

- nEDM measurement of θ_eff at the 10^{-12} level would tightly constrain the σ-evolution amplitude.
- LiteBIRD birefringence measurement incompatible with the late-time σ-fit would falsify this T3 module.

---

## 5. (T4) Topological Defects from σ_*-Crossing: Vortex Dark Matter Derivation

### 5.1 Kibble–Zurek mechanism applied to GSC

When a system is driven through a continuous phase transition at finite rate τ_quench, topological defects form with a density set by Kibble–Zurek scaling:

$$n_{\text{defects}} \sim \xi_{KZ}^{-d} \sim \tau_{\text{quench}}^{-d\nu/(1+\nu z)}$$

where ν and z are critical exponents of the transition and d is the spatial dimension. The mechanism was developed by Kibble (1976) for cosmological phase transitions and by Zurek (1985) for condensed-matter analogues; it is universal physics.

In GSC, the cosmological evolution of σ(t) crosses the effective critical scale σ_* with a finite rate set by σ̇/σ at the crossing epoch. We propose:

**The σ_*-crossing in GSC's RG-running ansatz constitutes a continuous phase transition in the effective gravitational sector. Topological defects formed at this crossing carry the Kibble–Zurek density appropriate to the universality class of the transition.**

### 5.2 What this derives

Earlier framework drafts (v9.1) postulated a vortex density in the cosmological superfluid vacuum. Here this density is **derived** from the σ-running rate at σ_*-crossing using KZ scaling. Concretely:

- The vortex density n_vortex is computable from σ̇(σ_*) and the critical exponents of the gravitational FRG fixed point;
- The dark matter abundance Ω_DM is then a *prediction*, not a free parameter;
- The dark matter spatial distribution naturally follows baryon distribution because vortices nucleate in regions of strongest σ-gradient, which correlate with mass concentration.

This is exactly the kind of derivation that was missing in v9.1: bold qualitative claim made specific by quantitative mechanism.

### 5.3 Specific predictions

- **Cosmic-string density** at late times: predicted from KZ scaling with σ_* parameters from the late-time fit.
- **Stochastic gravitational-wave background** from the cosmic string network, with characteristic frequency spectrum testable by NANOGrav, EPTA, and LISA.
- **CMB B-mode signature** distinct from inflationary gravitational waves (cosmic strings produce vector and tensor modes with specific power-spectrum signature).

### 5.4 Kill-tests

- LISA or NANOGrav exclusion of cosmic-string GW background at the GSC-predicted amplitude.
- LiteBIRD/CMB-S4 B-mode pattern incompatible with the predicted defect contribution.
- Observations of dark-matter distribution in dwarf galaxies or low-surface-brightness systems incompatible with vortex-tangle phenomenology.

### 5.5 Consistency note

This T4 module *replaces* the v9.1 superfluid-vortex postulate with a *derived* version. Failure of the derivation does not eliminate v9.1's vortex DM as a phenomenological possibility; it eliminates the specific KZ-based version proposed here. Other T4 modules (informational thermodynamics, holographic proton) are unaffected.

---

## 6. (T4) Spatial σ-Field, MOND Phenomenology, and Galactic Dynamics

### 6.1 σ as a field σ(x, t)

The T2/T3 treatment assumes σ depends only on cosmic time. The natural field-theoretic extension promotes σ to a spatial field σ(x, t) with kinetic term

$$\mathcal{L}_\sigma = \frac{1}{2} (\partial_\mu \sigma)(\partial^\mu \sigma) - V(\sigma)$$

and coupling to local matter density via the same mechanism that makes σ run cosmologically (G(σ) carrying the matter dependence).

### 6.2 MOND from σ-gradient

Bound by current cosmological evolution σ_0 = σ(t_now), local σ(x) deviates from σ_0 in the presence of matter concentrations. In deep gravitational potentials, σ relaxes to a different equilibrium, producing:

- A spatial gradient ∇σ that generates a fifth force;
- A coherence length λ_σ of σ-fluctuations setting an effective MOND scale;
- A radial-acceleration relation arising naturally from the σ-equation of motion in galactic potentials.

This is structurally similar to recent scale-covariant MOND work (e.g. [Scholz 2025, arXiv:2510.17704](https://arxiv.org/html/2510.17704)) but combined with cosmological σ-evolution from T2.

### 6.3 Predictions distinct from MOND

Critically, GSC's σ(x, t) gives predictions distinct from generic MOND:

- The MOND scale a_0 should evolve cosmologically with σ_0(t), giving slow secular evolution of galactic flat-rotation curves (very weak signal but in principle observable).
- Cluster-scale dynamics differ from galaxy-scale because σ-equilibrium depends on potential depth, not just mass density.
- Cosmic voids exhibit anomalous peculiar-velocity signatures from σ-equilibrium in low-density regions (testable with DESI peculiar velocities, Euclid).

### 6.4 Kill-tests

- Independent cluster-scale observations (e.g. cluster mass-temperature relations) incompatible with σ(x)-predicted profiles.
- DESI peculiar-velocity surveys finding standard ΛCDM consistency at the GSC-predicted deviation level.

---

## 7. (T3+T4) Information-Thermodynamic Interpretation

### 7.1 Verlinde-style entropic gravity, refined

If gravity is entropic in the Verlinde sense — emerging from information-theoretic counting at horizons — then the gravitational coupling G should be tied to information density. In GSC, this gives:

- σ-running tracks the change in cosmological information density;
- The Bekenstein bound at hadronic scales (saturated for proton-mass black holes) provides a candidate microphysical origin for σ_*;
- The proton effectively saturates the Bekenstein bound, with G_s/G_N ~ exp(S_Bek) ~ 10^{11} at hadronic scales.

These claims are present in earlier framework drafts (v9.1, Sections 10–11). The current framework retains them as T4 modules with the following discipline:

1. Claims that survived dimensional re-checking are restored;
2. Claims found to have order-of-magnitude inconsistencies (documented in [v9.1/DEFERRED_IDEAS_v10.md](../GSC%20v9.1/DEFERRED_IDEAS_v10.md)) are explicitly deferred with the corresponding open problem stated;
3. The Bekenstein-Landauer derivation of proton mass remains phenomenologically suggestive but not promoted to a derivation.

### 7.2 σ-rate as holographic complexity rate

A novel T4 connection: identifying σ̇/σ with the rate of growth of holographic complexity (Susskind's "complexity = volume" or "complexity = action" conjectures). This would derive the cosmological evolution rate of σ from a Lloyd bound on the rate of cosmological computation, providing a microphysical origin of σ̇.

Status: conjecture. Recent work on holographic complexity in FLRW ([Phys. Rev. D 101, 046006](https://journals.aps.org/prd/abstract/10.1103/PhysRevD.101.046006)) and dilaton-dependent complexity ([Phys. Rev. D 97, 066022](https://dx.doi.org/10.1103/PhysRevD.97.066022)) provides a foundation. The specific GSC identification is, to our knowledge, novel.

### 7.3 σ as RG-flow time (Connes connection)

In Connes's thermal-time hypothesis, time emerges as the modular flow of the algebra of observables. In GSC, identifying

$$\sigma(t) \propto \exp(-t/\tau_{RG})$$

makes cosmological time the parameter of RG flow. This is a deeply structural reframing: time is not external, but emergent from the running of couplings. The framework becomes a cosmological realization of Connes's program.

Status: philosophical-conceptual contribution; not yet a quantitative claim. Notable for connecting GSC to the noncommutative-geometry community.

---

## 8. (T4) σ as Cosmological Quantum Reference Frame

### 8.1 Background: quantum reference frames

The Giacomini–Brukner–Castro-Ruiz program (arXiv:1712.07207 and subsequent papers) developed a formalism for *quantum reference frames* (QRFs): observers whose reference frame is itself a quantum system in superposition. Quantum features such as superposition and entanglement become *frame-dependent*. This is a major topic in current quantum-gravity research with mature mathematical formalism for spacetime QRFs (e.g. [Quantum 5, 508 (2021)](https://quantum-journal.org/papers/q-2021-07-22-508/)).

### 8.2 σ as a cosmological QRF

Different observers in different σ-eigenstates witness different cosmologies. The "freeze frame" of Section 1 is the description in the σ-classical (large-σ-amplitude) limit. The general QRF formulation:

- Takes the cosmological scale field σ as a quantum system with its own degrees of freedom;
- Defines observable cosmologies relative to the σ-state of the observer;
- Recovers the geometric-lock condition (Section 1.3) as a *theorem* about invariance of dimensionless observables under σ-QRF transformations.

### 8.3 Why this matters

This is the most conceptually novel reframing in the current cycle. It:

- Connects GSC to active QG research with established formal vocabulary;
- Provides a rigorous statement of what observers in different cosmologies can and cannot agree on;
- Suggests an empirical handle: cosmological superpositions (if any) of σ-states have decoherence rates set by σ-coupling to matter, in principle bounded by CMB primary-anisotropy data.

Status: structural reformulation. A complete development requires defining the σ-QRF Hilbert space and its transformation rules — this is the central piece of the current theoretical program.

---

## 9. Pre-Registered Predictions

A defining methodological feature of the framework is **pre-registration** of numerical predictions before observational data are released. The pre-registration register is a cryptographically-signed, time-stamped artifact at [predictions_register/](predictions_register/), with each entry containing:

- The prediction itself, expressed as a numerical range or threshold;
- The σ(t) ansatz and parameter values producing it;
- The relevant scripts and pipeline invocation;
- The target observational dataset and its expected release date;
- A SHA-256 hash of the corresponding scoring pipeline output.

Pre-registration prevents post-hoc parameter adjustment and converts the reproducibility infrastructure from a *referee tool* into a *falsification engine*. This is the operational core of the framework.

The eight central predictions are summarized below.

### 9.1 Prediction P1: BAO standard-ruler shift in DESI Year-3

**Statement.** The BAO acoustic scale r_s in GSC differs from the ΛCDM expectation by a calculable amount due to the σ-dependence of c_s and t_rec. The prediction is

$$\Delta r_s / r_s \mid_{GSC - \Lambda CDM} = f(\sigma_*, \text{ansatz})$$

with f(·) computed from the late-time fit parameters and propagated through the early-Universe sound horizon integral.

**Pipeline.** Extension of `scripts/phase4_desi_bao_*.py` to compute GSC-specific r_s. See [predictions_register/P1_bao_ruler_shift/](predictions_register/P1_bao_ruler_shift/).

**Target.** DESI Year-3 BAO release, expected 2027.

**Kill-test.** Observed Δr_s/r_s outside the GSC-predicted band at >3σ falsifies T2.

**Effort.** ≈ 2 weeks to compute GSC-specific r_s and lock in prediction. This is the lowest-effort, highest-impact near-term test.

### 9.2 Prediction P2: 21cm Cosmic Dawn signal

**Statement.** The cosmological 21cm absorption signal at z ≈ 15–25 in GSC differs from ΛCDM expectation through σ-evolution of:

- Recombination history (z_rec, x_e);
- Lyman-α coupling efficiency in spin-temperature determination;
- X-ray heating rate of the IGM;
- Wouthuysen-Field effect amplitude.

**Pipeline.** New module `gsc/cosmic_dawn/` (to be created), building on existing structure-formation code in [gsc/structure/](gsc/structure/).

**Target.** HERA Phase-II (~2027) and SKA-Low precision measurements (~2030).

**Kill-test.** Observed 21cm globally averaged signal at z ≈ 17 incompatible with GSC-predicted profile.

**Bonus.** The EDGES 2018 anomalously-deep absorption profile at z ≈ 17 — currently unexplained — is a candidate target for natural GSC explanation.

**Effort.** ≈ 2–3 months for a publishable computation.

### 9.3 Prediction P3: Neutron-lifetime beam–trap discrepancy

**Statement.** The currently-unexplained ~9 second discrepancy between beam (τ_n ≈ 887.7 s) and trap (τ_n ≈ 878.4 s) measurements of free-neutron lifetime arises from σ-environmental dependence: σ takes slightly different equilibrium values in the high-density trap-wall environment vs. the beam free-vacuum environment, modifying the β-decay rate by a calculable amount.

**Pipeline.** Computation of the σ-derivative of β-decay rate via dependence of V_ud, M_n − M_p, and Fermi coupling on σ.

**Kill-test.** Different trap geometries (varying wall material, density, distance) should exhibit different τ_n at the predicted level. UCNτ and other ongoing experiments can test this directly.

**Effort.** ≈ 1 month for first-pass computation; experimental tests are independently funded.

**Significance.** If validated, this would explain a real experimental anomaly and provide a *table-top* test of GSC. Significantly cheaper than space telescopes.

### 9.4 Prediction P4: CMB cosmic birefringence

**Statement.** The σ-F̃F coupling of Section 4 predicts cosmic birefringence

$$\beta = \int_0^{z_{CMB}} \frac{\sigma(z)}{f_\sigma} \, c \, \frac{dt}{dz} \, dz$$

with amplitude calculable from the late-time σ-fit and the derived σ-θ coupling.

**Target.** Planck (current ~0.35° ± 0.14° hint), LiteBIRD (~2030), CMB-S4 (~2032).

**Kill-test.** LiteBIRD measurement of β incompatible with GSC-predicted band at >3σ falsifies the σ-F̃F coupling (Section 4) and consequently the strong-CP-axion-replacement claim.

### 9.5 Prediction P5: Strong-CP θ-bound consistency

**Statement.** The σ-θ coupling drives θ_eff(z) along a calculable trajectory. The current value |θ_eff(z=0)| ≲ 10^{-10} (from neutron EDM, |d_n| < 1.8 × 10^{-26} e·cm) bounds the σ-coupling parameter f_σ.

**Kill-test.** Future nEDM measurement of θ_eff at the 10^{-12} level inconsistent with the σ-evolved attractor falsifies Section 4.

### 9.6 Prediction P6: Kibble-Zurek defect spectrum

**Statement.** The σ_*-crossing produces topological defects with density set by KZ scaling. The cosmic-string network from this defect-formation epoch produces a stochastic GW background with characteristic frequency spectrum dN/df.

**Target.** NANOGrav, EPTA (current), LISA (~2035).

**Kill-test.** Stochastic GW background incompatible with predicted spectrum, or absence of expected signal at GSC-predicted amplitude.

### 9.7 Prediction P7: GW-memory atomic-clock signature

**Statement.** Each LIGO/Virgo merger event produces a GW memory shift that, via σ-coupling, induces a permanent shift in σ-equilibrium and consequently in atomic transition frequencies. A globally-distributed network of optical-lattice atomic clocks should observe correlated frequency shifts following major merger events.

**Pipeline.** Post-event analysis of existing atomic-clock comparison data, time-correlated with LIGO/Virgo trigger times.

**Target.** Existing data from ITOC, BACON; future BACON-II.

**Kill-test.** No correlated shift observed at the GSC-predicted amplitude, given the GW-memory amplitudes inferred from LIGO data.

**Significance.** Uses existing infrastructure; no new instruments required. Among the lowest-cost observational tests.

### 9.8 Prediction P8: Redshift-drift sign and amplitude

**Statement.** The historical GSC prediction: redshift-drift sign at z ≈ 2–5 differs from ΛCDM. Now framed as a *supporting* discriminator, not the primary kill-test (the previously primary status was demoted in v11 in light of refined late-time data).

**Target.** ELT/ANDES (~2040+).

---

## 10. The v11 Reproducibility Stack: Operational Foundation

GSC is not only a theoretical proposal; it is built on a deterministic, publicly-auditable software stack. Key components:

- **Core package:** [gsc/](gsc/) — measurement model, σ(t) fits, datasets, structure, RG diagnostics, epsilon framework.
- **Schema validation:** [schemas/](schemas/) — JSON schemas for all major artifacts; validation gates publication.
- **Lineage DAG:** `scripts/phase2_lineage_dag.py` — deterministic provenance from inputs to outputs.
- **Continuous integration:** [.github/workflows/](.github/workflows/) — stdlib-only smoke tests and full-stack pipeline tests.
- **Repo footprint cap:** Hard-enforced via `audit_repo_footprint.py --max-mb 10`.
- **Operator scripts:** `operator_one_button.sh`, `release_candidate_check.sh`, `arxiv_preflight_check.sh`.
- **Submission bundles:** referee packs, paper assets, JOSS preflight.

The current cycle adds:

- **Pre-registration register** [predictions_register/](predictions_register/) — cryptographically-signed, time-stamped predictions with associated computation pipelines.
- **Tier-tagged claim ledger** `docs/claim_ledger.json` (to be migrated from the predecessor framework with tier annotations) — every claim labelled with tier, kill-test, dependency.
- **Falsification scoring scripts** that automatically compare published observational data against pre-registered predictions and produce timestamped scorecards.

This converts the existing reproducibility stack from a *defensive* tool ("here are our results, you can re-run them") into an *offensive* tool ("here is our prediction, signed and dated; here is the scoring pipeline; you cannot move the goalposts").

---

## 11. Layered Publication Strategy

Rather than a single monolithic paper, the framework is published as a four-paper layered programme matched to the tier hierarchy. This protects each layer from collateral damage in review.

### 11.1 Paper A — Empirical late-time (T1 + T2)

**Title.** *GSC: A Scale-Covariant Measurement-Theoretic Framework for Late-Time Cosmology.*

**Length.** ≈ 30 pages.

**Content.** The freeze-frame measurement model; σ(t) phenomenological ansätze; late-time fits to Pantheon+SH0ES, DESI BAO, fσ8; the geometric-lock consistency condition; pre-registered BAO ruler-shift prediction.

**Venue.** Phys. Rev. D, JCAP.

**Position relative to Wetterich.** Cited prominently; GSC positioned as specific crossover realization with explicit reproducibility stack and pre-registration.

### 11.2 Paper B — Theoretical mechanism (T3)

**Title.** *Renormalization-Group Running of the Gravitational Coupling and Cosmological Scale Field in GSC.*

**Length.** ≈ 25 pages.

**Content.** The G(σ) ansatz; status of σ_*; non-commutative IR/UV mixing as candidate derivation; AdS/QCD warp-factor route; FRG-motivated coupling to the QCD topological sector; predicted CMB birefringence consistency check.

**Venue.** CQG, JHEP.

### 11.3 Paper C — Speculative extensions (T4)

**Title.** *Information-Thermodynamic and Topological Extensions of GSC: Vortex DM, Holographic Proton, and Cosmological Quantum Reference Frames.*

**Length.** ≈ 40 pages.

**Content.** KZ-derived vortex DM; spatial σ(x,t) and MOND phenomenology; holographic proton at the Bekenstein bound; σ as cosmological QRF; σ ≅ RG-flow time (Connes); each module explicitly modular with independent kill-tests.

**Venue.** Foundations of Physics; Universe; or as preprint with selective journal targeting.

**Discipline.** Each module has its own §X.kill-test subsection; reviewer rejection of any one module does not invalidate the others.

### 11.4 Paper D — Methodology and software (publication infrastructure)

**Title.** *A Pre-Registration Reproducibility Stack for Falsifiable Cosmological Models.*

**Length.** ≈ 15 pages.

**Content.** The deterministic reproducibility stack; schema validation; lineage DAG; the pre-registration register; scoring pipelines; case studies from each Paper A–C prediction.

**Venue.** Journal of Open Source Software; Astronomy and Computing; SoftwareX.

**Significance.** Methodology Paper D is independently citable and provides credibility for the empirical claims of A–C even if the physical extensions are eventually disfavoured. Survives any physics outcome.

### 11.5 Why this structure

A reviewer can:

- Reject Paper C's vortex DM derivation without affecting acceptance of Paper A;
- Reject Paper B's σ-θ coupling without affecting Paper A's empirical fit;
- Cite Paper D's reproducibility methodology without endorsing any specific physical claim;
- Endorse Paper B's RG ansatz while remaining agnostic on Paper C's extension modules.

This is the operational realization of the tier hierarchy.

---

## 12. Honest Limitations and Known Gaps

The following are not solved by the current framework and should not be claimed:

### 12.1 σ_* derivation

Despite the two candidate routes of §3.5, σ_* remains effectively phenomenological. A complete first-principles derivation is outstanding work and a top priority for the next major framework cycle.

### 12.2 Conformal-frame triviality

Section 1.2 addresses this critique structurally but does not eliminate it. The empirical content of GSC depends on σ having genuinely independent dynamics. Demonstrations of this independence are concentrated in the T3 ansatz (specific G(σ) running) and T4 modules (σ-θ coupling, σ(x,t) gradient effects). If all of these fail, GSC reduces to a re-parametrization of ΛCDM.

### 12.3 Full CMB closure

GSC's CMB treatment uses compressed distance priors (CHW2018) and per-multipole consistency checks via a bridge layer. Full TT/TE/EE likelihood closure is not in canonical scope. Phase-2 E2 work continues as diagnostic-only.

### 12.4 Full perturbation closure

Linear-growth diagnostics are implemented; nonlinear structure formation and full Boltzmann coupling are at the bridge level (Phase-3) and not in canonical scope.

### 12.5 σ-axion equivalence as derivation

The argument of Section 4 is structural and motivational, not a derivation. A complete FRG calculation showing the gravitational fixed point produces a non-zero σ-F̃F coupling at the right order is outstanding.

### 12.6 Vortex DM derivation

The KZ argument of Section 5 is qualitative; concrete numerical predictions require the FRG critical exponents at the σ_*-crossing fixed point, which are not yet computed.

### 12.7 Cosmological QRF formalism

Section 8 is a reframing, not a complete formalism. Defining the σ-QRF Hilbert space and its transformation rules remains outstanding theoretical work.

These limitations are listed here, in the main document, deliberately. The framework's credibility depends on honesty about what is open.

---

## 13. Roadmap to the Next Cycle

**Six-month milestones:**

- **M201:** Pre-registration register implementation; first prediction (BAO ruler shift) signed and dated;
- **M202:** 21cm Cosmic-Dawn module implementation; second prediction signed;
- **M203:** Neutron-lifetime σ-derivative computation; third prediction signed;
- **M204:** Paper A draft circulated to internal reviewers;
- **M205:** Paper D (methodology) draft and JOSS preflight.

**Twelve-month milestones:**

- **M210:** σ-F̃F coupling FRG calculation initiated (collaboration-dependent);
- **M211:** Vortex-DM KZ critical-exponent computation;
- **M212:** σ-QRF formalism initial draft;
- **M213:** Paper B draft circulated;
- **M214:** First DESI Y3 scoring report.

**Eighteen-month milestones (next-cycle candidates):**

- **M220:** Either a derivation of σ_* from one of the two candidate routes, or honest documentation that both have been excluded;
- **M221:** Either consistent FRG-derived σ-F̃F coupling, or removal of the strong-CP claim;
- **M222:** Paper C draft;
- **M223:** First scoring of pre-registered predictions against released observational data.

The next major framework release is gated on the σ_* derivation outcome. If σ_* remains phenomenological, the next cycle will be a refinement with sharper kill-tests but the same open problem; if a derivation succeeds, σ_* may be promoted from T3 to T2 / T1 status.

---

## 14. Closing Position Statement

GSC is a *layered* theory: each tier defends itself, each module defends itself, the methodology paper defends the methodology.

(This document is the canonical framework specification. Predecessor framework drafts and triage history are in [archive/](archive/).)

The framework's central methodological commitment is that **truth claims should be exposed at the granularity at which they can be falsified**, and the publication strategy, the documentation, and the software stack are organized to enforce this.

The framework is *not* a claim that ΛCDM is wrong; it is a claim that a scale-covariant alternative exists with independent dynamics, falsifiable predictions in the next observational decade, and an operational reproducibility infrastructure that is itself a contribution worth making.

The framework *is* a claim that the v9.1 maximalism (twelve sections, eleven predictions, vortex DM, holographic proton) and the v11 discipline (deterministic pipelines, schema validation, reproducibility stack) are not in fundamental tension. They can co-exist, provided the architecture acknowledges different levels of epistemic confidence and structures the work accordingly.

Whether GSC succeeds will be determined by the next observational decade: DESI Year-3 BAO, LiteBIRD birefringence, HERA/SKA 21cm, neutron-lifetime experiments, and cosmic-string GW backgrounds will produce sharp, pre-registered tests of specific GSC predictions. Failure of any individual prediction will cleanly eliminate the corresponding tier or module, leaving the others unaffected. Success of multiple independent predictions would constitute genuine evidence beyond ΛCDM.

The framework's honesty is its strongest defensive position. Every limitation is explicit. Every kill-test is specified. Every prediction is pre-registered. If the universe disagrees with the framework, we will know — and we will know which part disagrees.

---

## Appendices (referenced; to be developed separately)

- **Appendix A** — Wetterich and asymptotic-safety lineage; detailed positioning.
- **Appendix B** — Mathematical conventions; metric signature; unit choices.
- **Appendix C** — Software stack reference (gsc/, scripts/, schemas/).
- **Appendix D** — Pre-registration log format and cryptographic signing protocol.
- **Appendix E** — Detailed late-time fit results (porting from v11 release).
- **Appendix F** — RG-flow ansatz: candidate G(σ) parametrizations and their phenomenological ranges.
- **Appendix G** — σ_* candidate derivations: technical details (non-commutative IR; AdS/QCD warp).
- **Appendix H** — σ-F̃F coupling: structural argument and outstanding FRG calculation.
- **Appendix I** — Kibble-Zurek defect-formation calculation: critical exponents and string-density estimates.
- **Appendix J** — σ as cosmological QRF: Hilbert-space construction sketch.
- **Appendix K** — Pre-registered predictions: detailed numerical tables.
- **Appendix L** — Falsification scoring pipelines: algorithmic specification.
- **Appendix M** — Compatibility with v11 canonical artifacts and migration notes.

---

## References (working set)

- Wetterich, C. *A Universe without expansion.* arXiv:1303.6878 (2013).
- Wetterich, C. *Quantum gravity and scale symmetry in cosmology.* (Cosmon-quintessence series.)
- Canuto, V. M. et al. *Scale-covariant theory of gravitation.* Phys. Rev. D 16, 1643 (1977).
- Reuter, M. & Saueressig, F. *Quantum gravity and the functional renormalization group.* Cambridge UP.
- Giacomini, F., Castro-Ruiz, E. & Brukner, Č. *Quantum mechanics and the covariance of physical laws in quantum reference frames.* arXiv:1712.07207.
- Höhn, P. A. et al. *Spacetime quantum reference frames and superpositions of proper times.* Quantum 5, 508 (2021).
- Minwalla, S., Van Raamsdonk, M. & Seiberg, N. *Noncommutative perturbative dynamics.* JHEP 02, 020 (2000).
- Eichhorn, A. & Versteegen, F. *Asymptotic safety in the dark.* JHEP 08, 147 (2018).
- Volovik, G. E. *The Universe in a Helium Droplet.* Oxford UP (2003).
- Verlinde, E. *On the origin of gravity and the laws of Newton.* JHEP 04, 029 (2011).
- Connes, A. & Rovelli, C. *Von Neumann algebra automorphisms and time-thermodynamics relation in generally covariant quantum theories.* Class. Quant. Grav. 11, 2899 (1994).
- Kibble, T. W. B. *Topology of cosmic domains and strings.* J. Phys. A 9, 1387 (1976).
- Zurek, W. H. *Cosmological experiments in superfluid helium?* Nature 317, 505 (1985).
- Susskind, L. *Computational complexity and black hole horizons.* Fortsch. Phys. 64, 24 (2016).
- Favata, M. *The gravitational-wave memory effect.* Class. Quant. Grav. 27, 084036 (2010).
- Minami, Y. & Komatsu, E. *New extraction of the cosmic birefringence from the Planck 2018 polarization data.* Phys. Rev. Lett. 125, 221301 (2020).
- Scholz, E. *Einstein gravity extended by a scale covariant scalar field with Bekenstein term and dynamical mass generation.* arXiv:2510.17704 (2025).

(Full reference list to be built out in companion `paper.bib` for each of Papers A–D.)

---

*GSC working draft. Not for citation as published work. Comments and corrections welcome via repository issues.*
