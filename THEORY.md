# GSC — Theory

*A layered scale-covariant cosmology with pre-registered falsification.*

**Status in one paragraph.** GSC describes cosmic redshift as the coherent shrinking of bound matter
against a nearly static background, instead of space expanding. In its pure form (tier T1) this is a
mathematically exact re-description of standard cosmology (ΛCDM): every dimensionless observable is the
same. The framework's content beyond ΛCDM therefore lives in its higher tiers. Today that content is small:
gravity slightly weaker, relative to atoms, in the early universe (P14). The registered late-time deviation, a
+0.417% shift of the BAO standard ruler (P1), turned out to have one coherent reading, which a joint CMB + BAO fit
absorbs into H₀ (see [OPEN_PROBLEMS.md](OPEN_PROBLEMS.md)). Beyond that there is a package of exact null
predictions that the framework pre-commits to die on. Most mechanism and extension modules (tiers T3 and T4)
are excluded by data or remain conjectures. The contribution that survives any physics outcome is the method
([METHOD.md](METHOD.md)).

## Contents

1. [Lineage: what is and is not original](#1-lineage-what-is-and-is-not-original)
2. [Architecture: four tiers](#2-architecture-four-tiers)
3. [T1 — the freeze-frame measurement model](#3-t1--the-freeze-frame-measurement-model)
4. [T2 — the late-time ansatz](#4-t2--the-late-time-ansatz)
5. [T3 — mechanism hypotheses](#5-t3--mechanism-hypotheses)
6. [T4 — speculative extension modules](#6-t4--speculative-extension-modules)
7. [The fifteen registered predictions](#7-the-fifteen-registered-predictions)
8. [Kill conditions (pre-committed)](#8-kill-conditions-pre-committed)
9. [Limitations](#9-limitations)
10. [References](#10-references)

---

## 1. Lineage: what is and is not original

The core thesis — that observed cosmological redshift can be reframed as the coherent shrinkage of bound
matter against an approximately static background — is not original to this work. The observational
equivalence was developed by **C. Wetterich**, *A Universe without expansion* (arXiv:1303.6878, 2013), and
by his programme identifying cosmon-driven dark-energy evolution with asymptotic-safety renormalization-group
flow. The scale-covariant theory of gravitation goes back to **Canuto et al.** (Phys. Rev. D 16, 1643, 1977).

GSC positions itself inside this lineage as a specific phenomenological realization — an ansatz for the scale
field σ(t) — supplemented by two things that are its own: an explicit **layered claim hierarchy** with a
kill-test per layer, and a **pre-registered falsification programme** built on a deterministic,
self-verifying software stack. The claims original to GSC are extensions and synthesis, not the underlying
frame equivalence.

## 2. Architecture: four tiers

A framework does not have to defend or abandon every module at once. GSC separates its claims into four
tiers of epistemic confidence. Each tier states what it asserts, how it could be falsified, and what survives
if it fails.

| Tier | Type | Claim | Kill-test | If false, what survives | Current status |
|---|---|---|---|---|---|
| **T1** | Kinematic frame | Freeze-frame shrinkage is conformally equivalent to FLRW expansion; all local dimensionless physics is invariant (the *geometric lock*) | Mathematical inconsistency, or a robust detection of any exact-null violation (kill conditions K1, K2) | — | Alive; every null test so far passes |
| **T2** | Phenomenological ansatz | A small late-time σ(t) evolution with one canonical parameter p | Registered observations outside the predicted band; DR1-era BAO sets p < 7.63×10⁻⁴ | T1 | Alive at p = 6×10⁻⁴ in the registered heuristic. Its only coherent reading confines the drift to z > 10, where a CMB + BAO fit absorbs it into H₀ and leaves early-universe gravity (P14; OPEN_PROBLEMS.md problem 1) |
| **T3** | Mechanism hypotheses | Renormalization-group running of G(σ); σ couplings to specific sectors | All viable profiles excluded by precision tests, or incompatible with a first-principles derivation | T1 + T2 | Largely excluded or conjectural (§5) |
| **T4** | Speculative extensions | Defects, spatial σ(x), information-thermodynamic and quantum-reference-frame readings | Per-module observational tests | T1 + T2 + T3 | Mostly excluded or untested (§6) |

Every section below is labelled with its tier, so a reader can see exactly what they accept or reject with
each argument.

---

## 3. T1 — the freeze-frame measurement model

### 3.1 Frame equivalence

Scalar–tensor cosmologies admit physically equivalent descriptions related by conformal rescaling:

- **Einstein-like frame:** particle masses are constant; the metric expands (FLRW, scale factor a(t)).
- **Freeze frame:** the background geometry is approximately Minkowski; particle masses, atomic radii and
  clock frequencies vary coherently with one scale field σ(t).

Only **dimensionless ratios** of comparable quantities are observable. Neither frame is "true"; both give
identical predictions for every well-defined dimensionless observable. The choice of frame is a choice of
parametrization.

### 3.2 The conformal-triviality critique

The standard objection: *if the two frames are equivalent, the freeze frame is ΛCDM with a change of
variable.*

- **Where the objection is right:** for a *passive* scale parameter, whose evolution is fixed entirely by the
  Einstein-frame content, the frames are observationally identical. The freeze frame then adds only
  interpretation.
- **Where it can fail:** if σ has *independent dynamics*, or couples to some sectors differently from others,
  the frame map is no longer a free gauge choice and new observables appear.

The empirical content of GSC therefore reduces to one question: *does σ have independent dynamics, and in
which sector is it visible?* Everything above T1 is an attempt to answer that question, and the recent
consistency review ([OPEN_PROBLEMS.md](OPEN_PROBLEMS.md)) shows the answer constrains itself sharply: a
perfectly universal rescaling is unobservable by construction, so any observable deviation must be carried by
a specific non-universality — and each non-universality has its own precision bounds.

### 3.3 The operational measurement model

Implemented in `gsc/measurement_model.py` and documented in [docs/measurement_model.md](docs/measurement_model.md).
Photons propagate in an approximately static background with constant energies along their paths; atomic
transition energies at emitter and detector evolve with σ. The observed redshift is

$$1 + z_{obs} = \frac{\Delta E_{atom}(t_{em})}{\Delta E_{atom}(t_{det})} = \frac{\sigma(t_{em})}{\sigma(t_{det})} \cdot R_{geom}$$

where R_geom captures geometric path effects. For background cosmology R_geom = 1: the entire redshift is
metrology drift. Distance modulus, BAO ruler and growth rate are all expressible in this form.

### 3.4 The geometric lock

Local experiments (atomic-clock comparisons, GPS, lunar laser ranging) show no secular drift. The framework
therefore requires σ to couple **universally** to all dimensional sectors at leading order:

- particle masses m ∝ σ⁻¹;
- Newton's coupling G ∝ σ²;
- lengths r ∝ σ.

Under this *strict universal coherent scaling* every dimensionless particle-physics ratio is σ-invariant:
μ = m_p/m_e, the fine-structure constant α, β-decay rates measured by atomic clocks, branching ratios and
cross-section ratios, and the gravitational coupling G m²/ħc. The lock is a hard consistency condition, not a
free parameter, and it is what the exact-null predictions P9, P11, P12 and P13 test.

### 3.5 What T1 commits to

T1 commits only to the freeze frame as a valid parametrization, to observables being dimensionless ratios of
evolving scales, and to the geometric lock. It commits to no σ(t) law, no running of G, and no extension
module. Mathematically T1 is essentially unfalsifiable; observationally it is exposed through its exact
nulls, any one of which can end it (kill conditions K1 and K2).

---

## 4. T2 — the late-time ansatz

### 4.1 The canonical parameter

T2 adds a small late-time σ evolution with one canonical parameter, defined in `gsc/canonical_params.py`:

$$\sigma(z)/\sigma(0) = (1+z)^{-p}, \qquad p = 6 \times 10^{-4}.$$

The value was chosen inside the region allowed by already-public data: the registered DESI Year-1 check
(|z| < 3) allows p < 7.63×10⁻⁴. It was deliberately taken near that boundary rather than near zero, because a
theory kept alive by shrinking its observables to zero is not alive.

**Role of p.** p is a *metrology* exponent: a leading-order modulation of atomic units relative to a
flat-ΛCDM background, and the only sense in which the registered pipelines P1, P2, P4, P5 and P9 use it. It
must never be read as an expansion law H(z) = H₀(1+z)^p (a coasting universe excluded by the package's own BAO
data); a mechanical guard in `verification/claims.json` forbids that use in any registered pipeline.

**Open problem.** Which sector carries p — and therefore which other observables must move with it — is not
yet specified consistently across the register. A universal σ rescaling is unobservable, so the P1 shift
requires a specific non-universality, and the most natural one implies a present-day drift of G relative to
atomic units that lunar laser ranging constrains. The only reading that survives both lunar ranging and a joint
CMB + BAO fit confines the drift to the early universe, where the fit absorbs it into H₀. This is problem 1 in
[OPEN_PROBLEMS.md](OPEN_PROBLEMS.md). A non-universal reading with a known cause, the timescape cosmology in which
gravity makes clocks and rulers in galaxies differ from the void-dominated average, fits the DESI DR2 BAO shape much
worse than ΛCDM (problem 9). Black holes coupled to the expansion fit the expansion history nearly as well as ΛCDM,
but the growth they need conflicts with the black-hole masses measured locally (problem 10).

### 4.2 Ansatz families

Three families are implemented in the P1 pipeline: **powerlaw** (the canonical one), **transition** (a
low-redshift leg p and a five-times-larger high-redshift leg; it fails the DR1-era check outright and is kept
only as a falsified comparison branch), and **rg_profile** (identical to powerlaw at leading order).

### 4.3 What T2 predicts

- **BAO ruler shift (P1):** +0.417% relative to the ΛCDM expectation, from the drag-epoch σ ratio
  (1+z_drag)^p. The worked DR1-era check passes at z = +2.36. Testability: DESI DR2 aggregate BAO precision
  ~0.24% puts the shift at ~1.7σ; the full five-year release (~0.2%) at ~2.1σ — indicative alone, decisive
  only in combination. These estimates hold at fixed cosmological parameters. In the only coherent reading of
  the shift (masses drifting relative to the Planck mass before z ≈ 10), a joint CMB + BAO fit absorbs it into
  H₀, which falls by 0.9%, and after the refit D/r_d differs from ΛCDM by less than 0.005%
  ([analyses/joint_fit.md](analyses/joint_fit.md)). What remains distinct is early-universe gravity: 0.8% weaker
  relative to atoms at recombination and 3% at nucleosynthesis, a target for full-spectrum CMB fits and
  nucleosynthesis rather than for BAO.
- **Redshift drift (P8):** equal to ΛCDM's to within 0.03 cm/s at every registered redshift, with the same
  sign structure. The drift is a consistency test, not a discriminator.

### 4.4 Kill-test for T2

T2 falls if the registered BAO test lands outside the predicted band at more than 3σ once its forward data
arrive, or if no σ(t) ansatz compatible with the geometric lock fits late-time data.

---

## 5. T3 — mechanism hypotheses

### 5.1 Running gravitational coupling

The original mechanism proposal was renormalization-group running of the gravitational coupling G(σ), with a
rapid-growth regime near a critical scale σ_*, for example the Landau-pole form

$$G(\sigma) = \frac{G_N}{1 - (\sigma_*/\sigma)^2}.$$

This form is **retired as a derivation target**. It is the opposite of asymptotic-safety behaviour (which
exists to remove such poles), gravity at the fixed point is sector-blind and cannot import the QCD scale, and
the hadronic identification of σ_* has no derivation. It survives only as a phenomenological parametrization.

### 5.2 The status of σ_*

σ_* is an effective parameter, not a derived one. The one live derivation route is the functional
renormalization-group (FRG) **scaling-solution** programme of Wetterich and collaborators: the intrinsic scale
generated by the flow away from the fixed point is associated with the dark-energy (meV) density, not a
hadronic scale (arXiv:2407.03465). The dilaton-gravity fixed point with a field-dependent Planck mass now has
a peer-reviewed scaling solution describing inflation and late dynamical dark energy (arXiv:2512.14009, PRD 113,
106023 (2026)), and the same programme predicts the ratio of the Fermi scale to the Planck mass
(arXiv:2601.16731). Pursuing this route means computing the scaling solution for the σ sector — a specialist
calculation not attempted here.

### 5.3 Non-universal couplings and their bounds

Several proposed extensions break strict universality by coupling σ to one sector more strongly than to
others (the σ–F̃F coupling behind P4 and P5; a σ-environmental coupling behind P3). Non-universal extensions are
admissible only as separate, explicitly bounded modules:

- free-fall composition dependence: MICROSCOPE and torsion balances;
- spatial σ gradients: atomic-clock comparisons at the 10⁻¹⁸ level;
- present-day drift of G in atomic units: lunar laser ranging gives Ġ/G = (−5.0 ± 9.6)×10⁻¹⁵/yr
  (Biskupek, Müller & Torre 2021, arXiv:2012.12032); MESSENGER ranging gives |Ġ/G| < 4×10⁻¹⁴/yr
  (Genova et al. 2018). These exclude an unscreened G ∝ σ² running at the canonical p (|z| ≈ 8.2);
- high-redshift dimensionless-ratio drift: quasar absorption spectroscopy.

Every registered prediction is either consistent with strict universality or explicitly declared a bounded
non-universal extension. The surviving G(σ) region is a locally observable running G ∝ σ^{2λ} with λ ≲ 0.40,
or running whose local signature is exactly null.

### 5.4 Candidate derivations of σ_* (conjectures)

- **Non-commutative UV/IR mixing:** in non-commutative field theory, loop corrections generate an emergent
  infrared scale Λ_IR ~ 1/√(θ_NC Λ_UV²). The conjecture σ_* ≅ Λ_IR is unproven; it is falsifiable if a proper
  non-commutative gravity FRG analysis yields a σ_* incompatible with the late-time fit.
- **Holographic AdS/QCD warp factor:** identifies σ_* with the confinement scale (hierarchy G_s/G_N ~ 10¹¹ from
  a warp factor α ~ 0.5). Order-of-magnitude consistency only; not integrated with the late-time pipeline.

Both are conjectures with stated kill-tests, not derivations.

### 5.5 σ–F̃F coupling and the strong-CP problem

The structural proposal: if σ controls the displacement of the gravitational fixed point, and that fixed
point renormalizes the dimension-4 QCD topological term, σ-evolution induces a coupling
(σ/f_σ) Tr(F F̃). The effective θ would then relax dynamically, like the Peccei–Quinn mechanism but without a
separate axion field, and the photon-sector part of the same coupling predicts CMB cosmic birefringence.

Status: a structural conjecture, not a derivation. It is obstructed by de Brito, Eichhorn & Lino dos Santos
(2022) at the dimension-4 level, and the joint σ–axion window at literature couplings is excluded (Paper B
§4). The registered birefringence test P4 passes at the registered rule against the current <3σ hint; the
strong-CP bound test P5 passes. ACT DR6 reports β = 0.215° ± 0.074° (2.9σ from zero), which continues to
squeeze this module.

### 5.6 Kill-test for T3

T3 falls if all viable G(σ) profiles consistent with T2 are excluded by equivalence-principle tests,
dimensionless-constant variation (Oklo, clock comparisons of α and μ) or solar-system Ġ/G bounds, or if a
first-principles FRG derivation is incompatible with T2. The first channel has partially fired: the
unscreened G ∝ σ² running is excluded at canonical coupling (§5.3).

---

## 6. T4 — speculative extension modules

Each module has its own kill-test; the failure of one does not propagate.

### 6.1 Topological defects from σ_*-crossing

If the evolution of σ crosses σ_* at a finite rate, the crossing can act as a continuous transition that forms
defects with Kibble–Zurek density n ~ τ_quench^(−dν/(1+νz)). Proposed consequences: a cosmic-string network
with a stochastic gravitational-wave background, a distinct CMB B-mode contribution, and a dark-matter
reading of the defect tangle. **Status:** the registered spectrum test (P6) fails at the default parameters —
pulsar-timing bounds exclude a crossing scale near the GUT scale (a TeV-scale crossing is required).

### 6.2 Spatial σ(x, t) and MOND-like phenomenology

Promoting σ to a spatial field with a kinetic term gives a fifth force from ∇σ, a coherence length acting as
an effective MOND scale, cosmological evolution of that scale, and potential-depth-dependent cluster
dynamics. The registered test is P10 (energy-independent, structure-correlated TeV arrival-time dispersion).
**Status:** pending; the predicted amplitude is below current detector thresholds. The simplest evolution of
the scale, a0 proportional to the expansion rate H(z) as the coincidence a0 ≈ c H₀/2π suggests, is disfavoured by
100 rotation curves at z = 0.6–2.5 (2.8–5.4σ; OPEN_PROBLEMS.md, problem 11). Tying a0 to the dark-energy density
instead, with DESI DR2's evolving dark energy, fits the same galaxies slightly better than a constant a0 (about 2σ
at most) and predicts a0 falling to 38–78% of today's at z ≈ 3–5; registered as P15. The rotation curves published
so far at z ≈ 4.5 cannot measure a0 (analyses/a0_high_z.md). Verlinde's emergent gravity, where the extra
gravity is the dark-energy vacuum's response to matter, shows the same dark-energy pattern, but with its own scale
it predicts far more extra gravity than these galaxies show (analyses/emergent_gravity.md).

### 6.3 Information-thermodynamic readings (conjectures)

Entropic-gravity readings tie G to information density; σ̇/σ as a holographic complexity rate; cosmological
time as renormalization-group flow time (Connes' thermal time). Conceptual, not quantitative claims.

### 6.4 σ as a cosmological quantum reference frame

In the quantum-reference-frame formalism (Giacomini, Castro-Ruiz & Brukner), observables are defined relative
to the state of the observer's frame. Treating σ as such a frame would recover the geometric lock as a theorem
about invariance under frame changes. **Status:** a reformulation; the Hilbert-space construction is
outstanding.

### 6.5 GW-memory atomic-clock signature

Gravitational-wave memory from mergers could shift σ-equilibrium and hence clock frequencies, correlated across
a clock network. **Status:** the registered test (P7) is sub-threshold at present sensitivities.

### 6.6 σ-environmental neutron lifetime

The beam–trap neutron-lifetime discrepancy was once proposed as a σ-environmental effect. **Status:**
retracted. Under universal scaling the correct sensitivity is zero — the framework predicts **no** environmental
dependence (P3), and a later beam measurement using electron detection agrees with the trap values, which
points to a method-specific systematic in proton-counting beam experiments rather than to new physics.

---

## 7. The fifteen registered predictions

Each prediction is a folder under [predictions/](predictions/) with its statement, frozen pipeline output,
input data and scorecard. The live status table is [PREDICTIONS.md](PREDICTIONS.md), generated from the
register itself. The register currently has 9 active scorers.

### Prediction P1 — BAO standard-ruler shift
T2. The apparent BAO ruler is +0.417% larger than the ΛCDM expectation at the canonical p. Retrodictive
DR1-era check: PASS (z = +2.36). Forward target: the full five-year DESI release. Its only coherent reading is
absorbed into H₀ in a joint CMB + BAO fit, so the registered statistic cannot distinguish it (open problem 1).
[predictions/P01_bao_ruler_shift/](predictions/P01_bao_ruler_shift/)

### Prediction P2 — 21cm Cosmic-Dawn signal
T2/T3. A parametric deepening of the z ≈ 17 absorption trough. Forward target: HERA Phase II and SKA-Low. The
amplification factor used by the pipeline is not derived (open problem 3).
[predictions/P02_21cm_cosmic_dawn/](predictions/P02_21cm_cosmic_dawn/)

### Prediction P3 — Neutron-lifetime environmental dependence
T4. Universal scaling predicts no beam–trap effect; the non-universal explanation is retracted. Scored FAIL for
the anomaly explanation. [predictions/P03_neutron_lifetime/](predictions/P03_neutron_lifetime/)

### Prediction P4 — CMB cosmic birefringence
T3. Birefringence from the σ–F̃F coupling. PASS at the registered rule against the current <3σ hint; the module
is otherwise under strong pressure (§5.5). [predictions/P04_cmb_birefringence/](predictions/P04_cmb_birefringence/)

### Prediction P5 — Strong-CP θ-bound consistency
T3. The σ–θ coupling stays within neutron-EDM bounds. PASS.
[predictions/P05_strong_cp_bound/](predictions/P05_strong_cp_bound/)

### Prediction P6 — Kibble–Zurek defect spectrum
T4. Gravitational-wave background from σ_*-crossing defects. FAIL at default parameters (pulsar-timing bounds).
[predictions/P06_kz_defect_spectrum/](predictions/P06_kz_defect_spectrum/)

### Prediction P7 — GW-memory atomic-clock signature
T4. Correlated clock shifts after merger events. SUB-THRESHOLD.
[predictions/P07_gw_memory_clocks/](predictions/P07_gw_memory_clocks/)

### Prediction P8 — Redshift drift
T2, supporting. Equal to ΛCDM's drift to 0.03 cm/s with the same sign structure (revision r2; the earlier
revision, computed with a coasting toy history, is superseded and kept for provenance). Forward target:
ELT/ANDES. [predictions/P08_redshift_drift/](predictions/P08_redshift_drift/)

### Prediction P9 — Constancy of μ = m_p/m_e
T1 exact null. PASS at current bounds (partly by construction; see the register entry).
[predictions/P09_proton_electron_mass_ratio/](predictions/P09_proton_electron_mass_ratio/)

### Prediction P10 — TeV blazar arrival-time dispersion
T4. Energy-independent, structure-correlated dispersion from σ(x) gradients. Forward target: CTAO. Pending.
[predictions/P10_tev_blazar_dispersion/](predictions/P10_tev_blazar_dispersion/)

### Prediction P11 — Distance duality η(z) = 1
T1 exact null. Current DDR constraint η₁ = 0.023 ± 0.027 → PASS (z = +0.85). Sudden-death channel K1.
[predictions/P11_distance_duality/](predictions/P11_distance_duality/)

### Prediction P12 — Nuclear–electronic clock-ratio null
T1 exact null in the hadronic sector: d ln(ν_Th/ν_Sr)/dt = 0. Anchor ratio 4.707072615078(18); measured
α-sensitivity K = 5900(2300). A genuine forward registration (one epoch existed at registration).
Sudden-death channel K2. [predictions/P12_nuclear_clock_ratio/](predictions/P12_nuclear_clock_ratio/)

### Prediction P13 — GW–EM luminosity-distance duality Ξ₀ = 1
T1 exact null in the tensor sector. GWTC-4.0 gives Ξ₀ = 1.2 +0.8/−0.4 → PASS (z = +0.5). Sudden-death channel
K1. [predictions/P13_gw_em_duality/](predictions/P13_gw_em_duality/)

### Prediction P14 — Early-universe gravity weaker relative to atoms
T2, the coherent reading of the canonical exponent (registered in v20.1 under K0.3). Gravity in atomic units is
0.8% weaker than today's at recombination and 3.0% weaker at nucleosynthesis, exactly unchanged below z = 10, with
ln(G_BBN/G₀) = 3.80 × ln(G_rec/G₀). Awaiting data precise enough to tell it from G = G₀. If it fails, K0.4 applies.
Data published before the registration (not scored): helium puts it 1.4σ away and G = G₀ 0.8σ. Deuterium depends on
nuclear rates that are not settled; with it, P14 is 1.3σ away with one rate set and 2.7–3.0σ with the other
([analyses/p14_bbn_status.md](analyses/p14_bbn_status.md)).
[predictions/P14_early_gravity/](predictions/P14_early_gravity/)

### Prediction P15 — Milgrom's acceleration scale follows the dark-energy density
T4 (§6.2, registered in v20.2). The scale at which galaxies show dark matter follows the square root of the
dark-energy density, with DESI DR2's dark energy: a0 at z = 3 is 0.74 (0.63–0.78) of today's, 0.57 (0.38–0.63) at
z = 5. Suggested by the RC100 rotation curves, which cannot score it; contradicted by the one sample in which a0
rises (OPEN_PROBLEMS.md, problem 11). Forward target: rotation curves at z ≥ 2.
[predictions/P15_a0_dark_energy/](predictions/P15_a0_dark_energy/)

---

## 8. Kill conditions (pre-committed)

A tiered hierarchy can degenerate into unfalsifiability if every failure is absorbed by demoting a module or
adding a bespoke extension. These conditions sit above the tiers and are part of the pre-registration.

*Frozen register records written before the reorganization refer to these conditions by their old section
numbers: §12.2.1 = K0, §12.2.1a = K1, §12.2.1b = K2 (see [METHOD.md](METHOD.md)).*

### K0 — Majority rule over forward tests

1. **Scope.** Only genuinely forward tests count — those registered before their data exist: P2, P8, P10, P12,
   and the full-survey DESI BAO test of P1. Retrodictive checks do not count.
2. **Threshold.** If at least three of these five fail at their registered confidence, the GSC core (T1–T3) is
   abandoned as a distinct theory, not just the implicated modules. The condition fires as soon as three have
   failed; passing tests never veto a kill.
3. **No post-hoc rescue.** A registered prediction may not be saved by a new tier demotion, a new non-universal
   extension, or an unimplemented correction. Such mechanisms count only if registered and scored as new
   forward predictions.
4. **Conformal-reduction clause.** If the surviving content of GSC becomes observationally indistinguishable
   from ΛCDM, GSC is falsified *as a distinct theory*, however many ΛCDM-equivalent fits it still produces.

Note: P8 can fail only if ΛCDM-class kinematics fail, so it contributes no framework-specific failure mode. The
scope and the threshold are left unchanged rather than re-tuned, and this loss of framework-specific forward
content is recorded openly. P1's statistic turned out to be unable to distinguish its only coherent reading from
ΛCDM (OPEN_PROBLEMS.md, problem 1); the early-universe content of that reading was registered under clause 3 as
P14, whose own registration adds: if P14 fails, clause 4 applies.

### K1 — Duality sudden-death (photon and tensor sectors)

A single robust violation of distance duality falsifies T1 outright (P11), and so does a single robust
Ξ₀ ≠ 1 in gravitational-wave sirens (P13). "Robust" means all three of: ≥ 3σ; stable under calibration
choices (supernova calibration; galaxy-catalogue and population models for sirens); present in
model-independent or independently reproduced analyses. No demotion, extension or correction may be invoked.

### K2 — Local-invariance sudden-death

The geometric lock is the framework's load-bearing wall. A robust detection of any of the following
falsifies T1 outright:

- a nonzero local Ġ/G in orbital-versus-atomic comparisons (current bounds in §5.3; BepiColombo and
  next-generation lunar retroreflectors tighten them);
- a secular drift of any local clock ratio: electronic (d ln α/dt = 1.8(2.5)×10⁻¹⁹/yr, Filzinger et al. 2023),
  mass ratio μ (P9), or nuclear/electronic (P12).

"Robust" carries the same three-part qualifier as K1. The registered value at every instrument in this family
is exactly zero.

Each of K1 and K2 only adds ways for the framework to die; neither removes any.

---

## 9. Limitations

These are not solved and must not be claimed:

- **Coherence of the T2 deviation.** See [OPEN_PROBLEMS.md](OPEN_PROBLEMS.md): which sector carries p, and
  what that implies for P1, P2, P8 and the local null.
- **σ_* derivation.** Effectively phenomenological; the FRG scaling-solution route is the only live one (§5.2).
- **Conformal triviality.** The framework is distinct from ΛCDM only if σ has independent dynamics; if every
  demonstration of that fails, kill condition K0.4 applies.
- **CMB.** Only compressed distance priors are used; there is no full temperature/polarization likelihood.
- **Perturbations.** Linear growth only; no nonlinear structure formation or full Boltzmann treatment.
- **σ–F̃F coupling, defect dark matter, quantum reference frames.** Structural arguments without the required
  calculations (§5.5, §6).
- **Signing.** The register is content-hashed and git-timestamped; cryptographic (GPG) signing is specified but
  not yet executed ([METHOD.md](METHOD.md)).

---

## 10. References

- Wetterich, C. *A Universe without expansion.* arXiv:1303.6878 (2013).
- Wetterich, C. *Dark energy evolution from quantum gravity.* arXiv:2407.03465 (2024).
- Maitiniyazi, Y., Wetterich, C. & Yamada, M. *Scaling solutions for gauge invariant flow equations in dilaton
  quantum gravity.* PRD 113, 106023 (2026), arXiv:2512.14009.
- Wetterich, C. *Fermi scale from quantum gravity scaling solution.* arXiv:2601.16731 (2026).
- Canuto, V. M., Adams, P. J., Hsieh, S.-H. & Tsiang, E. *Scale-covariant theory of gravitation and
  astrophysical applications.* Phys. Rev. D 16, 1643 (1977).
- de Brito, G. P., Eichhorn, A. & Lino dos Santos, R. R. (2022), weak-gravity bound on gravity-induced
  photon couplings (see Paper B §3.2.1 for the full citation).
- Biskupek, L., Müller, J. & Torre, J.-M. *Benefit of new high-precision LLR data for the determination of
  relativistic parameters.* arXiv:2012.12032.
- Genova, A. et al. *Solar system expansion and strong equivalence principle as seen by the NASA MESSENGER
  mission.* Nat. Commun. 9, 289 (2018).
- Filzinger, M. et al. PRL 130, 253001 (2023).
- Zhang, C. et al. *Frequency ratio of the ²²⁹ᵐTh nuclear isomeric transition and the ⁸⁷Sr atomic clock.*
  Nature 633, 63 (2024), arXiv:2406.18719.
- Beeks, K. et al. *Fine-structure constant sensitivity of the Th-229 nuclear clock transition.*
  arXiv:2407.17300.
- LIGO–Virgo–KAGRA. *GWTC-4.0: Constraints on the cosmic expansion rate and modified gravitational-wave
  propagation.* arXiv:2509.04348.
- Reuter, M. & Saueressig, F. *Quantum gravity and the functional renormalization group.* Cambridge UP.
- Giacomini, F., Castro-Ruiz, E. & Brukner, Č. arXiv:1712.07207.
- Minwalla, S., Van Raamsdonk, M. & Seiberg, N. JHEP 02, 020 (2000).
- Kibble, T. W. B. J. Phys. A 9, 1387 (1976); Zurek, W. H. Nature 317, 505 (1985).
- Minami, Y. & Komatsu, E. PRL 125, 221301 (2020).

Further references with verification provenance: [docs/observational_frontier_2026.md](docs/observational_frontier_2026.md).
