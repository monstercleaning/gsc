# Early-time bridge (Option 2 / freeze-frame metrology) - spec v0

**Status:** Draft spec (v0)
**Goal:** Define a minimal, testable "early-time closure" for Option 2 that removes late-time nuisances (`r_d` free BAO; "compressed CMB" inputs) and becomes the gateway to full CMB integration later.

This spec is intentionally staged. Stage 0/1 should be implementable without CLASS/CAMB; Stage 2+ can optionally integrate with them.

---

## 0.1 Minimal closure selected for v0

**Chosen for v0:** `E0 (rd-only closure)`.

Rationale:

* Removes BAO `r_d` nuisance with minimal scope expansion.
* Keeps late-time freeze/release (`v10.1.1-late-time-r4`) stable and reproducible.
* Defers full CMB spectra integration to a later stage, consistent with v10.1 scope.

Out of scope for this v0 implementation:

* full TT/TE/EE likelihood,
* full perturbation engine in freeze-frame variables.

---

## 0.2 Diagnostic pointer: full-range (no-stitch) closure (E2.7)

Bridge-stage diagnostics (E1.*) are intentionally “stitched” by construction. To move beyond that
technical debt, we also maintain an **opt-in full-range (no-stitch) diagnostic** that defines a
single `H(z)` over `z∈[0,z*]` with a minimal `p(z)` relax and an explicit BBN safety clamp.

Tooling + docs:

* `scripts/cmb_e2_full_history_closure_scan.py`
* `scripts/reproduce_v10_1_e2_full_history_closure_diagnostic.sh`
* `docs/early_time_full_history.md`

Release tags (diagnostic-only): `v10.1.1-bridge-e2-full-history-closure-diagnostic-r0` and `...-r1`.

Related (diagnostic-only): E2.8 “guarded relax” adds `z_relax_start` to protect the `z~2–5` drift window
while allowing high-z convergence above the guard:

* `scripts/cmb_e2_full_history_guarded_relax_scan.py`
* `scripts/reproduce_v10_1_e2_full_history_guarded_relax_diagnostic.sh`

E2.10 (diagnostic-only) tests a more explicit “distance closure” proxy by applying a high-z multiplicative
deformation `H(z) -> A(z) H(z)` only for `z > z_boost_start` (chosen `>=5`), keeping the drift window intact:

* `scripts/cmb_e2_highz_hboost_repair_scan.py`
* `scripts/reproduce_v10_1_e2_highz_hboost_repair_diagnostic.sh`
* `docs/early_time_highz_hboost_repair.md`

WS13 consolidation (diagnostic-only) provides a compact closure-requirements/no-go map for referees:

* `scripts/cmb_e2_closure_requirements_plot.py`
* `scripts/reproduce_v10_1_e2_closure_requirements.sh`
* `docs/early_time_e2_closure_requirements.md`
* `docs/early_time_e2_synthesis.md` (single referee verdict / E2 decision tree)

---

## 0. Background

In Option 2 (freeze-frame measurement model), the *interpretation layer* is explicit: what an observer infers depends on how rulers/clocks/energy scales evolve. Late-time we already treat distances and redshift drift as metrology-aware observables.

Early-time tasks we must lock down:

1. **Compute** the BAO drag scale `r_d` (instead of profiling it away).
2. Define **compressed CMB "anchors"** (e.g. `θ*`, `R`, `ℓ_A`) in freeze-frame language.
3. Specify the minimal mapping needed for recombination bookkeeping to be consistent with the Option-2 metrology layer.

---

## 1. "Done" definition (for early-time bridge v0)

Early-time bridge v0 is "done" when we have:

* A deterministic function that returns `r_d` (in Mpc today) from a compact parameter set, with unit tests + regression value(s).
* A deterministic function that returns at least one compressed CMB anchor:

  * `θ* = r_s(z*) / D_A(z*)` (dimensionless), and/or
  * `(R, ℓ_A)` distance priors.
* A late-time pipeline mode where BAO is **not** `r_d`-free nuisance anymore:

  * BAO likelihood uses predicted `D_M(z)/r_d`, `D_H(z)/r_d`, etc with `r_d` computed.
