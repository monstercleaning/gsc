# Phase-3 SigmaTensor-v1 model (background-only)

## Scope boundary

This document specifies a **minimal action-based background model** for Phase-3
scaffolding.

- It keeps the QFT matter sector standard.
- It adds a canonical scalar field for late-time background evolution.
- It does **not** include perturbations/Boltzmann hierarchy in this milestone.
- Full CMB TT/TE/EE spectra fitting is **out of scope** here and remains
  **future work** (not implemented in this background-only checkpoint).
- It does **not** claim dark-matter microphysics resolution.

## Action (Einstein frame, reduced Planck units)

\[
S = \int d^4x\,\sqrt{-g}\left[\frac{1}{2}R - \frac{1}{2}(\partial\phi)^2 - V(\phi)\right]
+ S_m[\psi_m,g] + S_r[\psi_r,g]
\]

Potential (v1):

\[
V(\phi)=V_0\exp\{-\lambda(\phi-\phi_0)\},\quad \phi_0=0\text{ (gauge default)}
\]

Define:

\[
x\equiv \ln a,\quad u\equiv \frac{d\phi}{dx},\quad E\equiv H/H_0,
\quad v(\phi)\equiv V(\phi)/(3H_0^2)=\hat V_0 e^{-\lambda\phi}.
\]

## Input parameterization

Primary inputs:

- `H0_si` in `1/s`
- `Omega_m0`
- `w_phi0` in `[-1,1)`
- `lambda >= 0`
- `sign_u0` in `{+1,-1}`
- optional radiation override `Omega_r0_override`
- otherwise `Omega_r0` from `(Tcmb_K, N_eff, H0)` via `omega_r_h2`

Derived at `x=0` (`a0=1`, `z=0`):

- `Omega_phi0 = 1 - Omega_m0 - Omega_r0` (must be `>0`)
- `u0 = sign_u0 * sqrt(3 * Omega_phi0 * (1 + w_phi0))`
- `Vhat0 = Omega_phi0 * (1 - w_phi0)/2`

## Background equations in `x=ln a`

Algebraic Friedmann:

\[
E^2(x) = \frac{\Omega_{m0}e^{-3x}+\Omega_{r0}e^{-4x}+v(\phi)}{1-u^2/6}
\]

Effective equation of state:

\[
\frac{p_{\rm tot}}{3H_0^2}=\frac{\Omega_{r0}e^{-4x}}{3}+\frac{u^2E^2}{6}-v,
\quad
\frac{\rho_{\rm tot}}{3H_0^2}=E^2,
\]

\[
w_{\rm eff}=\frac{\Omega_{r0}e^{-4x}}{3E^2}+\frac{u^2}{6}-\frac{v}{E^2},
\quad
\frac{d\ln H}{dx}=-\frac{3}{2}(1+w_{\rm eff}).
\]

Scalar equation:

\[
\phi'=u,
\quad
u' = -(3+d\ln H/dx)u - (3/E^2)\,dv/d\phi.
\]

For the exponential potential (`dv/dphi = -lambda v`):

\[
u' = -(3+d\ln H/dx)u + (3\lambda v)/E^2.
\]

## Derived diagnostics

On a fixed `z` grid:

- `H(z) = H0_si * E(z)`
- `Omega_phi(z) = u^2/6 + v/E^2`
- `w_phi(z) = (u^2/6 - v/E^2)/(u^2/6 + v/E^2)`

Action-reference exponent:

- `p_action = lambda^2/2`
- In scalar-dominated exponential-attractor conditions,
  `H(z) ~ (1+z)^(p_action)`.

This mapping is a **background-level diagnostic relation** in the current
Phase-3 scaffold; perturbations and full CMB spectra remain future work.

## Numerical method (M122)

- Deterministic fixed-grid RK4 in `x=ln a` from `x=0` to
  `x_end=-ln(1+z_max)`.
- No random seeds and no adaptive randomness.
- Fail-fast on non-physical states (`1-u^2/6 <= 0`, non-finite or non-positive
  `E^2`, non-finite state updates).

