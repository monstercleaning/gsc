# Reviewer FAQ (Referee Pack): the current framework late-time (Option 2)

This FAQ is a **referee-pack aid**: short answers with pointers to the paper and canonical docs.

It is **not part of the paper PDF** and is **not included** in the submission bundle builder.

---

## Scope quick answers (external review themes)

## Q0a) "Do you run the full peak-level CMB module today?"

A: No. the current framework uses compressed priors (distance priors / shift parameters) in
the Phase-2 bridge. This is diagnostic-only and not a full spectra fit
(`TT/TE/EE`, peak-level Boltzmann path) in canonical scope.
Pointers: `docs/early_time_e2_status.md`;
`docs/project_status_and_roadmap.md`.

## Q0b) "Is `sigma(t)` derived from FRG/asymptotic safety?"

A: No. Current FRG/AS usage is conceptual motivation only. The `k(sigma)` map
is treated as an ansatz-level modeling choice and remains an explicit open
problem.
Pointers: `docs/sigma_field_origin_status.md`;
`docs/rg_asymptotic_safety_bridge.md`.

## Q0c) "Do you claim dark matter is solved?"

A: No. The structure module is a linear-theory/approximate diagnostic channel
and does not claim dark-matter resolution.
Pointers: `docs/structure_formation_status.md`;
`docs/external_reviewer_feedback.md`.

## Q0d) "Do you match full Planck CMB spectra?"

A: No. Current canonical Phase-2 bridge uses compressed/shift-parameter style
constraints and distance-priors diagnostics. Full TT/TE/EE peak-level spectra
fitting is future work.
Pointers: `docs/early_time_e2_status.md`;
`docs/project_status_and_roadmap.md`.

## Q0e) "Do you claim CDM replacement in this release?"

A: No. We do not claim dark matter is solved or replaced. Current
structure-formation checks are linear-growth and `fσ8`/RSD diagnostic overlays;
dark-matter microphysics stance remains open in roadmap scope.
Pointers: `docs/structure_formation_status.md`;
`docs/perturbations_and_dm_scope.md`;
`docs/project_status_and_roadmap.md`.

---

## Q1) "Isn't this just a conformal frame redefinition / Wetterich redux?"

A: The conformal map itself is a variable change; by itself it is not new physics. The v11.0.0+
Phase-4 claim is operational and inference-level: we commit to an explicit **measurement model**
and evaluate epsilon/cross-probe consistency diagnostics under Roadmap v2.8. Redshift drift remains
in use as supporting no-go evidence for specific history classes and as historical motivation.
Pointers: paper `GSC_Framework_v10_1_FINAL.md` ("1.2 Relationship to Wetterich (2013)" and
"8. Redshift drift (historical; deprecated as primary)" for historical context);
`docs/measurement_model.md`; `docs/risk_register.md`.

## Q1b) "Does redshift drift discriminate frames?"

A: No. Sandage-Loeb `dz/dt0 = H0(1+z) - H(z)` is kinematic and frame-agnostic at this level.
What it discriminates observationally is the adopted history `H(z)`. In practice we test whether the
specific GSC toy histories used in the run imply a different drift sign than a ΛCDM history in `z~2-5`.
Pointers: paper `GSC_Framework_v10_1_FINAL.md` ("8.1 Definition", "8.3 GSC v10");
`gsc/measurement_model.py` (`z_dot_sandage_loeb` docstring).

## Q1c) "So what exactly is falsifiable?"

A: In current Roadmap v2.8 framing, the primary falsifiable channel is measurement-model epsilon
inference and cross-probe consistency triangles under explicit assumptions. Drift-sign remains a
supporting history-vs-history no-go diagnostic (`dz/dt0 = H0(1+z) - H(z)`) for specific late-time
history classes. If `H(z)` is matched to ΛCDM, drift is degenerate between frame labels at this level.
Pointers: `docs/risk_register.md`; `docs/measurement_model.md`; paper
`GSC_Framework_v10_1_FINAL.md` ("Scope, Claims, and Kill Tests", Sec. 8; historical framing).

## Q1d) "In asymptotic safety the running is with momentum scale `k`. How do you identify `k` with `sigma(t)`?"