* Clear declared assumptions: what is carried over from "standard early-time physics" and what is reinterpreted as metrology.

Non-goals for v0:

* Full TT/TE/EE spectra.
* Full recombination microphysics derivation in freeze frame.

---

## 2. Assumptions we must pin down (Option-2 compatible)

### 2.1 Conformal-duality bridge assumption (minimal-risk)

For early-time microphysics we adopt:

* Dimensionless local physics (couplings, ratios) is invariant under universal scaling.
* We can compute early-time dimensionless quantities using an Einstein-frame equivalent description, then map to freeze-frame "what is measured" using the established metrology rules.

This is consistent with the idea that many early-time observables are fundamentally dimensionless ratios (e.g. `θ*`).

### 2.2 CMB temperature bookkeeping

We must explicitly define what is meant by `T(z)` "as measured in atomic units".
Canonical choice (v0): keep the standard relation `T(z)=T0(1+z)` as metrology bookkeeping:

* photon energies are constant in the freeze background,
* detectors/atomic energy scales evolve,
* so the inferred temperature scales with `(1+z)`.

This makes recombination redshift and standard fitting formulas usable as a first bridge.

(If we later change this, it must be a deliberate v1 decision because it affects recombination.)

---

## 3. Parameterization for early-time closure

### 3.1 Minimal parameter set (v0)

Use a Planck-like "physical density" set:

* `H0` (km/s/Mpc)
* `Omega_m` (late-time)
* `Omega_b_h2` (baryons)
* `Omega_c_h2` (CDM)
* `N_eff` (optional v0, default 3.046)
* `T0` (default 2.7255 K)
* `Y_p` (optional; if omitted use a standard fitting formula or fixed value)

In v0 we can treat radiation density derived from `T0` and `N_eff`.

### 3.2 Bridge to existing late-time models

For models like `gsc_transition`:

* For `z > z_bridge` (e.g. `z_bridge ~ 20` or `~ 100`), use a standard radiation+matter expansion history (Einstein-frame equivalent) for purposes of `r_d` and `z*`.
* For `z <= z_bridge`, use the chosen late-time history model.

Continuity requirements:

* `H(z)` continuous at `z_bridge`
* `D_M(z)` continuous

---

## 4. Outputs & API (proposed)

Create a new module: `gsc/early_time_bridge.py` (or package `gsc/early_time/`).

### 4.1 `r_d` computation

* `compute_rd_Mpc(params) -> float`

Implementation options:

* Use Eisenstein & Hu / Hu & Sugiyama fitting formulas for `z_drag`, then integrate:

  * `r_s(z) = ∫_{z}^{∞} c_s(z') / H(z') dz'`
  * `r_d = r_s(z_drag)`
* Use SciPy quad for integration (since the current framework venv already has scipy).

### 4.2 Compressed CMB anchor

* `compute_theta_star(params, history) -> float`
  where:
* `z_star` is from fitting formula (Hu & Sugiyama) in v0,
* `r_s(z_star)` computed via same integrator,
* `D_A(z_star)` computed from the chosen `history` + Option-2 distance mapping rules.

Optional:

* `compute_distance_priors(params, history) -> dict` returning `{R, lA, omega_b_h2, ...}`.

---

## 5. Data contracts

### 5.1 CMB compressed priors file (v0)

Add a small CSV/JSON file under:

* `data/cmb/planck2018_distance_priors.csv` (or similar)

Contract:

* `name,value,sigma` (and optionally a covariance matrix file)

This must be versioned and cited in paper.

E1.1 strict (canonical) CMB mode uses a citation-grade vector+cov input:

* `data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv`
* `data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov`

CLI guardrail (strict path):

* CHW2018 distance priors must be run with `--cmb-cov` and `--cmb-mode distance_priors`
  (the CHW2018 `r_s(z*)` stopgap calibration is applied only in the `distance_priors` path).

and does not use `sigma_theory` by default. Any `sigma_theory` is treated as an
explicit opt-in bridge/dev knob.

### 5.2 E1.2 (strict): r_s(z*) stopgap calibration for CHW2018 lA