## Consistency checks (M123)

Deterministic checkpoint tooling:

- `scripts/phase3_st_sigmatensor_consistency_report.py`
- outputs:
  - `THEORY_CONSISTENCY_REPORT.json`
  - `THEORY_CONSISTENCY_REPORT.md`

Example:

```bash
python3 scripts/phase3_st_sigmatensor_consistency_report.py \
  --H0-km-s-Mpc 67.4 \
  --Omega-m 0.315 \
  --w0 -0.95 \
  --lambda 0.4 \
  --z-max 1100 \
  --n-steps 4096 \
  --outdir /tmp/st_consistency \
  --format text
```

Optional gate examples (all opt-in):

```bash
python3 scripts/phase3_st_sigmatensor_consistency_report.py \
  --H0-km-s-Mpc 67.4 \
  --Omega-m 0.315 \
  --w0 -0.95 \
  --lambda 0.4 \
  --z-max 1100 \
  --n-steps 4096 \
  --outdir /tmp/st_consistency \
  --require-accelerating-today \
  --require-early-omega-phi-lt 1e-2 \
  --require-denom-min-gt 1e-4
```

Scope reminder: these are background-level consistency gates only and do not
constitute perturbation/Boltzmann closure.

## EFT diagnostic export (M124)

Deterministic export tooling:

- `scripts/phase3_pt_sigmatensor_eft_export_pack.py`
- outputs:
  - `EFT_EXPORT_SUMMARY.json`
  - `EFT_ALPHAS.csv`
  - `README.md`

For canonical quintessence in GR, the exported alpha mapping uses:

- `alpha_M=0`, `alpha_B=0`, `alpha_T=0`, `c_s2=1`
- `alpha_K=u^2` with cross-check `alpha_K=3*Omega_phi*(1+w_phi)`

Example:

```bash
python3 scripts/phase3_pt_sigmatensor_eft_export_pack.py \
  --H0-km-s-Mpc 67.4 \
  --Omega-m 0.315 \
  --w0 -0.95 \
  --lambda 0.4 \
  --z-max 30 \
  --n-steps 2048 \
  --outdir /tmp/st_eft_export \
  --format text
```

Scope reminder: this is a background-only EFT diagnostic export scaffold and is
not a perturbation/Boltzmann closure.

## Boltzmann backend (CLASS) export pack (M125)

Deterministic bridge tooling:

- `scripts/phase3_pt_sigmatensor_class_export_pack.py`

This generates a Phase-2-harness-compatible CLASS export pack:

- `EXPORT_SUMMARY.json`
- `CANDIDATE_RECORD.json`
- `BOLTZMANN_INPUT_TEMPLATE_CLASS.ini`
- `README.md`
- `SIGMATENSOR_DIAGNOSTIC_GRID.csv` (diagnostic only)

Example:

```bash
python3 scripts/phase3_pt_sigmatensor_class_export_pack.py \
  --H0-km-s-Mpc 67.4 \
  --Omega-m 0.315 \
  --w0 -0.95 \
  --lambda 0.4 \
  --z-max 5 \
  --n-steps 512 \
  --outdir /tmp/st_class_export \
  --format text
```

Then run the existing harness/results flow:

```bash
python3 scripts/phase2_pt_boltzmann_run_harness.py \
  --export-pack /tmp/st_class_export \
  --code class \
  --runner docker \
  --run-dir /tmp/st_class_run \
  --overwrite \
  --created-utc 2000-01-01T00:00:00Z \
  --require-pinned-image
```

Scope reminder: this is backend wiring for external CLASS runs and does not add
an in-repo perturbation derivation. Any in-repo CMB context remains
compressed-priors / diagnostic-only in current scope, not a full CMB spectra
fit.

## Spectra sanity report (Phase-3, M126)

Deterministic external-output sanity tooling:

- `scripts/phase3_pt_spectra_sanity_report.py`

The tool performs portable, claim-safe checks on externally generated spectra
files (run directories or results-pack directories/zips):