A: In the current framework this is a working identification (ansatz), not a FRG derivation. The motivation is that
the relevant bound-system internal scale tracks `sigma`, so the effective running can be parameterized
as `k = k(sigma)` (often using a `k ∝ 1/sigma` form up to model-dependent factors). We treat that map as
phenomenological and keep its first-principles derivation as an open problem for future work. Observational
discriminants in the current release remain phrased through explicit history comparisons `H(z)` rather than
through frame labels alone.
Pointers: `docs/rg_scale_identification.md`; paper `GSC_Framework_v10_1_FINAL.md` (Sec. 4, Sec. 8).

## Q1e) "Is your running `G(k)` derived from asymptotic safety / FRG?"

A: No. In the current framework asymptotic safety / FRG is conceptual motivation, not a derivation claim. The
implemented `G(k)` form is a minimal phenomenological ansatz, and the `k(sigma)` identification is
treated as non-trivial and not derived in the current release. A first-principles bridge is kept as
an explicit open problem.
Pointers: `docs/rg_asymptotic_safety_bridge.md`; `docs/rg_scale_identification.md`;
`docs/project_status_and_roadmap.md`.

## Q2) "Is this tired light?"

A: No. Tired-light analogies fail classic expansion tests (SN time dilation, Tolman dimming, etc.).
The late-time mapping here preserves **(1+z)** time dilation and **Tolman (1+z)^-4** dimming under
photon number conservation along null geodesics (within the stated working hypotheses).
Pointers: paper `GSC_Framework_v10_1_FINAL.md` ("3.4 Classic expansion tests retained");
`docs/measurement_model.md` (light propagation assumptions).

## Q3) "Why is the redshift drift formula applicable in your measurement model?"

A: Redshift drift is defined as an **observable** `dz/dt0` measured by a local observer over time.
The analysis uses the standard kinematic Sandage-Loeb relation for an FLRW description and then
evaluates it under the late-time history `H(z)` used in the harness; the measurement-model role is to
state what `z` and `t0` mean operationally in the freeze-frame mapping, not to invent a new drift formula.
Pointers: paper `GSC_Framework_v10_1_FINAL.md` ("8.1 Definition"); `docs/measurement_model.md`;
code/test: `gsc/measurement_model.py` and `tests/test_history_gsc.py`.

## Q4) "Energy conservation claims / 'LambdaCDM violates energy'?"

A: The paper does **not** argue that LCDM is wrong because it "violates energy conservation." In
time-dependent cosmological backgrounds, a single global conserved energy is not generally defined
without a global timelike Killing symmetry (this is a symmetry statement, not an inconsistency of GR).
GSC highlights that in the freeze frame a conserved Noether energy can be defined, which is an accounting
advantage, not a falsifier.
Pointers: paper `GSC_Framework_v10_1_FINAL.md` ("6. Global Energy Bookkeeping and Noether Charge").

## Q5) "What about varying constants / dotG/G / WEP constraints?"

A: Under the **universal scaling** postulate used in the current framework, local **dimensionless** ratios are invariant,
so local clock/Oklo/WEP-style tests are targeted to be null in that limit. Any **non-universal** corrections
would generically show up as drift in dimensionless quantities and are therefore strongly constrained; such
corrections are treated as mandatory future consistency checks rather than being assumed away.
Pointers: paper `GSC_Framework_v10_1_FINAL.md` ("5.5 Oklo..."); `docs/measurement_model.md`;
referee-pack: `docs/risk_register.md`.

## Q5b) "Why must universality be exact? How small is 'small'?"

A: Because the strongest constraints are on **dimensionless** drifts (clock ratios, WEP composition dependence).
One way to see the scale is to parameterize departures as small differential scalings between an EM/leptonic
scale and a hadronic/nuclear scale: `m_e ∝ σ^(-1-ε_EM)`, `m_p ∝ σ^(-1-ε_QCD)`, so
`d ln μ / dt = (ε_EM - ε_QCD) H_σ` for `μ ≡ m_p/m_e`. Then generically:
`d/dt ln(ν_A/ν_B) = K_α d ln α/dt + K_μ d ln μ/dt + …`, and at the present epoch `H_σ(t0)=H0 ≈ 7×10^-11 yr^-1`.
So even `|ε_EM-ε_QCD| ~ 10^-7` gives an `O(10^-17 yr^-1)` drift in `ln μ` before `K` factors. In the current framework we
set `ε_EM=ε_QCD=0` (strict universality); nonzero `ε` is an explicit risk parameterization for v10+ extensions,
not a core claim.
Pointers: paper `GSC_Framework_v10_1_FINAL.md` (Sec. 5.6 risk model); `docs/precision_constraints_translator.md` (worked examples in Sec. 4).

