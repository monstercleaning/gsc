# Early-Time Bridge: E2 Plan (Option 2 / freeze-frame) — design note

**Status:** Design note (E2 plan)
**Scope:** Diagnostic/bridge layer only (not canonical for submission).

This document defines the next bridge layer after E1.*: **E2**, whose purpose is to remove the
diagnostic “stitch knob” and make the early-time mapping to compressed CMB priors self-consistent.

---

## 1) What is E2 (minimum definition)

E2 is the minimal bridge layer that:

1. Integrates a **single** effective `H(z)` consistently from `z=0` to `z=z*`, including:
   - matter + radiation (with explicit `N_eff` bookkeeping),
   - late-time model history parameters (e.g. `p`, `z_transition`) where applicable.
2. Computes, self-consistently:
   - `D_M(z*)` (comoving distance to recombination),
   - `r_s(z*)` (sound horizon at recombination),
   - compressed CMB distance priors such as `(R, lA, omega_b_h2)` (or equivalent).

In other words: **no explicit `cmb_bridge_z`** stitch is allowed in E2. The mapping must be
well-defined as a single function `H(z; params)` over the full range.

---

## 2) Degrees of freedom (allowed vs forbidden)

Allowed (explicit parameters):

- Late-time history parameters (model-dependent): e.g. `p`, `z_transition`, etc.
- Physical densities: `omega_b_h2`, `omega_c_h2`, plus `N_eff` and `Tcmb_K` (defaults allowed).
- Late-time `H0` (or an equivalent normalization), with clear units and priors if fitting.

Forbidden (E2 must not rely on these “stopgaps”):

- Ad hoc calibration factors for `r_s(z*)` as a permanent mechanism.
- A free “stitch” knob like `cmb_bridge_z` that replaces part of the integral by construction.
- Untracked fudge terms (`sigma_theory`, etc.) as defaults. If used, they must be explicitly opt-in
  diagnostics, not part of E2’s baseline definition.

---

## 3) Test plan (how we know E2 is working)

Regression (LCDM sanity):

- At Planck-like parameters, E2 must reproduce a stable “Planck-like” baseline for:
  - `z*` (from the chosen definition/fit),
  - `D_M(z*)`, `r_s(z*)`, `lA`, `R`,
  within declared tolerances.

Sensitivity tests (non-LCDM histories):

- Scan sensitivity of `D_M(z*)` and `lA` to the late-time history parameters (e.g. `p`, `z_transition`).
- Compare to the E1.3 diagnostic behavior to confirm that the prior “catastrophic” dependence on
  `bridge_z` is replaced by a well-defined dependence on physical/model parameters.

Diagnostics:

- Maintain a “distance budget” breakdown for `D_M(z*)` by redshift interval to localize where tension
  accumulates (see `scripts/cmb_distance_budget_diagnostic.py`).

---

## 4) Guardrails (process / repo hygiene)

- E2 is a bridge/diagnostic layer only:
  - It must not modify the canonical late-time release (`v10.1.1-late-time-r4`) or submission artifacts.
- Outputs must be isolated:
  - results in `results/early_time_*` or `results/diagnostic_*`
  - paper assets only if explicitly requested (default: do not write `paper_assets_*`).
- Any E2 tags/releases must be new (`v10.1.1-bridge-e2-*`) and must not retag existing releases.

---

## 5) E2.0 results (rs_star fit diagnostic)

**Question (diagnostic-only):** For a *non-degenerate* bridge (`bridge_z_used > z_transition`), how much
extra rescaling of `r_s(z*)` would be required to minimize strict CHW2018 distance-priors chi2 if we
allow changing **only** `lA` via `r_s(z*)` scaling (i.e. `lA -> lA / k`) while keeping `R` fixed?

Tooling:

- `scripts/cmb_rs_star_calibration_fit_e2.py` (single point)
- `scripts/cmb_rs_star_calibration_scan_e2.py` (batch scan + figures + assets zip)

Representative numbers (strict CHW2018 cov; `gsc_transition p=0.6 z_transition=1.8`):

- `bridge_z_used=2` (non-degenerate but barely):
  - baseline `chi2_cmb ≈ 13.47`
  - fitted `rs_star_calibration_fit ≈ 1.000956` (about **+0.096%** in `r_s(z*)`)
  - `chi2_cmb_min ≈ 0.057`
