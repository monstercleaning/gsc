# E2.10 Drift-Constrained Closure Bound (Diagnostic-Only)

Scope: this is a diagnostic bound, not a submission claim.  
It does not modify canonical late-time outputs (`v10.1.1-late-time-r4` / `v10.1.1-submission-r2`).

## Construction

We evaluate a one-parameter deformation in the drift test window:

- `H_mod(z; s) = (1-s) H_base(z) + s H_cap(z)`, for `z in [2,5]`
- `H_cap(z) = H0 (1+z) (1-epsilon_cap)`, with `epsilon_cap = 1e-6`
- `s in [0,1)` so `s -> 1` approaches drift `-> 0+` while keeping the sign positive.

Outside the window:

- late-time baseline stays `gsc_transition` up to `z_handoff=5`
- for `z > 5`, we use flat LCDM+rad reference for the early-time segment.

Operational drift condition (FLRW/Sandage-Loeb kinematics):

- `dot(z) = H0(1+z) - H(z)`
- positive drift iff `H(z) < H0(1+z)`

Analytic consequence in a window `[z1,z2]`:

- if `H(z) < H0(1+z)`, then
  `integral_{z1}^{z2} dz/H(z) > (1/H0) ln[(1+z2)/(1+z1)]`.
- For `(z1,z2)=(2,5)`, this gives
  `Delta chi_min = (c/H0) ln 2`.
- At `H0=67.4 km/s/Mpc`, `Delta chi_min ~= 3.08e3 Mpc`.
- Companion sanity helper: `scripts/e2_drift_bound_analytic.py`
  (doc note: `docs/early_time_e2_drift_bound_analytic.md`).

## Representative result (baseline checkpoint)

Checkpoint: `p=0.6`, `z_transition=1.8`, Planck-like early inputs, strict CHW2018 covariance.

- `s=0` (baseline): `chi2_cmb ~= 8.32e4`, `Delta v(z=4,10y) ~= 4.53 cm/s`
- best scanned point (`s=0.995`): `chi2_cmb ~= 1.54e4`, `Delta v(z=4,10y) ~= 0.0227 cm/s`
- all scanned points satisfy `drift_sign_ok=True` (discrete `z={2,3,4,5}` and dense check on `[2,5]`).

Interpretation: under this construction, even near the drift boundary (`Delta v -> 0+`), strict CHW2018 closure remains far from `O(1)` chi2. This is a diagnostic no-go trend for the tested assumptions.

## Artifacts and Repro

- Pre-release tag: `v10.1.1-bridge-e2-drift-constrained-closure-bound-r0`
- Asset zip: `paper_assets_cmb_e2_drift_constrained_closure_bound_r0.zip`
- SHA256: `215d0573a9b4bac4c69051838a781d6c8242fe2822836da795771bfb47e292f2`
- Reproduce:
  - `bash scripts/reproduce_v10_1_e2_drift_constrained_closure_bound.sh --sync-paper-assets`

Outputs:

- `results/diagnostic_cmb_drift_constrained_bound/`
- `paper_assets_cmb_e2_drift_constrained_closure_bound/`