## Q6) "What about SN standard candle physics under varying masses?"

A: the current framework does not claim a first-principles SN luminosity evolution model. In the late-time harness, the SN
absolute magnitude offset is treated as a nuisance (`Delta M`, profiled), and core inferences are framed
around measurement-model epsilon inference and cross-probe consistency diagnostics rather than SN astrophysics.
Drift remains supporting no-go evidence, not the primary discriminator.
Pointers: `docs/reproducibility.md` (SN nuisance handling); paper `GSC_Framework_v10_1_FINAL.md`
(scope statements + historical drift focus); `docs/risk_register.md`.

## Q6b) "Do you assume Etherington reciprocity (distance duality)? Can you test it?"

A: Late-time the current framework treats distance duality as a **working hypothesis** (not a derived claim) under the stated
light-propagation assumptions. As an opt-in diagnostic, we also parameterize deviations via a single
`epsilon_dd` and fit it from SN+BAO consistency (profiling `Delta M` and `r_d` nuisances).
Pointers: `docs/distance_duality.md`; script: `scripts/distance_duality_diagnostic.py`.

## Q7) "How do you evade atomic clock / Oklo constraints?"

A: the current framework does not “evade” them; it makes a sharp **null prediction** in the strict universal-scaling limit:
purely local **dimensionless** ratios (clock comparisons, Oklo resonance conditions expressed as dimensionless
combinations, etc.) do not drift. Any non-universal correction would be strongly constrained and must be
modeled explicitly (it is not part of the the current framework canonical claims).
Pointers: `docs/precision_constraints_translator.md` (worked examples Sec. 4; baseline `ε_EM=ε_QCD=0`); `docs/measurement_model.md`.

## Q8) "Does v10 predict WEP violation?"

A: In the ideal the current framework universal-scaling limit, no: there is no composition-dependent scaling, so WEP tests
are a null prediction. If universality is relaxed in a future extension, WEP/MICROSCOPE constraints become a
primary kill-test and must be included explicitly.
Pointers: `docs/precision_constraints_translator.md`; referee-pack: `docs/risk_register.md`.

## Q9) "What about CMB / early universe?"

A: The canonical the current framework late-time release is explicitly late-time only. Early-universe closure (including
full TT/TE/EE peak-level CMB spectra, recombination microphysics, and transfer-function fidelity) is deferred
and introduced only through **opt-in bridge** layers with their own tags/releases and diagnostics.
For Phase-2 E2, the CMB-facing module is a **compressed priors diagnostic** path; it is not a full
power-spectrum or peak-level treatment.
Pointers: `docs/early_time_bridge.md`; `docs/project_scope.md`;
`docs/project_status_and_roadmap.md`; tags documented in `README.md`.

## Q9b) "If CMB is out of scope, did you at least quantify what closure would require?"

A: Yes, diagnostically. We provide a compact “closure requirements / no-go” map that translates
non-degenerate bridge `dm_fit` targets into an effective high-z `A_required` and shows how the required
deformation scales with repair start redshift. In the tested families, delaying repair start to `z~10+`
while preserving the drift window is a practical no-go. This is explicitly diagnostic (not a core claim).
Pointers: `docs/early_time_e2_synthesis.md`; `docs/early_time_e2_closure_requirements.md`; tooling:
`scripts/cmb_e2_closure_requirements_plot.py`.

## Q9c) "Where is the consolidated diagnostic evidence pack?"

A: Use the diagnostics index; it maps each module to release tag, asset ZIP, SHA256, reproduce command,
and output directory from one place. This keeps submission scope unchanged while making all bridge diagnostics
auditable.
Pointer: `docs/diagnostics_index.md`.

## Q9d) "What is the shortest E2 summary I can read first?"

A: Start with the E2 synthesis note (single verdict + decision tree), then use the diagnostics index
for module-level artifacts/checksums/reproduce commands.
Pointers: `docs/early_time_e2_synthesis.md`; `docs/diagnostics_index.md`.
Current status under tested assumptions: no region with both `drift_sign_ok=True` in `z~2-5`
and strict no-fudge CHW2018 `chi2_cmb~O(1)` (see WS14/WS15 notes).