- `bridge_z_used=5` (strongly non-degenerate):
  - baseline `chi2_cmb ≈ 8.25e4` (catastrophic; `R` pull ~29σ, `lA` pull ~265σ)
  - fitted `rs_star_calibration_fit ≈ 1.074` (about **+7.4%** in `r_s(z*)`)
  - `chi2_cmb_min ≈ 1.49e3` (still catastrophic; `R` mismatch remains)

Interpretation:

- If the required shift in `r_s(z*)` is **O(1–2%)**, it might be an “early-time closure” requirement
  that could plausibly be met by an E2 treatment.
- If the required shift is **~8–10%+**, it is a major early-universe requirement.
- In practice, the `bridge_z=5` case shows that even allowing a large `r_s(z*)` rescaling cannot repair
  the `R` mismatch, so E2 must address the **`D_M(z*)` integral** (not only `lA` / `r_s(z*)`).

**Explicit guardrail:** This rs* fit is a diagnostic-only nuisance and is not used in the canonical
late-time release or submission pipeline.

---

## 6) E2.2 results (D_M(z*) + r_s(z*) joint-fit diagnostic)

**Question (diagnostic-only):** For a *non-degenerate* bridge (`bridge_z_used > z_transition`), what combined
shift in `D_M(z*)` and `r_s(z*)` would be required to make strict CHW2018 distance priors compatible?

Tooling:

- `scripts/cmb_dm_rs_star_fit_diagnostic.py`

Method (deterministic, semi-analytic):

- Grid over `rs_star_calibration` (multiplicative on `r_s(z*)`)
- For each grid point, solve analytically for the optimal `dm_star_calibration` (multiplicative on `D_M(z*)`),
  since chi² is quadratic in `dm` when `rs` is held fixed.

Representative numbers (strict CHW2018 cov; `gsc_transition p=0.6 z_transition=1.8`, `bridge_z_used=5`):

- Report baseline (context): `dm=1.0`, `rs=_RS_STAR_CALIB_CHW2018=1.0028886` gives `chi2_cmb ≈ 8.25e4`
  with `R` pull ~29σ and `lA` pull ~265σ.
- Joint fit (diagnostic-only):
  - `dm_star_calibration_fit ≈ 0.929094` (about **-7.09%** in `D_M(z*)`)
  - `rs_star_calibration_fit ≈ 1.0045` (about **+0.45%** vs 1.0; **+0.16%** vs the CHW2018 stopgap baseline)
  - `chi2_cmb_min ≈ 0.0177`, with pulls `R ≈ 0.04σ`, `lA ≈ 0.001σ`, `omega_b_h2 ≈ 0.07σ`.

Interpretation:

- This confirms that strict CHW2018 compatibility for a non-degenerate bridge requires **distance closure**:
  `D_M(z*)` must be reduced by O(7%) relative to the current E1 bridge prediction in this checkpoint.
- The required additional `r_s(z*)` shift beyond the CHW2018 stopgap is sub-percent here; the dominant lever is
  `D_M(z*)` (equivalently: an effective boost in `H(z)` over the relevant part of the high-z distance integral).

**Explicit guardrail:** This is a diagnostic “what would it take” tool. The fitted calibrations are not used in the
canonical late-time release or submission pipeline, and do not constitute a physical early-time model.

---

## 7) E2.3 results (dm\* distance closure → effective H(z) boost mapping)

**Question (diagnostic-only):** If E2.2 suggests a required multiplicative reduction of `D_M(z*)` by
`dm_star_calibration_fit` at a *non-degenerate* bridge point, what is the equivalent **constant**
boost `A` one would need to apply to `H(z)` on `[z_boost_start, z*]` to obtain the same reduction?

Tooling:

- `scripts/cmb_e2_distance_closure_to_hboost.py`

Definition (effective mapping only; not physics):

- write the bridge distance split as `D_M(z*) = D_M(0->z_boost_start) + D_M(z_boost_start->z*)`.
- define `D_M_target = dm_star_calibration * D_M(z*)`.
- solve for `A` such that `D_M(0->z_boost_start) + D_M(z_boost_start->z*)/A = D_M_target`.

Representative mapping (E2.2 snapshot; `gsc_transition p=0.6 z_transition=1.8`, `bridge_z_used=5`):

