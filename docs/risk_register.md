# Risk Register (Referee Pack): the current framework late-time (Option 2)

This document is a **referee-pack aid**: a short list of decisive falsifiers, high-risk assumptions,
and where the corresponding guardrails live in the repository.

It is **not part of the paper PDF** and is **not included** in the submission bundle builder.

Recommended reading order for E2 risk context:

- `docs/early_time_e2_synthesis.md` (referee verdict + decision tree)
- `docs/early_time_e2_executive_summary.md` (short findings)
- `docs/early_time_e2_closure_requirements.md` (quantitative no-go/requirements map)
- `docs/early_time_e2_drift_constrained_bound.md` (WS14 Pareto bound)
- `docs/early_time_e2_closure_to_physical_knobs.md` (WS15 effective `deltaG` scale map)

---

## Kill Tests / Decisive Falsifiers

| Test | What would falsify | Why decisive | Where in repo |
|---|---|---|---|
| Epsilon measurement-model inference + cross-probe consistency triangles (primary Roadmap v2.8 discriminator) | If joint/paired probe inference requires incompatible `epsilon` sectors or fails consistency triangles under explicit coupling assumptions | Current Phase-4 pivot treats inference-level `epsilon` consistency as the primary discriminator, because it compares probe families under one measurement-model layer and explicit assumptions. | Roadmap: `docs/GSC_Consolidated_Roadmap_v2.8.md`; readiness docs: `docs/EPSILON_FRAMEWORK_READINESS.md`; scripts: `scripts/phase4_epsilon_translator_mvp.py`, `scripts/phase4_epsilon_sensitivity_matrix_toy.py`, `scripts/phase4_pantheon_plus_epsilon_posterior.py` |
| Redshift drift sign at high redshift (`z >= 2`) (supporting no-go diagnostic) | A robust measurement of **negative** `dz/dt0` in the quasar range (e.g. `z ~ 2-5`) | The core late-time toy histories used in the current framework are constructed to satisfy `H(z) < H0(1+z)` in the quasar range and thus predict **positive drift** there. In Phase-4 this remains supporting no-go evidence, not the primary project discriminator. | Paper (historical framing): `GSC_Framework_v10_1_FINAL.md` ("8. Redshift drift (historical; deprecated as primary)"); code: `gsc/measurement_model.py` (`z_dot_sandage_loeb`); tests: `tests/test_history_gsc.py`; helper: `scripts/redshift_drift_table.py`; diagnostic: `scripts/phase4_sigmatensor_drift_sign_diagnostic.py` |
| Local metrology: secular drift in **dimensionless** ratios | Credible detection of secular drift in dimensionless ratios (e.g. `alpha`, mass ratios, clock ratios) beyond SM/GR systematics | Universal scaling is the axiom that protects local experiments (null drift for dimensionless ratios). Non-universal drift is strongly constrained; a verified drift would directly violate the axioms used in v10 late-time measurement translation. **If universality is violated, the Option-2 program fails.** A convenient risk parameterization is to allow small differential scalings between EM/leptonic and hadronic/nuclear sectors, e.g. `m_e ∝ σ^(-1-ε_EM)`, `m_p ∝ σ^(-1-ε_QCD)` (paper Sec. 5.6); in the current framework we set `ε_EM=ε_QCD=0`. | Paper: `GSC_Framework_v10_1_FINAL.md` (Sec. 5.6 + "Oklo..."); spec: `docs/measurement_model.md`; translator: `docs/precision_constraints_translator.md` (worked examples Sec. 4); lock-tests: `tests/test_measurement_model_null_predictions.py` |

---

## High-Risk Assumptions (And Minimization Strategy)