## Q9e) "Did you quantify a parameterization-light bound between drift and CMB closure?"

A: Yes. We added a drift-constrained Pareto diagnostic that deforms only the drift window toward the
`H(z)=H0(1+z)` boundary and reports strict CHW2018 chi2 vs `Delta v(z=4,10y)`. In the tested setup,
chi2 remains very large even as drift approaches `0+`, so this acts as a no-go indicator under those
assumptions (diagnostic-only, not a core claim).
Pointers: `docs/early_time_e2_drift_constrained_bound.md`; script:
`scripts/cmb_e2_drift_constrained_closure_bound.py`.

## Q9f) "How large is the implied early-time deformation in physical terms?"

A: We translate WS13 closure targets into effective knob scales via `deltaG = A^2 - 1` (equivalently
`delta rho/rho = A^2 - 1`). Representative medians are `deltaG~0.42` for `z_start=5` and `~0.67` for
`z_start=10` in the tested target set. This is an interpretation map for E2 planning, not a microphysical model.
Pointers: `docs/early_time_e2_closure_to_physical_knobs.md`; script:
`scripts/cmb_e2_closure_to_physical_knobs.py`.

## Q9g) "Does CMB already falsify GSC?"

A: Not as a submission-scope claim. The reviewer-safe interpretation is:

- We do **not** claim a full CMB power-spectrum/peak-level fit in the current framework.
- Phase-2 E2 uses compressed priors as a diagnostic pathway.
- Under tested families/knobs and filters, we do not find a joint region that simultaneously keeps
  the drift-sign target in `z~2-5` and reaches strict compressed-priors closure.
- This is reported as an open early-time closure problem, not as a solved/closed module.

Reproducible evidence path (bundle workflow):
- produce bundle outputs with `scripts/phase2_e2_bundle.py`
- verify with `scripts/phase2_e2_verify_bundle.py`
- inspect deterministic paper assets/snippets from `scripts/phase2_e2_make_paper_assets.py`
- consolidated operational context: `docs/early_time_e2_status.md`

## Q10) "What is the current dark-matter stance in GSC?"

A: The current baseline keeps the standard matter budget in practical use (`Omega_m` interpreted in the usual way for background diagnostics). The present release does not claim dark-matter removal or that dark matter is no longer needed. The structure module added in this phase is diagnostic scaffolding and does not change that stance.
Pointers: `docs/structure_formation_status.md`; `docs/project_status_and_roadmap.md`;
`docs/perturbations_and_dm_scope.md`;
`GSC_Framework_v10_1_FINAL.md` (Open Problems / roadmap scope).

## Q10b) "Do you already provide full structure-formation predictions?"

A: Not yet. Current coverage is approximation-first: BBKS transfer-function diagnostics and GR-baseline linear growth (`D`, `f`, `g=fD`, optional `fσ8` amplitude profiling) driven by explicit `H(z)` backgrounds. Full perturbations, Boltzmann hierarchy, and survey-level LSS likelihoods remain deferred.
Pointers: `docs/structure_formation_status.md`; `scripts/phase2_sf_structure_report.py`; `scripts/phase2_sf_fsigma8_report.py`.

## Q10c) "Do you now claim structure-growth closure from `A_s` to `fσ8`?"

A: No. The current bridge provides a baseline linear-theory diagnostic (`A_s,n_s -> P(k) -> sigma8 -> fσ8`) under explicit approximations (BBKS transfer + GR linear growth over a chosen `H(z)` history). It is useful for consistency checks and controlled comparisons, but it is not a full perturbation/Boltzmann treatment and does not by itself resolve dark-matter or full LSS closure claims.
Pointers: `docs/structure_formation_status.md`; `scripts/phase2_sf_fsigma8_report.py`; `gsc/structure/power_spectrum_linear.py`.

## Q10d) "Do you already fit RSD `fσ8` as a primary cosmology constraint?"

A: We provide an RSD `fσ8` diagnostic layer (including diagonal-variance chi2 and analytic `sigma8` amplitude profiling), but we do not present it as a full survey-level structure-formation fit. The implementation is a claim-safe baseline (GR linear growth + approximation-first transfer/AP handling), intended for consistency monitoring and stress tests rather than final perturbation closure claims.
Pointers: `scripts/phase2_sf_fsigma8_report.py`; `data/structure/fsigma8_gold2017_plus_zhao2018.csv`; `docs/structure_formation_status.md`.