- `dm_star_calibration_fit ≈ 0.929094` implies an effective **constant** high-z boost
  `A( z_boost_start = 5 ) ≈ 1.2176` (≈ **+21.8%** in `H(z)` on `[5, z*]`).

Interpretation:

- A “~7% distance closure” at `z*` generally corresponds to a **larger** fractional change in `H(z)` at high z,
  because `D_M(0->z_boost_start)` is fixed by the late-time history and cannot be repaired by any boost applied
  only above `z_boost_start`.

**Explicit guardrail:** This is an interpretation mapping for planning E2 work, not a physical early-time closure.

---

## 8) E2.4 results (coarse dm\*/rs\* closure scan)

**Question (diagnostic-only):** Over a coarse family of late-time histories, how does the required
distance closure (`dm_fit`) vary with `(p, z_transition)` and with the non-degenerate bridge choice?

Tooling:

- `scripts/cmb_e2_dm_rs_fit_scan.py`
- Reproduce wrapper: `scripts/reproduce_v10_1_late_time_e2_closure_diagnostic.sh`

Grid (fixed Planck-like early inputs; strict CHW2018 cov):

- `p ∈ {0.55,0.6,0.65,0.7,0.75,0.8,0.9}`
- `z_transition ∈ {0.8,1.2,1.5,1.8,2.2,3.0,4.0}`
- `bridge_z_used ∈ {5, 10}` (both are non-degenerate on this grid)

Diagnostic scan summary (this grid; `gsc_transition`):

- For `bridge_z_used=5`:
  - `dm_fit` median ≈ **0.9438**, range ≈ **[0.8245, 0.9992]**
- For `bridge_z_used=10`:
  - `dm_fit` median ≈ **0.8332**, range ≈ **[0.6555, 0.9615]**
- Over this fixed-early-params grid, `rs_fit` is essentially constant (`≈ 1.0045`), reinforcing that the dominant
  lever is **distance closure** (i.e. `D_M(z*)` / `R`), not `r_s(z*)`.

Artifact pointer:

- Pre-release tag (diagnostic-only): `v10.1.1-bridge-e2-closure-diagnostic-r1`
  - Includes tables/figures/manifest for E2.3 + E2.4 (referee pack material; not part of submission bundle).

---

## 9) E2.5 results (drift ↔ CMB closure correlation diagnostic)

**Question (diagnostic-only):** Over the same coarse family of late-time histories, how does the **late-time**
drift amplitude (e.g. `Δv(z=4)` over 10 years) correlate with the required **early-time distance closure**
(`dm_fit`) and the effective high-z boost mapping `A`?

Tooling:

- `scripts/cmb_e2_drift_cmb_correlation.py`
- Reproduce wrapper: `scripts/reproduce_v10_1_e2_drift_cmb_correlation.sh`
- Doc note: `docs/early_time_drift_cmb_correlation.md`

Artifact pointer:

- Pre-release tag (diagnostic-only): `v10.1.1-bridge-e2-drift-cmb-correlation-r0`
  - Includes correlation tables/figures/manifest (diagnostic; out of submission scope).

---

## 10) E2.6 note (neutrino-sector knob; diagnostic-only)

Tooling + doc:

- Script: `scripts/cmb_e2_neutrino_knob_diagnostic.py`
- Doc: `docs/early_time_neutrino_knob.md`

Checkpoint takeaway (r0 snapshot; strict CHW2018 cov; `gsc_transition p=0.6 z_transition=1.8`):

- Varying `Delta N_eff` can shift `r_s(z*)` (and therefore `lA`) substantially, but the required
  **distance closure** `dm_fit` remains the dominant requirement for non-degenerate bridges.
- At `bridge_z_used=5`, `dm_fit` stays near `~0.928–0.929` across `Delta N_eff ∈ [-1,+1]`
  (equivalent to an effective constant `A_required_const ~ 1.22` on `[5,z*]`).
- At `bridge_z_used=10`, the required closure remains extreme (`dm_fit ~ 0.795`, `A_required_const ~ 6.3`).

Interpretation: in this checkpoint, “sound-horizon-only” knobs do not remove the need for a genuine **distance-integral**
closure mechanism in E2.

---

## 11) E2.7 (full-range history; no stitch) — diagnostic-only