- robust TT column detection (header-first, deterministic tie-breaks)
- finite/format checks and simple summary metrics (`ell` range, first TT peak)
- optional strict gates (exit code `2`) for CI/reviewer flows

Example on a results pack:

```bash
python3 scripts/phase3_pt_spectra_sanity_report.py \
  --path /tmp/st_results_pack \
  --outdir /tmp/st_spectra_sanity \
  --created-utc 2000-01-01T00:00:00Z \
  --require-tt 1 \
  --format text
```

Scope reminder: this is a spectra-format/consistency sanity layer only and not
a likelihood fit.

## Growth / fσ8 diagnostic report (Phase-3, M127)

Deterministic growth-bridge tooling:

- `scripts/phase3_sf_sigmatensor_fsigma8_report.py`

This report solves GR linear growth (`D`, `f`) over the SigmaTensor-v1
background and emits a deterministic `fσ8` diagnostic grid, with optional RSD
chi2 and optional AP correction.

Example:

```bash
python3 scripts/phase3_sf_sigmatensor_fsigma8_report.py \
  --H0-km-s-Mpc 67.4 \
  --Omega-m 0.315 \
  --w0 -0.95 \
  --lambda 0.4 \
  --sigma8-mode derived_As \
  --As 2.1e-9 \
  --rsd 1 \
  --ap-correction 0 \
  --outdir /tmp/st_fsigma8_report \
  --format text
```

Scope reminder: this is a background-driven GR growth diagnostic overlay and is
not a full perturbation/Boltzmann closure.

## Low-z joint diagnostics (BAO + SN + RSD, M128)

Deterministic joint diagnostic tooling:

- `scripts/phase3_joint_sigmatensor_lowz_report.py`

This report evaluates low-z BAO + SN + RSD blocks with analytic nuisance
profiling:

- BAO: profiled `r_d` nuisance
- SN: profiled `delta_M` nuisance
- RSD: profiled (or derived/fixed) `sigma8_0`

Optional LCDM baseline comparison (`w0=-1`, `lambda=0`) reports per-block and
total `delta_chi2` values for diagnostic context.

Example:

```bash
python3 scripts/phase3_joint_sigmatensor_lowz_report.py \
  --H0-km-s-Mpc 67.4 \
  --Omega-m 0.315 \
  --w0 -0.95 \
  --lambda 0.4 \
  --bao 1 --sn 1 --rsd 1 \
  --sigma8-mode nuisance \
  --compare-lcdm 1 \
  --outdir /tmp/st_lowz_joint \
  --format text
```

Scope reminder: this is a deterministic low-z diagnostic chi2 report and not a
full global cosmology fit.

## CMB distance priors bridge block (M129)

`phase3_joint_sigmatensor_lowz_report.py` now supports an optional compressed
CMB bridge block (`--cmb 1`) using Planck-2018 CHW2018 distance priors with
covariance.

- This is an E1 bridge diagnostic using `compute_bridged_distance_priors(...)`.
- It evaluates a compressed-prior chi2 block only.
- It is not a full CMB TT/TE/EE likelihood.

Example:

```bash
python3 scripts/phase3_joint_sigmatensor_lowz_report.py \
  --H0-km-s-Mpc 67.4 \
  --Omega-m 0.315 \
  --w0 -0.95 \
  --lambda 0.4 \
  --bao 1 --sn 1 --rsd 1 --cmb 1 \
  --cmb-z-bridge 5.0 \
  --omega-b-h2 0.02237 \
  --compare-lcdm 1 \
  --outdir /tmp/st_lowz_joint_cmb \
  --format text
```

## Relation to Phase-2 `p_late` intuition

Phase-2 used phenomenological power-law intuition in late-time diagnostics.
SigmaTensor-v1 provides an action-based background realization where the
scalar-dominated attractor naturally yields `p_action = lambda^2/2`.

## Next milestones (not in M122)

- EFT/alpha-function perturbation layer and Boltzmann-interface coupling.
- External-code perturbation comparisons as first-class validation channels.
- Non-linear structure extensions and broader survey likelihood integration.
- Additional microphysics constraints beyond background-level closure.