| Assumption | Risk | Mitigation / Scope control | Where in repo |
|---|---|---|---|
| Strict universality (`ε_EM=ε_QCD=0`) | If any sector-dependent / non-universal correction is needed, it is immediately exposed to the strongest precision constraints (clock ratios, Oklo, WEP). This is a genuine “project-killer” risk. | the current framework treats universality as a **required symmetry** (not an optional assumption) and keeps departures fixed to zero in canonical claims. A future extension must introduce non-universality explicitly via `ε`-type parameters and confront the precision-constraint bounds; order-of-magnitude translations are documented. | Paper: `GSC_Framework_v10_1_FINAL.md` (Sec. 5.6 risk model); translator: `docs/precision_constraints_translator.md` (worked examples Sec. 4); lock-tests: `tests/test_measurement_model_null_predictions.py` |
| Etherington reciprocity (distance duality) as a working hypothesis for late time | If reciprocity fails (beyond known astrophysical systematics), the specific late-time light propagation mapping used here would need revision | Treated explicitly as a **working hypothesis** for the the current framework late-time release; not claimed as a new derivation. A diagnostic module parameterizes deviations via `epsilon_dd` and fits it from SN+BAO consistency (opt-in). | Spec: `docs/measurement_model.md` (Etherington); paper: `GSC_Framework_v10_1_FINAL.md` ("3.4 Classic expansion tests retained"); diagnostic: `docs/distance_duality.md` + `scripts/distance_duality_diagnostic.py` |
| SN absolute luminosity is a nuisance (`Delta M`), not first-principles | Any real luminosity evolution can bias inference if mis-modeled | Policy in the current framework: do **not** claim a first-principles SN luminosity model; treat `Delta M` as nuisance and keep conclusions focused on drift + kinematic consistency. | Repro doc: `docs/reproducibility.md` (SN nuisance handling); code: `scripts/late_time_fit_grid.py` (profiles `Delta M`) |
| BAO `r_d` is a nuisance in the late-time harness | If early-time physics differs, `r_d` inferred from CMB can shift; late-time-only closure is incomplete | Policy in the current framework late-time: keep `r_d` as profiled nuisance ("late-time safe"); early-time derivation is deferred to explicit bridge work (separate tags/releases). | Repro doc: `docs/reproducibility.md` ("BAO r_d modes"); bridge spec: `docs/early_time_bridge.md` |
| E2 closure start too high (`z_boost_start >> 5`) | Delaying repair to high z leaves too little integral lever-arm, so required deformation (`A_required`) blows up while strict CHW2018 `R` tension remains large in tested families | Track explicitly via the WS13 closure-requirements map; treat this as a no-go indicator for the tested constant-boost family. If closure is to work, repair must start near the low end of the handoff region (`z~5`) or use richer early-time physics than a single high-z post-recombination boost. | `docs/early_time_e2_closure_requirements.md`; scripts: `scripts/cmb_e2_closure_requirements_plot.py`, `scripts/cmb_e2_highz_hboost_repair_scan.py` |
| E2 closure vs drift-sign tension | In tested full-history families, closure strategies that lower strict CHW2018 chi2 can contaminate the `z~2-5` drift-sign discriminator, while drift-protected variants remain CMB-incompatible (no-fudge) | Treat as an explicit decision problem, not hidden tuning: either protect drift-window sign and accept unresolved closure, or enforce compressed-prior closure and accept a direct drift-sign risk. Track this with the E2 synthesis decision tree and module-level diagnostics. | `docs/early_time_e2_synthesis.md`; `docs/diagnostics_index.md`; scripts: `scripts/cmb_e2_full_history_guarded_relax_scan.py`, `scripts/cmb_e2_highz_hboost_repair_scan.py` |
| E2 closure no-go under tested assumptions | Combining WS14 and WS15 evidence: tested proxy/deformation families do not yield a region with `drift_sign_ok=True` in `z~2-5` and strict no-fudge CHW2018 `chi2_cmb~O(1)` | Keep this explicitly scoped ("under tested assumptions"), avoid claim creep, and use it as a decision gate for any E2 reopen branch. Require future branches to declare changed assumptions (observables mapping/full CMB treatment/family definition) up front. | `docs/early_time_e2_synthesis.md`; `docs/early_time_e2_drift_constrained_bound.md`; `docs/early_time_e2_closure_to_physical_knobs.md` |
| Drift-constrained Pareto bound still large-chi2 | Even when drift amplitude is pushed close to the positive-boundary (`Delta v -> 0+`) in the tested drift-window deformation, strict CHW2018 chi2 remains `O(10^4)`; this is a no-go trend for that construction | Keep this bound as a referee-facing constraint and avoid over-interpreting any single repair family. Use it as a hard planning filter for E2 candidates (must improve closure without violating drift-window sign). | `docs/early_time_e2_drift_constrained_bound.md`; script: `scripts/cmb_e2_drift_constrained_closure_bound.py` |
| Large effective deformation scale (`deltaG`, `delta rho/rho`) | Closure mappings imply `deltaG = A^2 - 1`; for representative targets, medians rise from `~0.42` (`z_start=5`) to `~0.67` (`z_start=10`) and upper quantiles exceed unity | Track required scale explicitly to avoid hidden tuning; if required effective deformation remains large in drift-safe regions, classify tested family as practically non-viable and pivot E2 decision tree branch. | `docs/early_time_e2_closure_to_physical_knobs.md`; script: `scripts/cmb_e2_closure_to_physical_knobs.py` |

---

## Mitigations / Evidence (Guardrails & Portability)

Pointers to the "do not regress / do not leak machine state" checks:

- Drift-sign guardrail tests for the toy GSC histories: `tests/test_history_gsc.py`
- Precision-constraints translator (WEP/Oklo/clocks/LLR) + null-prediction lock-tests: `docs/precision_constraints_translator.md` and `tests/test_measurement_model_null_predictions.py`
- Manifest portability (repo-relative paths): `tests/test_manifest_repo_relative_paths.py`
- Canonical assets zip verification (sha256 + zip safety): `scripts/verify_release_bundle.py`
  - Unit tests: `tests/test_verify_release_bundle.py`
- Submission bundle builder (offline-safe, for arXiv/referees): `scripts/make_submission_bundle.py`