**Goal (diagnostic-only):** move beyond the “bridge stitch” construction by defining a **single**
full-range history `H(z)` over `z ∈ [0, z*]`, then test whether a minimal `p(z)` relaxation can
reduce the strict CHW2018 distance-priors tension without a bridge parameter.

Key features:

- A full-range history that reproduces the late-time `gsc_transition` behavior for `z≲few`.
- A 1-parameter **`p_eff(z)` relax** (from `p_late` toward `1.5`) for `z≫z_transition`.
- An explicit **BBN safety clamp** (diagnostic guardrail): for `z >= z_bbn_clamp`, force
  `H(z) = H_LCDM+rad(z)` and record this in manifests.

Tooling:

- Histories: `gsc/histories/full_range.py`
- Compressed CMB priors (full-history path): `compute_full_history_distance_priors(...)`
- Scan script: `scripts/cmb_e2_full_history_closure_scan.py`
- Reproduce wrapper: `scripts/reproduce_v10_1_e2_full_history_closure_diagnostic.sh`
- Doc note: `docs/early_time_full_history.md`

Artifact pointer (diagnostic-only): `v10.1.1-bridge-e2-full-history-closure-diagnostic-r0`.

### What r1 adds (hardening / interpretability)

The r1 diagnostic package makes E2.7 more referee-readable by explicitly separating:

- **No-fudge baseline**: strict CHW2018 chi² with `dm=1`, `rs=1` (no calibration factors), including pulls.
- **Residual “what would it take” mapping**: best-fit `(dm_fit, rs_fit)` and `Δchi² = chi²_base − chi²_min`.
- **Drift sanity**: records `Δv(z)` over 10 years for `z∈{2,3,4,5}` for both the late-time history and the full-history variant,
  and a boolean `drift_sign_ok` (keeps the drift discriminator from being “paid for” silently).
- **BBN guardrail**: a cheap lock test enforces that for `z >= z_bbn_clamp` the full-history `H(z)` matches LCDM+rad within tolerance.

Artifact pointer (diagnostic-only): `v10.1.1-bridge-e2-full-history-closure-diagnostic-r1`.

---

## 12) E2.8 (guarded relax: protect drift window) — diagnostic-only

E2.7 identified a high-leverage failure mode: a fast high-z relax can reduce strict CHW2018 chi² in the
full-history mode, but it may also contaminate the **late-time drift discriminator** in the `z~2–5` window.

E2.8 introduces a minimal guard (diagnostic-only):

- keep the exact late-time power-law GSC component up to `z_relax_start` (chosen `>=5`);
- allow `p_eff(z)` relax toward `p_target=1.5` only for `z > z_relax_start`.

This produces a clean “feasible region” diagnostic: points where `drift_sign_ok=True` **and**
`chi2_full_base` is significantly reduced (no-fudge, strict CHW2018).

Tooling:

- Full-history implementation: `gsc/histories/full_range.py` (`z_relax_start`, guarded mode)
- Scan script: `scripts/cmb_e2_full_history_guarded_relax_scan.py`
- Reproduce wrapper: `scripts/reproduce_v10_1_e2_full_history_guarded_relax_diagnostic.sh`
- Doc note: `docs/early_time_full_history.md`

---

## 13) E2.10 (high-z H-boost repair; drift-safe) — diagnostic-only

E2.8 shows that `p(z)` relax alone may be insufficient to close strict CHW2018 distance priors while
preserving the late-time drift discriminator.

E2.10 introduces a deliberately model-agnostic proxy for “distance closure”:

- apply an explicit multiplicative deformation `H(z) -> A(z) H(z)` only above a guard redshift
  `z_boost_start` (chosen `>=5`), so the drift window `z∈[2,5]` remains untouched by construction.

This tests whether strict CHW2018 chi² can be reduced in **full-history** mode without any `dm/rs`
fit knobs (i.e. “no-fudge” closure check).

Tooling:

- Wrapper: `gsc/histories/full_range.py` (`HBoostWrapper`)
- Scan script: `scripts/cmb_e2_highz_hboost_repair_scan.py`
- Reproduce wrapper: `scripts/reproduce_v10_1_e2_highz_hboost_repair_diagnostic.sh`
- Doc note: `docs/early_time_highz_hboost_repair.md`

---

## 14) WS13 consolidation (closure requirements / no-go map) — diagnostic-only