In strict CHW2018 distance-priors mode (`R`, `lA`, `omega_b_h2` + published covariance),
the most sensitive observable is:

* `lA = pi * D_M(z*) / r_s(z*)`

The bridge-level predictor uses:

* `z_star` from a fitting formula
* a lightweight numerical integral for `r_s(z*)` and `D_M(z*)`

At Planck-like benchmark parameters, this introduces a small systematic offset in `r_s(z*)`,
which inflates the `lA` pull under the very strict Planck covariance.

E1.2 introduces a tiny, explicit calibration factor applied only to `r_s(z*)` in the
CHW2018 distance-priors prediction path:

* file: `gsc/early_time/cmb_distance_priors.py`
* constant: `_RS_STAR_CALIB_CHW2018`

This calibration:

* applies only to `r_s(z*)` when evaluating CHW2018 distance priors
* does not apply to `r_d` / BAO (E0 `compute_rd_Mpc` is separate)
* is a stopgap to ensure strict E1.1 measures model/assumption tension rather than a known
  approximation offset in `r_s(z*)`

Benchmark (Planck-like) parameters:

* `H0=67.4`
* `Omega_m=0.315`
* `omega_b_h2=0.02237`
* `omega_c_h2=0.1200`
* `Neff=3.046`
* `Tcmb_K=2.7255`

Expected strict regression (CHW2018, no `sigma_theory`):

* `pull(R) ~ -0.08`
* `pull(lA) ~ 0.0` (calibrated)
* `pull(omega_b_h2) ~ 0.07`
* `chi2_cmb ~ 0.01` (3 dof)

TODO(v10+): replace this with a higher-precision early-time engine or an explicitly-derived
freeze-frame treatment of recombination, and remove the calibration.

Numerics audit (integration vs definition):

* Tag/Release: `v10.1.1-bridge-e2-rs-star-numerics-audit-r0`
* Entry point: `scripts/reproduce_v10_1_rs_star_numerics_audit.sh`

At Planck-like parameters, the audit compares the current bridge-level trapezoid
integral for `r_s(z*)` (in `u=ln(1+z)`) against a Gauss–Legendre quadrature
reference using the same `z*` fitting formula. Result: the trapezoid
discretization error at the canonical grid (`n=8192`) is **O(10^{-8}) relative**
(sub-ppm), far smaller than the **+0.2889%** CHW2018 stopgap calibration.

Interpretation: the CHW2018 `r_s(z*)` stopgap factor is **not** explained by
numerical quadrature error of the `r_s` integral itself; it is dominated by
bridge-level approximations (e.g. `z*` fit / compressed-prior definition
matching) and remains a scoped, explicit stopgap.

Definition audit (z* vs r_s):

- Tag/Release: `v10.1.1-bridge-e2-zstar-recombination-audit-r0`
- Entry point: `scripts/reproduce_v10_1_e2_zstar_recombination_audit_diagnostic.sh`

This diagnostic compares `z*` from the Hu–Sugiyama fitting formula against a minimal
Peebles-style recombination ODE (hydrogen-only; approximate) and recomputes `r_s(z*)`
at the resulting `z*`. Purpose: estimate how much of the ~0.29% CHW2018 stopgap could
be attributed to *definition/approximation* choices in `z*` (not quadrature error).

E1.2 strict canonical artifact:

* Tag/Release: `v10.1.1-bridge-e1.2-strict-r1` (repo-relative `manifest.json`)
* Entry point: `scripts/reproduce_v10_1_late_time_e1_2_strict.sh`
* Benchmark helper: `scripts/cmb_chw2018_benchmark.py`

Provenance/guardrails:

* Calibration is applied only to `r_s(z*)` in the CHW2018 distance-priors path (not to `r_d` / BAO).
* The reproducibility manifest records calibration provenance under:
  `cmb_by_model.<model>.rs_star_calibration*`

---

## 5.3 E1.3 (diagnostic): non-LCDM bridge sensitivity scan

E1.3 is intentionally a **diagnostic** bridge layer for non-LCDM late-time
histories. It does **not** claim a full CMB likelihood or a solved early-time
freeze-frame recombination mapping.