## Q10e) "Does Phase-2 E2 now include structure-formation information?"

A: Yes, as an additive diagnostic overlay only. The Phase-2 best-candidates report can attach an RSD `fσ8` chi2 block (`chi2_rsd`, profiled `sigma8_0`, and `chi2_total_plus_rsd`) for top candidates and emits a paper snippet summary. This is still a linear-GR diagnostic under explicit assumptions, not a full perturbation-theory closure or a dark-matter-removal claim.
Pointers: `scripts/phase2_e2_best_candidates_report.py`; `scripts/phase2_e2_make_paper_assets.py`; `docs/structure_formation_status.md`.

## Q10f) "Which transfer function is used for linear `P(k)`/`sigma8` estimates?"

A: The default backend is BBKS. We also provide an optional Eisenstein-Hu 1998 no-wiggle backend (`eh98_nowiggle`) for smooth baryon-suppressed transfer estimates. Both are approximation-first diagnostics and are not Boltzmann-solver equivalents (no CAMB/CLASS claim in this release).
Pointers: `gsc/structure/transfer_bbks.py`; `gsc/structure/transfer_eh98.py`; `scripts/phase2_sf_fsigma8_report.py`; `docs/structure_formation_status.md`.

## Q10g) "What is the status of structure-formation tests right now?"

A: Current coverage is diagnostic linear theory only: transfer approximation (BBKS/EH98 no-wiggle), linear growth (`D,f`), and optional RSD `fσ8` overlay for consistency checks. This is not a full perturbation-theory closure and not a survey-complete LSS likelihood result.
Pointers: `docs/structure_formation_status.md`; `docs/project_status_and_roadmap.md`;
`scripts/phase2_sf_fsigma8_report.py`; `scripts/phase2_e2_pareto_report.py`.

## Q10h) "Do you now provide joint CMB+RSD candidate selection in Phase-2?"

A: Yes, as an additive diagnostic ranking layer. `phase2_e2_best_candidates_report.py` now supports
explicit ranking modes for CMB-only and joint CMB+RSD (`chi2_total + chi2_rsd`) over eligible E2
candidates. This is operational triage/reporting for scanned points and does not change scan physics.
Pointers: `scripts/phase2_e2_best_candidates_report.py`;
`docs/early_time_e2_status.md`; `docs/structure_formation_status.md`.

## Q10i) "What remains out of scope after this joint ranking update?"

A: Three boundaries remain explicit:

- full CMB anisotropy spectra fitting (TT/TE/EE peaks) is not in canonical the current framework scope; current CMB bridge remains compressed-priors diagnostic-only;
- `k(sigma)` / `sigma(t)` is still phenomenological (no first-principles FRG derivation claim);
- dark matter is not claimed as solved/eliminated; current structure layer is linear-theory diagnostic.

Pointers: `docs/project_status_and_roadmap.md`; `docs/structure_formation_status.md`.

## Q10j) "Are primordial tilt (`n_s`) and pivot now explicit in structure diagnostics?"

A: Yes, in the linear diagnostic layer only. The structure report and `sigma8-from-As`
helpers expose explicit `n_s` and `k_pivot` knobs so assumptions are auditable instead
of implicit. This is still an approximation-first bridge and not a full Boltzmann
perturbation pipeline.
Pointers: `scripts/phase2_sf_fsigma8_report.py`;
`gsc/structure/power_spectrum_linear.py`;
`docs/structure_formation_status.md`.

## Q10k) "Is `sigma(t)` now derived from FRG / asymptotic safety?"

A: No. Current release status remains: FRG/asymptotic-safety references are conceptual
motivation, while the operational `k(sigma)` mapping is treated as a working ansatz.
Derivation-level support is deferred roadmap work.
Pointers: `docs/sigma_field_origin_status.md`;
`docs/rg_scale_identification.md`;
`docs/project_status_and_roadmap.md`.

## Q10l) "What did you add for FRG inputs if derivation is still deferred?"

A: We added a deterministic ingestion scaffold for external FRG flow tables
(`k,g` CSV in, stable summary out) to make comparisons reproducible while
keeping claims scoped. This interface is diagnostic-only and keeps
`k(sigma)` as ansatz-level in the current release.
Pointers: `scripts/phase2_rg_flow_table_report.py`;
`gsc/rg/flow_table.py`;
`docs/sigma_field_origin_status.md`.