To keep referee discussion concise, WS13 consolidates E2.2/E2.4 closure targets and E2.10 no-fudge
results into one map:

- infer representative `dm_fit` targets from E2.4 (bridge-filtered quantiles + anchor points),
- map each target to `A_required(z_boost_start)` via the E2.3 constant-boost formula,
- expose the practical no-go trend when repair starts too high (`z~10+`) in tested families.

Tooling + note:

- script: `scripts/cmb_e2_closure_requirements_plot.py`
- reproduce wrapper: `scripts/reproduce_v10_1_e2_closure_requirements.sh`
- doc: `docs/early_time_e2_closure_requirements.md`

---

## 15) Diagnostics index (single entrypoint)

For reviewers and new sessions, use the consolidated index:

- `docs/diagnostics_index.md`

It tracks (for each diagnostic module): release tag URL, asset name, SHA256, reproduce command, and result outdir.

Companion short summary for reviewers:

- `docs/early_time_e2_executive_summary.md`

## 16) Current status (referee-facing synthesis)

For a single referee-grade verdict across E1/E2 diagnostics, read:

- `docs/early_time_e2_synthesis.md`

This note consolidates what has been ruled out in tested deformation families, what remains feasible,
and the current E2 decision tree (drift-window protection vs strict compressed-prior closure assumptions).

---

## 17) E2.10 drift-constrained closure bound (Pareto diagnostic)

Purpose:

- provide a parameterization-light bound between the drift discriminator and strict CHW2018 closure:
  `chi2_cmb` vs `Delta v(z=4,10y)` while enforcing positive drift in `z in [2,5]`.

Construction (diagnostic-only):

- deform only the drift window with `H_mod=(1-s)H_base+sH_cap`, `s in [0,1)`, where
  `H_cap=H0(1+z)(1-epsilon_cap)`.
- keep high-z (`z>5`) reference as flat LCDM+rad.

Checkpoint result (baseline params):

- `s=0`: `chi2_cmb ~= 8.32e4`, `Delta v(z=4,10y) ~= 4.53 cm/s`
- best scanned point (`s=0.995`): `chi2_cmb ~= 1.54e4`, `Delta v(z=4,10y) ~= 0.0227 cm/s`
- all points keep positive drift (`drift_sign_ok=True`), but strict CHW2018 closure remains far from `O(1)`.

Pointers:

- Script: `scripts/cmb_e2_drift_constrained_closure_bound.py`
- Reproduce: `scripts/reproduce_v10_1_e2_drift_constrained_closure_bound.sh`
- Doc: `docs/early_time_e2_drift_constrained_bound.md`
- Tag: `v10.1.1-bridge-e2-drift-constrained-closure-bound-r0`

---

## 18) E2.11 closure requirements -> physical knobs (diagnostic translation)

Purpose:

- translate `A_required`/`dm_target` closure requirements into effective physical scales for planning:
  `deltaG = A^2 - 1`, `delta rho/rho = A^2 - 1`.

Representative quantiles from WS13 targets:

- `z_start=5`: median `A ~= 1.191`, median `deltaG ~= 0.420`
- `z_start=10`: median `A ~= 1.290`, median `deltaG ~= 0.666`

Interpretation:

- delaying repair start pushes required effective deformation to large `O(1)` scales in tested families.

Pointers:

- Script: `scripts/cmb_e2_closure_to_physical_knobs.py`
- Reproduce: `scripts/reproduce_v10_1_e2_closure_to_physical_knobs.sh`
- Doc: `docs/early_time_e2_closure_to_physical_knobs.md`
- Tag: `v10.1.1-bridge-e2-closure-to-physical-knobs-r0`

---

## 19) Consolidated status pointers (WS14/WS15)

Use these as the current E2 status entrypoint:

- `docs/early_time_e2_synthesis.md` (referee verdict + decision paragraph)
- `docs/early_time_e2_drift_constrained_bound.md` (WS14)
- `docs/early_time_e2_drift_bound_analytic.md` (WS14 analytic sanity appendix)
- `docs/early_time_e2_closure_to_physical_knobs.md` (WS15)
- `docs/diagnostics_index.md` (tags/assets/SHA256/reproduce map)

Synthesis note sections to read first:

- `Assumptions behind E2 diagnostics`
- `What would have to change to reopen E2`