Key design choices:

* `--cmb-bridge-z` is an explicit *diagnostic knob* (not a physical parameter).
* Strong dependence of CMB pulls/chi2 on `bridge_z` is expected and is used to
  indicate that full early-time closure is not yet specified for the model.

Reproduce entry point (scan over several `bridge_z` values):

* `scripts/reproduce_v10_1_late_time_e1_3_diagnostic.sh`

Outputs:

* `results/late_time_fit_cmb_e13_diagnostic/cmb_bridge_scan.csv`
* `results/late_time_fit_cmb_e13_diagnostic/figures/chi2_cmb_vs_bridge_z.png`
* `results/late_time_fit_cmb_e13_diagnostic/tables/cmb_best_debug.txt`
* `results/late_time_fit_cmb_e13_diagnostic/tables/cmb_pzt_coarse_scan.csv`

Interpretation (expected behavior):

* For non-LCDM histories, strict CHW2018 distance priors can yield extremely large
  pulls/chi2 under this bridge closure. This is expected and is the diagnostic
  output: it quantifies sensitivity to `bridge_z` and to the late-time history
  assumptions, not a solved CMB likelihood.
* **Degeneracy warning (gsc_transition):** if `bridge_z_used <= z_transition`,
  then the CMB comoving-distance integral for `D_M(z*)` never enters the powerlaw
  segment. In that case the CMB prediction is effectively **LCDM-only** with
  respect to `(p, z_transition)` and is **not diagnostic** of the high-z GSC
  behavior. Diagnostic scans record this as `is_degenerate=true` and exclude such
  points from "best" selection.

This is meant for sensitivity studies and reviewer-facing transparency, not for
the canonical the current framework late-time paper assets.

**Distance-budget diagnostic (why `bridge_z >= 5` fails):**
the `D_M(z*)` tension in E1.3 is dominated by the **low-redshift** contribution. In the default
diagnostic parameterization (`gsc_transition`, `p=0.6`, `z_transition=1.8`), pushing `bridge_z` to 5
makes the **[2,5]** segment of the `D_M(z*)` integral deviate strongly from the early-time LCDM+rad
baseline, while the `[5,20]` and `[20,z*]` segments are unchanged by construction.
See: `scripts/cmb_distance_budget_diagnostic.py` (writes into
`results/diagnostic_cmb_distance_budget/`). This diagnostic motivates the E2 plan:
`docs/early_time_e2_plan.md`. Canonical E1.3 artifact: `v10.1.1-bridge-e1.3-diagnostic-r3`.

**E2.2 closure diagnostic (what would it take?):**
even if we allow an extra scaling of `r_s(z*)` (E2.0), strict CHW2018 distance priors remain catastrophic at
non-degenerate `bridge_z` because `R` (and thus `D_M(z*)`) is unchanged. E2.2 introduces a diagnostic-only
joint-fit of `(dm_star_calibration, rs_star_calibration)` that answers: “how much would `D_M(z*)` and `r_s(z*)`
need to shift to close CHW2018?”. For `gsc_transition p=0.6 z_transition=1.8` at `bridge_z_used=5`:

* Distance-budget: the excess `ΔD_M(z*)` is dominated by the **[2,5]** segment (≈ `+1070 Mpc`); above 5 is 0 by bridge construction.
* Joint fit (diagnostic-only): `dm_star_calibration_fit ≈ 0.929` (≈ `-7.1%` in `D_M(z*)`),
  `rs_star_calibration_fit ≈ 1.0045`, with `chi2_cmb_min ≈ 0.0177` under strict CHW2018 covariance.

Tool: `scripts/cmb_dm_rs_star_fit_diagnostic.py`. Artifact tag:
`v10.1.1-bridge-e2-dm-rs-fit-diagnostic-r0` (diagnostic-only).

### E1.3 diagnostic findings (r3)

Degeneracy definition (must not be treated as a “good fit”):

