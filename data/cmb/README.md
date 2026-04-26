# CMB compressed priors (E1 skeleton)

This directory is reserved for E1 compressed-CMB inputs used by the
early-time bridge.

Status in this branch:

* Contract and loader scaffolding only.
* No default pipeline usage yet.
* Values in `planck2018_distance_priors.csv` are placeholders for wiring/tests.

Citation-grade inputs:

* `planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv` + matching
  covariance `planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov`
  provide a Planck 2018 distance-priors vector `(R, lA, omega_b_h2)` sourced
  from Chen, Huang & Wang (2018, arXiv:1808.05724). These are intended for E1
  bridge/diagnostic runs.

E1.1 strict (canonical) mode:

* Use the CHW2018 vector+cov dataset above.
* Always pass the covariance file (`--cmb-cov ...cov`), not diag-only.
* Always run with `--cmb-mode distance_priors` (strict path; CHW2018 `r_s(z*)` stopgap calibration is only applied there).
* Do not use `sigma_theory` (the canonical CHW2018 CSV does not include it).

For bridge/dev runs, `planck2018_distance_priors_with_theory_floor.csv` adds a
nonzero `sigma_theory` for `theta_star`. This is opt-in and is not used by the
default pipeline.

For non-LCDM late-time models, CMB priors are only supported with an explicit
`--cmb-bridge-z` (a diagnostic knob that controls where the late-time history
is stitched onto an LCDM+rad early-time history for `D_M(z_*)`). `theta_star` is
knife-edge, so strong sensitivity to `--cmb-bridge-z` is expected in E1 bridge
mode.

Planned contract (v1):

* Scalar mode: CSV columns `name,value,sigma` (optional `label`).
* Optional: `sigma_theory` (absolute) to add a theory-error floor in quadrature:
  `sigma_eff^2 = sigma^2 + sigma_theory^2`.
* Vector mode: values CSV + covariance file, similar to BAO vector blocks.

When E1 is activated, all priors must be documented with source citations and
checked into `manifest.json` via dataset path + SHA256.