* If `bridge_z_used <= z_transition`, then the CMB comoving-distance integral for `D_M(z*)` never enters
  the non-LCDM (powerlaw) segment of `gsc_transition`. The CMB prediction is effectively LCDM-only with
  respect to `(p, z_transition)`, and the point is recorded as degenerate (`is_degenerate=true`).

Manifest provenance keys to look at (both in results and in synced paper assets):

* `cmb_by_model.<model>.cmb_bridge_degenerate`
* `cmb_by_model.<model>.cmb_bridge_degenerate_reason`
* `cmb_by_model.<model>.bridge_z_used`
* `cmb_by_model.<model>.rs_star_calibration` (CHW2018 stopgap; applied only to `r_s(z*)`)

Numbers (r3 checkpoint; fixed parameters scan):

* Best **non-degenerate** `gsc_transition` point: `chi2_cmb = 13.465` at `bridge_z_used = 2.0` with `lA ≈ 3.145σ`.
* For **bridge_z >= 5**, the CHW2018 distance-priors tension becomes catastrophic:
  e.g. `chi2_cmb ≈ 8.25e4` at `bridge_z_used = 5`.

Canonical artifact:

* Tag/Release: `v10.1.1-bridge-e1.3-diagnostic-r3`

## 6. Tests (required for DoD)

### 6.1 Unit tests

* `test_rd_monotonicity`: `r_d` decreases as `Omega_m h^2` increases (basic sanity).
* `test_rd_regression_planck`: regression check vs a known reference value (Planck 2018 best-fit; tolerance e.g. 0.5-1% for v0).
* `test_theta_star_regression`: regression vs a reference.

### 6.2 Integration tests (pipeline)

* Add a CI "synthetic" run that computes `r_d` and runs BAO likelihood in "rd-derived" mode.

---

## 7. PR checklist v0 (for implementation PR)

* [ ] Spec reviewed: assumptions 2.1-2.2 are explicitly implemented as stated.
* [ ] New module: `gsc/early_time_bridge.py` (or package) with docstrings.
* [ ] `compute_rd_Mpc` implemented + unit tests.
* [ ] `compute_theta_star` implemented + regression test.
* [ ] BAO likelihood supports `--bao-rd-mode derived` (or similar), with clear defaults.
* [ ] CI passes (`scripts/ci_quick.sh`) with a minimal smoke early-time run.
* [ ] Paper provenance: add citations + manifest includes CMB-prior input checksums.

---

## 8. Spec PR gate (this PR only)

* [x] `E0 (rd-only)` selected explicitly as the v0 closure.
* [x] DoD stated in testable terms (`r_d` deterministic + regression + pipeline mode switch).
* [x] API surface declared before implementation.
* [x] Non-goals stated to prevent scope creep in v0.

---

## 9. Implementation stub list (next PRs)

1. `gsc/early_time_bridge.py`
2. `tests/test_early_time_bridge.py`
3. `data/cmb/planck2018_distance_priors.csv`
4. `scripts/late_time_fit_grid.py` (rd-mode switch)
5. `scripts/late_time_make_manifest.py` (record early-time method/config hash)

---

## 10. E1 skeleton (compressed CMB priors / theta*)

Purpose of E1 is interface hardening, not full CMB closure:

* Add a data contract for compressed CMB priors.
* Add loader and CLI flags with no behavior change unless explicitly enabled.
* Keep default late-time and E0 flows unchanged.

Minimal E1 contract:

* `--cmb PATH` points to a scalar-prior CSV (`name,value,sigma`).
* Optional `--cmb-cov PATH` for vector priors (future extension).
* `--cmb-mode {theta_star,distance_priors}` declares interpretation mode.

E1 DoD (skeleton PR):

* [ ] `data/cmb/README.md` exists with provenance/contract notes.
* [ ] `data/cmb/planck2018_distance_priors.csv` placeholder is versioned.
* [ ] `gsc/datasets/cmb_priors.py` loads scalar priors deterministically.
* [ ] `late_time_scorecard.py` and `late_time_fit_grid.py` expose `--cmb*` flags.
* [ ] Passing `--cmb` before E1 likelihood wiring exits with a clear "E1 skeleton" message.
* [ ] Unit tests cover loader and CLI guardrail behavior.
