# Early-Time E2 Closure Status (Phase 2)

## Target
E2 closure asks whether we can satisfy both constraints in one late-time history family:
- positive redshift drift in `z ~ 2..5`
- acceptable compressed-CMB distance priors (`R`, `lA`, `theta_star` aliases)

## Reproducible Harness
Use `scripts/phase2_e2_scan.py`.

It evaluates parameter points and writes:
- `e2_scan_points.csv` (all sampled points)
- `e2_scan_points.jsonl` (stream-friendly per-point records with `chi2_parts`)
- `e2_scan_summary.json` (counts + best points)
- optional per-point drift metrics in JSONL (`drift.z_list`, `drift.z_dot`, `drift.dv_cm_s_per_yr`, `drift.min_z_dot`)

The harness is intentionally lightweight and does **not** replace a full CMB likelihood.

## Scope note: CMB distance priors vs full spectra

Phase-2 E2 currently uses compressed CMB priors / shift-parameter diagnostics as
an operational bridge. It is not a full TT/TE/EE peak-level spectra fit and does
not replace Boltzmann-class anisotropy pipelines. For canonical scope and
roadmap boundaries, see `docs/project_status_and_roadmap.md`.

## Operational note: clean source snapshots (M74)
When sharing reproducible source state for E2 diagnostics, do not zip the full
working directory. Export a deterministic tracked-files snapshot from git:

```bash
python3 scripts/make_repo_snapshot.py \
  --ref v10.1.1-phase2-m73 \
  --profile lean \
  --out GSC_source_phase2_m73.zip
```

This avoids large local artifacts (`.git`, `.venv`, `results/`,
`paper_assets_*`, OS zip cruft) while preserving an exact committed source
snapshot.

For routine sharing, Phase-2 M75 adds a slimmer profile and a bloat-audit tool:

```bash
python3 scripts/make_repo_snapshot.py \
  --profile slim \
  --snapshot-format tar.gz \
  --output gsc_snapshot_slim.tar.gz

python3 scripts/audit_worktree_bloat.py \
  --root . \
  --top-n 20
```

Use the audit output to identify oversized local directories before exporting a
snapshot to collaborators.

Phase-2 M76 also redacts machine-local absolute paths in tracked legacy packs
so shared snapshots remain portable and do not leak workstation-specific path
details.

Phase-2 M77 adds a dedicated shareable profile and zip-bloat audit:

```bash
python3 scripts/make_repo_snapshot.py \
  --profile share \
  --snapshot-format zip \
  --output gsc_snapshot_share.zip

python3 scripts/make_repo_snapshot.py \
  --profile share \
  --dry-run \
  --format json

python3 scripts/phase2_e2_audit_zip_bloat.py \
  --zip GSC.zip \
  --top 30
```

Operational rule: do not zip the repository root directly. Use the snapshot
tool so `.git/.venv/results/paper_assets/data` bloat paths are excluded by
policy.

Phase-2 M78 additionally prunes redundant tracked legacy bundle trees (not part
of the active E2 workflow) and adds anti-regression tests so those heavy trees
do not re-enter tracked git state. If legacy packs are needed for historical
reference, use release/tag assets rather than storing extracted bundles in the
repository.

Phase-2 M79 standardizes deterministic share ZIP export as the default way to
send code+docs snapshots:

```bash
python3 scripts/make_repo_snapshot.py \
  --profile share \
  --format zip \
  --out GSC_share.zip
```

If collaborators need both source and a concrete E2 result set, send the share
ZIP plus the selected Phase-2 bundle artifact (not a whole-repo zip).

Worktree hygiene / cleanup (M80):

```bash
python3 scripts/clean_ignored_bloat.py --root . --mode report
python3 scripts/clean_ignored_bloat.py --root . --mode emit_script --script-out cleanup_ignored_bloat.sh
python3 scripts/clean_ignored_bloat.py --root . --mode clean --yes
```

The cleanup helper only targets ignored paths and refuses to delete anything
tracked by git. Use it when local `.venv/results/paper_assets` growth makes
manual archives unexpectedly large.

M95 operational reminder:

- do not zip the worktree directly (`.git/`, `.venv/`, `results/`,
  `paper_assets*/`, `__MACOSX/`, `.DS_Store` can dominate archive size),
- use deterministic share export:
  `python3 scripts/make_repo_snapshot.py --profile share --format zip --out GSC_share.zip`,
- use ignored-bloat cleanup when needed:
  `python3 scripts/clean_ignored_bloat.py --root . --mode report`.

## Sharing results with external reviewers (M100)

For reviewer handoff, prefer one deterministic pack artifact instead of manual
raw-worktree zips. The pack composes a selected bundle, a share-profile repo
snapshot, generated paper-assets, and verify outputs while blocking common
bloat paths (`.git`, `.venv`, `__MACOSX`, `.DS_Store`, legacy packs).

Manual checkout zips can easily become hundreds of MB (observed: ~317 MB from
`.git` ~105 MB, `.venv` ~168 MB, legacy `B/...` ~230 MB plus
`__MACOSX`). Use deterministic share/reviewer-pack tooling instead of raw zips.

```bash
python3 scripts/phase2_e2_make_reviewer_pack.py \
  --bundle /path/to/e2_bundle.zip \
  --outdir reviewer_pack_out \
  --zip-out reviewer_pack.zip
```

## Structure formation proxy (RSD fσ8) during E2 scans (M89)

You can emit additive `rsd_*` fields directly during `phase2_e2_scan.py` runs:

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm --toy \
  --grid H0=67.4 --grid Omega_m=0.315 \
  --rsd-overlay --rsd-ap-correction none
```

When enabled, each record can include `rsd_chi2`, `rsd_sigma8_0_best`,
`rsd_n`, `rsd_dataset_sha256`, and `rsd_overlay_ok` (plus skip reason when
not computed). This is a linear-GR growth proxy and not a full perturbation
treatment.

## Joint CMB+RSD objective during scan (optional, M96)

`phase2_e2_scan.py` keeps CMB-only objective by default (`chi2_total`). For
opt-in joint scoring during scan/refine, use:

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm --toy \
  --grid H0=67.4 --grid Omega_m=0.315 \
  --rsd-overlay \
  --chi2-objective joint \
  --rsd-chi2-field rsd_chi2_total \
  --rsd-chi2-weight 1.0
```

When joint mode is active and RSD data are available, records can include
`chi2_joint_total = chi2_total + rsd_chi2_weight * rsd_chi2_field`. If joint is
requested without `--rsd-overlay`, scan exits with code `2` and marker
`MISSING_RSD_OVERLAY_FOR_JOINT_OBJECTIVE`.

## Joint objective certification in paper-assets bundles (M97)

`phase2_e2_certificate_report.py` now surfaces JOINT-ready summaries when
`chi2_joint_total` is present in eligible rows:

- `best_cmb` (legacy/CMB baseline by `chi2_total`)
- `best_joint` (joint baseline by `chi2_joint_total`)
- additive RSD metadata on the selected joint row (`rsd_chi2_field_used`,
  `rsd_chi2_weight`, transfer/primordial metadata when present)

Monitor path:

```bash
python3 scripts/phase2_e2_live_status.py --input /path/to/merged.jsonl --format json
python3 scripts/phase2_e2_certificate_report.py --jsonl /path/to/merged.jsonl --outdir /tmp/e2_cert
```

Operational note: certificate JOINT blocks are additive and backward-compatible.
Legacy bundles without `chi2_joint_total` remain valid; JOINT blocks are simply
absent.

## Structure paper snippet location (M102)

Phase-2 paper-assets now emit a deterministic structure snippet:
`phase2_sf_fsigma8.{md,tex}`. In bundle/reviewer-pack workflows it is available
under:

- `paper_assets_cmb_e2_closure_to_physical_knobs/snippets/phase2_sf_fsigma8.{md,tex}`
- mirrored into `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/`
  via the `phase2_e2_all` aggregator path.

This snippet is reviewer-facing operational summary output (linear-theory scope),
not a full perturbation/nonlinear structure-formation closure claim.

## Joint candidate selection (CMB + RSD)

For reviewer-safe triage, compare best candidates by compressed-priors CMB
score versus additive joint score:

```bash
python3 scripts/phase2_e2_best_candidates_report.py \
  --input /path/to/merged.jsonl \
  --rank-by joint \
  --format text
```

Joint score is defined as `chi2_total + rsd_chi2` when both terms are
available. If RSD fields are missing, joint ranking is reported as unavailable;
`--rank-by cmb` remains the backward-compatible baseline.

Scope note: this remains a compressed-priors plus linear-growth diagnostic
overlay. It does not replace full TT/TE/EE spectra fitting and does not by
itself close perturbation-level structure formation. See
`docs/project_status_and_roadmap.md`.

## Refine plan emission with joint ranking (CMB + RSD)

When scan records already contain `rsd_*` fields, refine seeds can be ranked by
joint score directly in Pareto report emission:

```bash
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /path/to/merged.jsonl.gz \
  --rank-by joint \
  --emit-refine-plan /path/to/plan_refine_joint.json
```

Rank modes:
- `--rank-by cmb`: rank by `chi2_total` (legacy-safe CMB-only ordering)
- `--rank-by rsd`: rank by RSD chi2 field
- `--rank-by joint`: rank by `chi2_total + rsd_chi2`

If `--rank-by rsd|joint` is requested and no valid RSD chi2 field exists in
eligible rows, the tool exits with code `2` and prints
`MISSING_RSD_CHI2_FIELD` with a hint to run scans with `--rsd-overlay` (or pass
`--rsd-chi2-field` explicitly).

For sigma-origin context linked to early-time roadmap boundaries, see
`docs/sigma_field_origin_status.md` and the FRG flow-table scaffold
(`scripts/phase2_rg_flow_table_report.py`), which is diagnostic-only
and keeps `k(sigma)` as an ansatz-level working identification.

## Sigma-origin RG snippets in Phase-2 paper assets (M98)

When running `phase2_e2_make_paper_assets.py --mode all`, Phase-2 assets now
include deterministic RG status snippets:
`phase2_rg_flow_table.{md,tex}` and `phase2_rg_pade_fit.{md,tex}`.
These are reviewer-facing diagnostics and remain claim-safe status summaries,
not first-principles FRG derivations.

## RSD overlay sanity check (optional, M87)

You can add an optional linear-growth `fσ8` overlay to Phase-2 Pareto triage.
This is a claim-safe sanity channel, not a full perturbation/LSS likelihood.

```bash
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /path/to/merged.jsonl \
  --out-dir /tmp/gsc_e2_pareto_rsd \
  --rsd-overlay on \
  --rsd-data data/structure/fsigma8_gold2017_plus_zhao2018.csv \
  --rsd-weight 1.0
```

For distributed packs generated by `phase2_e2_jobgen.py`, run:

```bash
./rsd_overlay.sh
```

This writes `pareto_rsd_overlay.txt` and `pareto_rsd_overlay.json` in the pack
directory.

Supported samplers:
- `--sampler grid` (deterministic Cartesian grid; default)
- `--sampler random` (seeded uniform sampling in bounds)
- `--sampler halton` (deterministic low-discrepancy sequence; optional skip/scramble)
- `--sampler lhs` (deterministic Latin hypercube; center-in-stratum mode)
- `--sampler mh` (seeded Metropolis-Hastings with bounded proposals)
- `--sampler mh_adaptive` (deterministic adaptive random-walk MH with bounded transforms and target acceptance control)

Integration method (M20):
- `--integrator trap` (default, backward-compatible)
- `--integrator adaptive_simpson` (stdlib adaptive quadrature)

Sampling strategy recommendation:
- use `halton` or `lhs` first for broad, space-filling exploration in higher dimensions
- use `mh` or `mh_adaptive` afterwards to locally refine around promising points/bounds
- for repeated MCMC runs, prefer `--resume-mode cache` to reuse previous evaluations while keeping full chain emission

High-dimensional MCMC workflow (M27):
- `mh_adaptive` keeps proposals in-bounds via logit transforms and adapts proposal scales (`--mh-target-accept`, `--mh-adapt-every`, `--mh-init-scale`)
- multi-chain sampling: `--mh-chains K`
- deterministic with fixed `--seed`
- testing-only fast mode: `--toy` (no CMB dataset load; stdlib-only objective)

Example (toy, fast CI/debug):

```bash
python3 scripts/phase2_e2_scan.py \
  --toy \
  --model lcdm \
  --sampler mh_adaptive \
  --mh-chains 2 --mh-steps 30 --mh-burnin 10 --mh-thin 2 \
  --mh-target-accept 0.25 --mh-adapt-every 25 --mh-init-scale 0.1 \
  --resume-mode cache \
  --grid H0=60:75 \
  --grid Omega_m=0.2:0.4 \
  --out-dir /tmp/gsc_e2_mh_adaptive_toy
```

Integrator note:
- keep `trap` for strict backward-compatible comparisons with earlier runs
- use `adaptive_simpson` for numerics cross-checks while preserving the same model assumptions

## Exploratory Family: `dip_bump_window` (M21)
Phase2 M21 adds an exploratory history family that applies a multiplicative deformation
to a flat-`LCDM` baseline:

- `H(z) = H_base(z) * f(z)`
- `f(z) = 1 - A_dip * W(z; z_dip_lo, z_dip_hi, w) + A_bump * W(z; z_bump_lo, z_bump_hi, w)`

with smooth logistic windows `W` and fixed default windows (`dip: 2..5`, `bump: 5..1100`).
This family is meant to test a broader closure space: dip in the quasar drift window and
compensating high-z bump for CMB-distance integrals.

Important: this is a scan-space expansion, not a claim that E2 is solved.

Example:

```bash
python3 scripts/phase2_e2_scan.py \
  --model dip_bump_window \
  --sampler halton --n-samples 64 --seed 42 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid A_dip=0.05:0.85 \
  --grid A_bump=0.0:3.0 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --require-positive-drift \
  --out-dir /tmp/gsc_e2_dip_bump_scan
```

## Exploratory Family: `logh_two_window` (M49)
M49 adds a composite deformation in `log H` with two independent windows:

- `delta_logH(z) = tw1_a * W1(z) + tw2_a * W2(z)`
- `H(z) = H_base(z) * exp(delta_logH(z))`
- each `W` is Gaussian in `x=ln(1+z)`:
  `W(z; zc, w) = exp(-0.5 * ((ln(1+z)-ln(1+zc))/w)^2)`

This expands scan flexibility with a mid-z window (`tw1_*`) and a high-z window
(`tw2_*`) while preserving positivity of `H(z)` by construction.

Recommended default bounds:

- mid-z window (drift-relevant):
  `tw1_zc in [1.5, 8.0]`, `tw1_w in [0.05, 0.80]`, `tw1_a in [-1.0, 1.0]`
- high-z window (recombination/drag compensation):
  `tw2_zc in [50.0, 2000.0]`, `tw2_w in [0.05, 1.50]`, `tw2_a in [-1.0, 1.0]`

Minimal scan example:

```bash
python3 scripts/phase2_e2_scan.py \
  --model logh_two_window \
  --sampler halton --n-samples 64 --seed 42 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid tw1_zc=1.5:8.0 \
  --grid tw1_w=0.05:0.80 \
  --grid tw1_a=-1.0:1.0 \
  --grid tw2_zc=50.0:2000.0 \
  --grid tw2_w=0.05:1.50 \
  --grid tw2_a=-1.0:1.0 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --out-dir /tmp/gsc_e2_two_window_scan
```

Distributed workflow remains unchanged:
- emit plan (`phase2_e2_pareto_report.py --emit-refine-plan ...`)
- run slices (`phase2_e2_scan.py --plan ... --plan-slice I/N`)
- merge (`phase2_e2_merge_jsonl.py`) and run reports/jobgen/bundle tools.

## Exploratory Family: `spline4_logh` (M50)
M50 adds a knot-based smooth deformation in `log H`:

- coordinate: `x = ln(1+z)`
- fixed knots: `z = 3, 30, 300, 1100` plus anchor `z=0`
- free parameters:
  - `spl4_dlogh_z3`
  - `spl4_dlogh_z30`
  - `spl4_dlogh_z300`
  - `spl4_dlogh_z1100`
- interpolation: piecewise-linear in `x`
- tails:
  - `0 <= z < 3`: interpolate from anchor `(z=0, dlogh=0)` to `z=3`
  - `z > 1100`: hold-last at `spl4_dlogh_z1100`
- final history:
  `H(z) = H_base(z) * exp(dlogh(z))`

Recommended default bounds:

- `spl4_dlogh_z3 in [-1.0, 1.0]`
- `spl4_dlogh_z30 in [-1.0, 1.0]`
- `spl4_dlogh_z300 in [-1.0, 1.0]`
- `spl4_dlogh_z1100 in [-1.0, 1.0]`

Interpretation note: values are in `delta(log H)`, so `±1` corresponds to a
multiplicative factor of `exp(±1)` in `H(z)`.

Toy smoke:

```bash
python3 scripts/phase2_e2_scan.py \
  --toy \
  --deformation spline4_logh \
  --sampler random --n-samples 8 --seed 7 \
  --grid H0=66:69 \
  --grid Omega_m=0.28:0.34 \
  --grid spl4_dlogh_z3=-1:1 \
  --grid spl4_dlogh_z30=-1:1 \
  --grid spl4_dlogh_z300=-1:1 \
  --grid spl4_dlogh_z1100=-1:1 \
  --out-dir /tmp/gsc_e2_spline4_toy
```

Scan + plan workflow example:

```bash
python3 scripts/phase2_e2_scan.py \
  --model spline4_logh \
  --sampler halton --n-samples 128 --seed 13 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid spl4_dlogh_z3=-1:1 \
  --grid spl4_dlogh_z30=-1:1 \
  --grid spl4_dlogh_z300=-1:1 \
  --grid spl4_dlogh_z1100=-1:1 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --out-dir /tmp/gsc_e2_spline4_scan
```

## Extended Cosmology Parameter Scan
Phase2 M16 extends the scan space with optional early-time knobs:
- `omega_b_h2`
- `omega_c_h2`
- `N_eff`
- `Y_p` (optional metadata knob in the current compressed-priors path; marked as unused in outputs)

These parameters can be scanned with `--grid` in `grid/random/mh` modes. Optional Gaussian priors can be added with repeatable
`--gaussian-prior NAME=MU,SIGMA`; when omitted, prior penalty is zero (`chi2_parts.priors.chi2 = 0`).

Tiny grid demo with extended knobs:

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm \
  --grid H0=67.4 \
  --grid Omega_m=0.315 \
  --grid omega_b_h2=0.0219,0.02237 \
  --grid N_eff=2.9,3.046 \
  --Y-p 0.245 \
  --gaussian-prior omega_b_h2=0.02237,0.0005 \
  --gaussian-prior N_eff=3.046,0.20 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --omega-c-h2 0.1200 --Tcmb-K 2.7255 \
  --out-dir /tmp/gsc_e2_ext_grid
```

Seeded random scan over expanded bounds:

```bash
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --sampler random --n-samples 64 --seed 42 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid p=0.45:0.85 \
  --grid z_transition=0.8:2.2 \
  --grid omega_b_h2=0.0215:0.0235 \
  --grid omega_c_h2=0.110:0.130 \
  --grid N_eff=2.5:3.7 \
  --grid Y_p=0.22:0.27 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --require-positive-drift \
  --out-dir /tmp/gsc_e2_ext_random
```

## Example Runs
LCDM sanity run (expects good CMB chi2; drift-pass is typically false at high z):

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm \
  --grid H0=67.4 \
  --grid Omega_m=0.315 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --omega-b-h2 0.02237 --omega-c-h2 0.1200 --Neff 3.046 --Tcmb-K 2.7255 \
  --out-dir /tmp/gsc_e2_lcdm
```

GSC transition run with explicit drift requirement:

```bash
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --grid H0=62:72:2 \
  --grid Omega_m=0.28:0.36:0.02 \
  --grid p=0.45:0.85:0.10 \
  --grid z_transition=0.8:2.2:0.35 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --omega-b-h2 0.02237 --omega-c-h2 0.1200 --Neff 3.046 --Tcmb-K 2.7255 \
  --require-positive-drift --drift-z-min 2 --drift-z-max 5 --drift-z-n 61 \
  --out-dir /tmp/gsc_e2_gsc_transition
```

Random sampler smoke (deterministic with seed):

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm \
  --sampler random --n-samples 32 --seed 123 \
  --grid H0=64:72 \
  --grid Omega_m=0.28:0.36 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --omega-b-h2 0.02237 --omega-c-h2 0.1200 --Neff 3.046 --Tcmb-K 2.7255 \
  --out-dir /tmp/gsc_e2_random
```

Adaptive-quadrature smoke (same scan, explicit integrator metadata in JSONL):

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm \
  --sampler random --n-samples 16 --seed 7 \
  --integrator adaptive_simpson \
  --grid H0=64:72 \
  --grid Omega_m=0.28:0.36 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --omega-b-h2 0.02237 --omega-c-h2 0.1200 --Neff 3.046 --Tcmb-K 2.7255 \
  --out-dir /tmp/gsc_e2_adaptive
```

## Numerical error budget fields (M28)
Phase2 M28 extends scan JSONL with additive robustness metadata:

- `recombination_method`, `drag_method`, `recomb_converged`
- `cmb_num_method`
- `cmb_num_n_eval_dm`, `cmb_num_err_dm`
- `cmb_num_n_eval_rs`, `cmb_num_err_rs`
- `cmb_num_n_eval_rs_drag`, `cmb_num_err_rs_drag`
- `cmb_num_rtol`, `cmb_num_atol`

Interpretation:
- these are numerical diagnostics for integration/recombination stability;
- older JSONL artifacts without these fields remain valid and report tools treat
  missing values as optional.

Recombination toggle (diagnostic-only):

- `--recombination fit` (default): fitting-formula path.
- `--recombination peebles3`: lightweight ODE diagnostic path/fallback.
- controls: `--recombination-max-steps`, `--recombination-rtol`, `--recombination-atol`.

This switch is for robustness analysis and does not by itself change claims.

## Numerics robustness cross-check (M28-M29)
To test numerics/recombination sensitivity directly, compare two scan outputs
generated from the same `--plan` points but with different method flags.

Example workflow:

1. Produce (or reuse) a plan with stable `plan_point_id` values.
2. Run scan A and scan B with the same `--plan` and different method choices
   (for example `--integrator trap` vs `--integrator adaptive_simpson`, or
   `--recombination fit` vs `--recombination peebles3`).
3. Compare outputs:

```bash
python3 scripts/phase2_e2_robustness_compare.py \
  --jsonl-a /tmp/gsc_scan_a/e2_scan_points.jsonl \
  --jsonl-b /tmp/gsc_scan_b/e2_scan_points.jsonl \
  --out-tsv /tmp/gsc_scan_compare/robustness_compare.tsv \
  --match-key plan_point_id \
  --preset core
```

Interpretation:
- inspect `max_abs_delta` in the tool summary for `chi2_parts.cmb.chi2` and
  key drift fields;
- larger deltas indicate stronger numerics-method sensitivity and motivate
  tighter tolerances or additional robustness scans.

## Robustness via multi-run aggregation (M30)
When the parameter space grows, pairwise checks are often not enough. M30 adds
`phase2_e2_robustness_aggregate.py` to aggregate robustness across 2+ scan runs
that share `params_hash` points.

Suggested workflow:

1. Run the same plan under different numerics/recombination settings.
2. Aggregate across runs (strict intersection recommended):

```bash
python3 scripts/phase2_e2_robustness_aggregate.py \
  --jsonl /tmp/gsc_scan_trap/e2_scan_points.jsonl \
  --jsonl /tmp/gsc_scan_adaptive/e2_scan_points.jsonl \
  --jsonl /tmp/gsc_scan_peebles/e2_scan_points.jsonl \
  --label trap --label adaptive --label peebles3 \
  --outdir /tmp/gsc_robustness_m30 \
  --require-common \
  --max-span-chi2-cmb 1.0 \
  --max-span-chi2-total 1.0
```

3. Optional: emit a refine plan from robust candidates:

```bash
python3 scripts/phase2_e2_robustness_aggregate.py \
  --jsonl /tmp/gsc_scan_trap/e2_scan_points.jsonl \
  --jsonl /tmp/gsc_scan_adaptive/e2_scan_points.jsonl \
  --outdir /tmp/gsc_robustness_m30 \
  --require-common \
  --emit-refine-plan robust_refine_plan.json
```

Interpretation:
- `robust_ok=true` means spans stay within configured thresholds and consensus checks pass;
- this is a diagnostics filter for numerical/method sensitivity, not a new physics claim.

## Robustness-aware Pareto & refine (M31)
M31 connects M30 aggregate diagnostics directly to Pareto selection and refine-plan emission.
Instead of ranking points only by a single scan run, Pareto can now use robust objectives
(`worst` or `mean`) computed across multiple numerics/recombination variants grouped by
`params_hash`.

Workflow:

1. Run scan A and scan B on the same plan (`--plan`) so points share `params_hash`.
2. Build aggregate diagnostics:

```bash
python3 scripts/phase2_e2_robustness_aggregate.py \
  --jsonl /tmp/gsc_scan_a/e2_scan_points.jsonl \
  --jsonl /tmp/gsc_scan_b/e2_scan_points.jsonl \
  --outdir /tmp/gsc_robustness_m31 \
  --require-common
```

3. Build robustness-aware Pareto and emit refine plan:

```bash
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_scan_a/e2_scan_points.jsonl \
  --robustness-aggregate /tmp/gsc_robustness_m31/robustness_aggregate.csv \
  --robustness-objective worst \
  --robustness-min-runs 2 \
  --emit-refine-plan /tmp/gsc_robustness_m31/refine_plan_robust.json \
  --out-dir /tmp/gsc_robustness_m31/pareto
```

4. Re-run scan on robust refine points:

```bash
python3 scripts/phase2_e2_scan.py \
  --plan /tmp/gsc_robustness_m31/refine_plan_robust.json \
  --resume \
  --jobs 4 \
  --out-dir /tmp/gsc_robustness_m31/refine_run
```

Practical note:
- this loop helps avoid selecting points that look good only under one numerics/method setup;
- it is a diagnostics/stability workflow, not a standalone closure claim.

## Sensitivity-guided refine (M33)
M33 adds an optional refine strategy that uses local parameter sensitivity to propose
next points around Pareto/near-Pareto anchors.

It is a deterministic search heuristic for efficiency; it is not a physics proof.

Generate a sensitivity-guided plan:

```bash
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --emit-refine-plan /tmp/gsc_e2_iter0/refine_plan_sensitivity.json \
  --refine-strategy sensitivity \
  --refine-target-metric chi2_cmb \
  --refine-neighbors 64 \
  --refine-top-params 3 \
  --refine-step-frac 0.03 \
  --refine-direction both \
  --out-dir /tmp/gsc_e2_iter0/reports
```

Evaluate plan points with resume + parallel workers:

```bash
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --plan /tmp/gsc_e2_iter0/refine_plan_sensitivity.json \
  --resume \
  --jobs 8 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --out-dir /tmp/gsc_e2_iter0
```

## Reproducible Phase-2 E2 workflow (one-button, M34)
M34 adds a stdlib-only orchestration wrapper:
`scripts/phase2_e2_reproduce.py`.

It runs a deterministic end-to-end workflow:
- base scan
- base reports
- optional refine-plan emission + refine scan
- canonical combined JSONL (dedupe + sort by `params_hash`)
- final reports
- manifest with SHA256 checksums (`manifest.json`)

Base-only example:

```bash
python3 scripts/phase2_e2_reproduce.py \
  --outdir /tmp/gsc_e2_m34_base \
  --scan-args "--model gsc_transition --sampler halton --n-samples 128 --seed 42 --grid H0=62:72 --grid Omega_m=0.28:0.36 --grid p=0.45:0.85 --grid z_transition=0.8:2.2 --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov --cmb-bridge-z 5.0"
```

Base + refine example:

```bash
python3 scripts/phase2_e2_reproduce.py \
  --outdir /tmp/gsc_e2_m34_refine \
  --emit-refine-plan \
  --jobs 8 \
  --scan-args "--model gsc_transition --sampler lhs --n-samples 160 --seed 42 --grid H0=62:72 --grid Omega_m=0.28:0.36 --grid p=0.45:0.85 --grid z_transition=0.8:2.2 --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov --cmb-bridge-z 5.0"
```

Result bundle (deterministic naming):
- base/refine/combined JSONL artifacts
- report files for base and combined stages
- emitted refine plan (when enabled)
- `manifest.json` with checksumed artifacts/inputs for reproducibility

For fast CI/debug smoke tests:

```bash
python3 scripts/phase2_e2_reproduce.py \
  --outdir /tmp/gsc_e2_m34_toy \
  --toy \
  --emit-refine-plan \
  --scan-args "--model lcdm --sampler random --n-samples 10 --grid H0=60:75 --grid Omega_m=0.2:0.4"
```

Toy mode supports real plan/resume refine execution (no placeholder refine artifacts):

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm \
  --toy \
  --plan /tmp/gsc_e2_m34_toy/e2_refine_plan.json \
  --resume \
  --jobs 2 \
  --out-dir /tmp/gsc_e2_m34_toy/refine_eval
```

Pareto/tradeoff post-processing from one or more JSONL files:

```bash
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_e2_gsc_transition/e2_scan_points.jsonl \
  --top-k 20 \
  --show-params omega_b_h2,omega_c_h2,N_eff,Y_p \
  --out-dir /tmp/gsc_e2_gsc_transition/pareto
```

This writes:
- `pareto_summary.json`
- `pareto_frontier.csv`
- `pareto_top_positive.csv`
- `pareto_report.md`

## Refine workflow (M26)
M26 adds a deterministic refine-plan loop so we can iterate without manual range editing:

1. Run a broad scan (`halton`/`lhs`/`random`/`mh`) to produce `e2_scan_points.jsonl`.
2. Emit an explicit refine plan (concrete points, stable hashes, source checksum).
3. Evaluate that plan with resume+parallel support.
4. Re-run pareto/diagnostics/tension reports on the updated JSONL.

Example:

```bash
# Step 1: broad scan (example)
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --sampler halton --n-samples 256 --seed 42 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid p=0.45:0.85 \
  --grid z_transition=0.8:2.2 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --out-dir /tmp/gsc_e2_iter0

# Step 2: emit refine plan
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --emit-refine-plan /tmp/gsc_e2_iter0/refine_plan.json \
  --refine-top-k 25 \
  --refine-n-per-seed 20 \
  --refine-radius-rel 0.05 \
  --refine-sampler lhs \
  --refine-seed 0 \
  --out-dir /tmp/gsc_e2_iter0/reports

# Step 3: evaluate explicit plan points (resume + parallel)
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --resume \
  --jobs 4 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --out-dir /tmp/gsc_e2_iter0
```

## Distributed / Cluster workflow (M36)
For large plans, run deterministic shards with `--plan-slice I/N` and merge JSONL outputs with the stdlib merge tool.

```bash
# Step 1: produce refine plan as usual
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --emit-refine-plan /tmp/gsc_e2_iter0/refine_plan.json \
  --out-dir /tmp/gsc_e2_iter0/reports

# Step 2: run shard slices (example N=8)
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --plan-slice 0/8 \
  --jobs 4 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --out-dir /tmp/gsc_e2_iter0/shard_0

python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --plan-slice 7/8 \
  --jobs 4 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --out-dir /tmp/gsc_e2_iter0/shard_7

# Step 3: deterministic merge (dedupe by params_hash; canonicalize plan_slice_* by default)
python3 scripts/phase2_e2_merge_jsonl.py \
  /tmp/gsc_e2_iter0/shard_*/e2_scan_points.jsonl \
  --out /tmp/gsc_e2_iter0/merged/e2_scan_points.jsonl \
  --report-out /tmp/gsc_e2_iter0/merged/e2_merge_report.json

# Step 4: continue with reports/manifest
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_e2_iter0/merged/e2_scan_points.jsonl \
  --out-dir /tmp/gsc_e2_iter0/merged/reports
python3 scripts/phase2_e2_make_manifest.py \
  --outdir /tmp/gsc_e2_iter0/merged \
  --artifact e2_scan_points.jsonl \
  --artifact e2_merge_report.json
```

## One-command bundle (M37)
M37 adds a stdlib-only orchestration entrypoint:
`scripts/phase2_e2_bundle.py`.

It turns shard JSONL inputs into one canonical bundle directory:
- deterministic merged JSONL (`merged.jsonl`)
- key reports (`pareto`, diagnostics, CMB tension, sensitivity)
- optional refine plan emission via Pareto
- deterministic `bundle_meta.json` + `manifest.json` with SHA256 checksums

Example (shards directory -> full bundle):

```bash
python3 scripts/phase2_e2_bundle.py \
  --in /tmp/gsc_e2_iter0/shards \
  --outdir /tmp/gsc_e2_iter0/bundle \
  --emit-refine-plan \
  --plausibility any
```

Example (explicit steps, strict mode):

```bash
python3 scripts/phase2_e2_bundle.py \
  --in /tmp/gsc_e2_iter0/shard_0/e2_scan_points.jsonl \
  --in /tmp/gsc_e2_iter0/shard_1/e2_scan_points.jsonl \
  --outdir /tmp/gsc_e2_iter0/bundle_strict \
  --steps merge,pareto,diagnostics,tension,sensitivity,manifest,meta \
  --strict
```

Optional robustness hooks:
- provide both `--robustness-a ...` and `--robustness-b ...` to run
  `robustness_compare`/`robustness_aggregate` inside the bundle flow.
- without these inputs, robustness steps are skipped and recorded in `bundle_meta.json`.

## Verifying E2 bundles (M38)
Phase2 M38 adds an offline stdlib verifier:
`scripts/phase2_e2_verify_bundle.py`.

It validates manifest consistency and SHA256 hashes for all listed artifacts, for
either archive bundles (`.zip`, `.tar`, `.tar.gz`, `.tgz`) or unpacked bundle
directories.

Verify an archive:

```bash
python3 scripts/phase2_e2_verify_bundle.py \
  --bundle /tmp/gsc_e2_iter0/e2_bundle.tar.gz
```

Verify an unpacked directory:

```bash
python3 scripts/phase2_e2_verify_bundle.py \
  --bundle /tmp/gsc_e2_iter0/bundle_dir
```

Notes:
- This verifies internal integrity (manifest + per-file SHA256).
- It does not by itself prove publisher authenticity; for distribution, publish
  the SHA256 of the whole bundle file via an independent trusted channel.

## Diagnostics report tool (M19)
Use the stdlib-only diagnostics tool to quantify tradeoffs and no-go envelopes on top of scan JSONL artifacts:

```bash
python3 scripts/phase2_e2_diagnostics_report.py \
  --jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --outdir /tmp/gsc_e2_iter0/diagnostics
```

Outputs:
- `e2_diagnostics_summary.md`
- `e2_best_points.csv`
- `e2_tradeoff_envelope.csv`
- `e2_param_correlations.csv`

Interpretation quick notes:
- `require_drift` envelope rows answer: best achievable chi2 under drift constraints.
- `require_chi2` envelope rows answer: best achievable drift under chi2 constraints.

## Sensitivity / Correlation Report (M32)
Phase2 M32 adds a stdlib-only post-processing tool:
`scripts/phase2_e2_sensitivity_report.py`.

Purpose:
- quantify which parameter knobs correlate most strongly with chi2 and drift metrics
- support structured diagnostics for E2 closure tension without changing model claims

Baseline usage:

```bash
python3 scripts/phase2_e2_sensitivity_report.py \
  --in-jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --out-md /tmp/gsc_e2_iter0/sensitivity/sensitivity.md \
  --out-csv /tmp/gsc_e2_iter0/sensitivity/sensitivity.csv
```

Drift-positive filter:

```bash
python3 scripts/phase2_e2_sensitivity_report.py \
  --in-jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --require-drift-positive drift_z_min \
  --out-md /tmp/gsc_e2_iter0/sensitivity/sensitivity_drift_pos.md
```

Plausibility-only subset:

```bash
python3 scripts/phase2_e2_sensitivity_report.py \
  --in-jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --plausibility plausible_only \
  --out-md /tmp/gsc_e2_iter0/sensitivity/sensitivity_plausible.md
```

Explicit metrics + quantile trends:

```bash
python3 scripts/phase2_e2_sensitivity_report.py \
  --in-jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --metrics chi2_total,chi2_parts.cmb_priors,drift_z_min \
  --quantile-metric chi2_parts.cmb_priors \
  --out-md /tmp/gsc_e2_iter0/sensitivity/sensitivity_explicit.md \
  --out-json /tmp/gsc_e2_iter0/sensitivity/sensitivity_explicit.json
```

## CMB tension profiling (E2-C sensitivity, M22)
Phase2 M22 adds per-sample CMB tension diagnostics in scan JSONL:
- `cmb_pred`: predicted `R`, `lA`, `omega_b_h2` from the same CMB-priors compute path
- `cmb_tension`: multiplicative scaling diagnostics and sigma-diagonal residuals

Interpretation:
- `delta_D_pct` approximates the `D_M` scaling required to match `R`.
- `delta_rs_pct` approximates the `r_s` scaling required (after `R`-matching) to match `lA`.
- These are diagnostic sensitivity metrics only, not closure claims or new physics claims.

Generate the M22 report from one or more scan outputs:

```bash
python3 scripts/phase2_e2_cmb_tension_report.py \
  --indir /tmp/gsc_e2_iter0 \
  --outdir /tmp/gsc_e2_iter0/cmb_tension_report \
  --top-k 25 \
  --require-drift-sign positive
```

The tool writes:
- `cmb_tension_summary.json`
- `cmb_tension_summary.md`
- `cmb_tension_topk.csv`

## E2-B: Microphysics knobs (diagnostic stress test, M23)
Phase2 M23 adds a diagnostic-only microphysics branch for E2 scans. It introduces
effective scaling knobs for:
- `z_star` (`z_star_scale`)
- `r_s(z_star)` (`r_s_scale`)
- `r_d` (`r_d_scale`)

Purpose:
- stress-test whether E2 closure tension could require additional early-time
  microphysics/re-mapping beyond late-time `H(z)` deformations.
- quantify sensitivity, not claim a resolved model.

Important:
- this is a diagnostic branch only;
- it does not upgrade/strengthen the current framework scientific claims;
- defaults remain backward-compatible (`--microphysics none` => all scales = 1.0).

Example (knobs mode):

```bash
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --sampler halton --n-samples 64 --seed 42 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid p=0.45:0.85 \
  --grid z_transition=0.8:2.2 \
  --microphysics knobs \
  --z-star-scale-min 0.99 --z-star-scale-max 1.01 \
  --r-s-scale-min 0.97 --r-s-scale-max 1.03 \
  --r-d-scale-min 0.97 --r-d-scale-max 1.03 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --require-positive-drift \
  --out-dir /tmp/gsc_e2_microphysics
```

## M24: Microphysics plausibility contract
Phase2 M24 adds a machine-readable plausibility audit for microphysics knobs in
every E2 scan JSONL row.

Per-sample fields:
- `microphysics_knobs`: normalized knob values (`z_star_scale`, `r_s_scale`, `r_d_scale`)
- `microphysics_plausible_ok`: boolean
- `microphysics_penalty`: non-negative score (0 inside plausible ranges)
- `microphysics_max_rel_dev`: max relative deviation from defaults
- `microphysics_notes`: deterministic notes for knobs outside plausible ranges

Interpretation:
- a low-chi2 point with high `microphysics_penalty` is not a closure claim;
  it is a diagnostic indicator that the tested family may require less-plausible
  effective early-time remapping.
- `--microphysics none` remains backward-compatible and reports zero penalty.

## M25: Report filtering by microphysics plausibility
Phase2 M25 adds report-level plausibility filtering so E2 tradeoff tables can be
split between:
- all scanned points (`--plausibility any`, default)
- only points with `microphysics_plausible_ok=true` (`--plausibility plausible_only`)

Example (Pareto over plausible-only subset):

```bash
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --plausibility plausible_only \
  --top-k 25 \
  --out-dir /tmp/gsc_e2_iter0/pareto_plausible
```

Diagnostics now also summarize plausibility counts and compare best-overall vs
best-plausible candidates:

```bash
python3 scripts/phase2_e2_diagnostics_report.py \
  --jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --outdir /tmp/gsc_e2_iter0/diagnostics_plausibility
```

Iterative refine workflow (no manual range editing):

```bash
# 1) broad scan
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --sampler halton --n-samples 128 --seed 42 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid p=0.45:0.85 \
  --grid z_transition=0.8:2.2 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --require-positive-drift \
  --out-dir /tmp/gsc_e2_iter0

# 2) derive refine bounds + seed points from JSONL
python3 scripts/phase2_e2_pareto_report.py \
  --jsonl /tmp/gsc_e2_iter0/e2_scan_points.jsonl \
  --json-summary /tmp/gsc_e2_iter0/pareto/summary.json \
  --emit-refine-bounds /tmp/gsc_e2_iter0/pareto/refine_bounds.json \
  --emit-seed-points /tmp/gsc_e2_iter0/pareto/seed_points.jsonl \
  --refine-top-k 40 \
  --out-dir /tmp/gsc_e2_iter0/pareto

# 3) refine pass using generated bounds/seeds
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --sampler mh --n-steps 96 --seed 43 \
  --grid H0=62:72 \
  --grid Omega_m=0.28:0.36 \
  --grid p=0.45:0.85 \
  --grid z_transition=0.8:2.2 \
  --bounds-json /tmp/gsc_e2_iter0/pareto/refine_bounds.json \
  --seed-points-jsonl /tmp/gsc_e2_iter0/pareto/seed_points.jsonl \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-bridge-z 5.0 \
  --require-positive-drift \
  --out-dir /tmp/gsc_e2_iter1
```

## Distributed scan completeness: plan coverage + rerun plans (M39)
M39 adds a stdlib coverage tool for `phase2_e2_refine_plan_v1` runs:
`scripts/phase2_e2_plan_coverage.py`.

Use it after distributed slicing/merge to audit missing or failed plan points and
emit deterministic rerun plans.

```bash
# 1) run plan slices (example N=4)
python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --plan-slice 0/4 \
  --jobs 4 \
  --resume \
  --out-dir /tmp/gsc_e2_iter0/shard_0

python3 scripts/phase2_e2_scan.py \
  --model gsc_transition \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --plan-slice 3/4 \
  --jobs 4 \
  --resume \
  --out-dir /tmp/gsc_e2_iter0/shard_3

# 2) merge shard JSONL deterministically
python3 scripts/phase2_e2_merge_jsonl.py \
  /tmp/gsc_e2_iter0/shard_0/e2_scan_points.jsonl \
  /tmp/gsc_e2_iter0/shard_1/e2_scan_points.jsonl \
  /tmp/gsc_e2_iter0/shard_2/e2_scan_points.jsonl \
  /tmp/gsc_e2_iter0/shard_3/e2_scan_points.jsonl \
  --out /tmp/gsc_e2_iter0/merged.jsonl

# 3) audit coverage and emit rerun plans for gaps
python3 scripts/phase2_e2_plan_coverage.py \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --out /tmp/gsc_e2_iter0/coverage.json \
  --emit-missing-plan /tmp/gsc_e2_iter0/rerun_missing.json \
  --emit-failed-plan /tmp/gsc_e2_iter0/rerun_failed.json

# optional strict gate (exit 2 for missing, 3 for failed)
python3 scripts/phase2_e2_plan_coverage.py \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --strict
```

Bundle verification can now enforce coverage requirements:

```bash
python3 scripts/phase2_e2_verify_bundle.py \
  --bundle /tmp/gsc_e2_iter0/bundle_dir \
  --plan-coverage ok
```

`--plan-coverage complete` requires no missing points (failed allowed);
`--plan-coverage ok` requires no missing and no failed points.

## Distributed / cluster workflow (jobgen, M40)
M40 adds `scripts/phase2_e2_jobgen.py` to generate a deterministic
job pack from one refine plan for local bash slicing or Slurm arrays.

Example (bash slices):

```bash
python3 scripts/phase2_e2_jobgen.py \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --outdir /tmp/gsc_e2_iter0/jobpack \
  --slices 8 \
  --scheduler bash \
  -- --model gsc_transition --jobs 4

# run slice scripts (one per shard)
bash /tmp/gsc_e2_iter0/jobpack/run_slice_000_of_008.sh
bash /tmp/gsc_e2_iter0/jobpack/run_slice_001_of_008.sh
# ...

bash /tmp/gsc_e2_iter0/jobpack/merge_shards.sh
bash /tmp/gsc_e2_iter0/jobpack/bundle.sh
bash /tmp/gsc_e2_iter0/jobpack/verify.sh
```

Example (Slurm array):

```bash
python3 scripts/phase2_e2_jobgen.py \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --outdir /tmp/gsc_e2_iter0/jobpack_slurm \
  --slices 16 \
  --scheduler slurm_array \
  -- --model gsc_transition --jobs 4

sbatch /tmp/gsc_e2_iter0/jobpack_slurm/slurm_array.sbatch
bash /tmp/gsc_e2_iter0/jobpack_slurm/merge_shards.sh
bash /tmp/gsc_e2_iter0/jobpack_slurm/bundle.sh
bash /tmp/gsc_e2_iter0/jobpack_slurm/verify.sh
```

`jobgen_manifest.json` captures plan checksum, slice count, scheduler mode, and
the scan pass-through args used to build the pack.

## Paper assets generation (M42)
M42 adds `scripts/phase2_e2_make_paper_assets.py` to build deterministic
paper-facing E2 assets directly from scan JSONL (or bundle inputs), without
changing the physics model:

- `paper_assets_cmb_e2_drift_constrained_closure_bound/`
  - `tables/pareto_front.csv`
  - `tables/closure_bound_curve.csv`
  - `tables/best_points_summary.csv`
- `paper_assets_cmb_e2_closure_to_physical_knobs/`
  - `tables/top_models_knobs.csv`
  - `tables/knobs_summary_stats.csv`
  - `tables/knobs_table.tex`
  - `phase2_e2_physical_knobs_report.json`
  - `phase2_e2_physical_knobs.md`
  - `phase2_e2_physical_knobs.tex`

Example (both modes, default ignored paper-assets directories):

```bash
python3 scripts/phase2_e2_make_paper_assets.py \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --mode all \
  --plausibility plausible_only \
  --drift-constraint positive_only \
  --closure-cut 3.0 \
  --top-n 10
```

Drift-closure-bound only:

```bash
python3 scripts/phase2_e2_make_paper_assets.py \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --mode drift_closure_bound \
  --outdir /tmp/gsc_e2_assets_drift \
  --plausibility plausible_only \
  --drift-constraint positive_only
```

Closure-to-knobs only:

```bash
python3 scripts/phase2_e2_make_paper_assets.py \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --mode closure_to_knobs \
  --outdir /tmp/gsc_e2_assets_knobs \
  --plausibility plausible_only \
  --closure-cut 3.0 \
  --top-n 10
```

Interpretation note: these assets quantify the empirical trade-off between drift
constraints and compressed-CMB closure under explicit filters; they are
diagnostic/post-processing outputs.

## Drift-constrained closure bound report (M51)
M51 adds a dedicated deterministic stdlib report:
`scripts/phase2_e2_closure_bound_report.py`.

It quantifies the closure bound with explicit filters:
- best compressed-CMB `chi2_cmb` without drift constraint (within filtered eligible rows),
- best compressed-CMB `chi2_cmb` with drift-positive constraint,
- optional drift-positive + plausible-only best row when plausibility fields are present.

Standalone generation from merged JSONL:

```bash
python3 scripts/phase2_e2_closure_bound_report.py \
  --in-jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --out-dir /tmp/gsc_e2_iter0/closure_bound \
  --status-filter ok_only \
  --plausibility any \
  --drift-filter drift_positive_only \
  --top-n 20
```

Outputs:
- `phase2_e2_closure_bound_report.json`
- `phase2_e2_closure_bound_report.md`
- `phase2_e2_closure_bound_report.tex`
- `phase2_e2_closure_bound_candidates.csv`

Interpretation note: this is a bound within scanned families/ranges under
compressed priors and selected filters; it is not a full-likelihood claim.

## Closure -> physical knobs report (M53)
M53 adds a deterministic stdlib diagnostic report:
`scripts/phase2_e2_physical_knobs_report.py`.

It summarizes how best drift-eligible closure points map to:
- physical cosmology knobs (for available fields such as `omega_b_h2`, `omega_c_h2`, `N_eff`, `Y_p`, `H0`, `Omega_m`),
- CMB microphysics knobs from authoritative `KNOB_SPECS`,
- plausibility/drift-precheck status for selected candidates.

Standalone usage:

```bash
python3 scripts/phase2_e2_physical_knobs_report.py \
  --input-jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --outdir /tmp/gsc_e2_iter0/physical_knobs \
  --status-filter ok_only \
  --plausibility plausible_only \
  --require-drift-precheck \
  --selection best_plausible \
  --top-k 10
```

Outputs:
- `phase2_e2_physical_knobs_report.json`
- `phase2_e2_physical_knobs.md`
- `phase2_e2_physical_knobs.tex`

Paper-assets integration:
- `phase2_e2_make_paper_assets.py --mode closure_to_knobs` now emits the three
  report files above in `paper_assets_cmb_e2_closure_to_physical_knobs/`.
- Canonical snippets are emitted under:
  - `paper_assets_cmb_e2_closure_to_physical_knobs/snippets/phase2_e2_physical_knobs.tex`
  - `paper_assets_cmb_e2_closure_to_physical_knobs/snippets/phase2_e2_physical_knobs.md`

Interpretation note: this is a diagnostic mapping of scanned closure candidates
to effective knob shifts and plausibility flags, not a standalone microphysics claim.

## Best-candidates table snippet (M65)
M65 adds a deterministic stdlib report:
`scripts/phase2_e2_best_candidates_report.py`.

It builds a ranked top-N table from eligible records (`chi2_total` ascending,
stable tie-breaks) with status/plausibility filters aligned with Phase-2 report
semantics.

Standalone usage on merged JSONL (or shard directories/bundles):

```bash
python3 scripts/phase2_e2_best_candidates_report.py \
  --input /tmp/gsc_e2_iter0/merged.jsonl \
  --status-filter ok_only \
  --plausibility any \
  --top-n 10 \
  --format text \
  --json-out /tmp/gsc_e2_iter0/best_candidates.json \
  --md-out /tmp/gsc_e2_iter0/phase2_e2_best_candidates.md \
  --tex-out /tmp/gsc_e2_iter0/phase2_e2_best_candidates.tex
```

Paper-assets integration (`phase2_e2_make_paper_assets.py --mode closure_to_knobs`):
- report files:
  - `phase2_e2_best_candidates_report.json`
  - `phase2_e2_best_candidates.md`
  - `phase2_e2_best_candidates.tex`
- canonical snippets:
  - `paper_assets_cmb_e2_closure_to_physical_knobs/snippets/phase2_e2_best_candidates.md`
  - `paper_assets_cmb_e2_closure_to_physical_knobs/snippets/phase2_e2_best_candidates.tex`

Interpretation note: this is a pipeline-output ranking snapshot under selected
filters and compressed-priors diagnostics; it is not a standalone physics claim.

## Drift comparison snippet (M68)
M68 adds a deterministic stdlib drift-table report:
`scripts/phase2_e2_drift_table_report.py`.

It reports selected-redshift Sandage-Loeb drift values using:
- LCDM baseline (`H0=67.4`, `Omega_m=0.315`, `Omega_L=0.685` by default),
- best eligible E2 candidate (`chi2_total` minimum under status filter),
- best eligible plausible candidate.

Standalone usage:

```bash
python3 scripts/phase2_e2_drift_table_report.py \
  --input /tmp/gsc_e2_iter0/merged.jsonl \
  --eligible-status ok_only \
  --plausibility-mode also_report_best_plausible \
  --years 10 \
  --z 2 --z 3 --z 4 --z 5 \
  --format json \
  --json-out /tmp/gsc_e2_iter0/phase2_e2_drift_table_report.json \
  --emit-md /tmp/gsc_e2_iter0/phase2_e2_drift_table.md \
  --emit-tex /tmp/gsc_e2_iter0/phase2_e2_drift_table.tex
```

Paper-assets integration (`phase2_e2_make_paper_assets.py --mode drift_closure_bound`):
- report files:
  - `phase2_e2_drift_table_report.json`
  - `phase2_e2_drift_table.md`
  - `phase2_e2_drift_table.tex`
- canonical snippets:
  - `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_drift_table.md`
  - `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_drift_table.tex`

Interpretation note: this is a history-only drift diagnostic summary from pipeline
outputs (compressed-priors workflow context), not a standalone closure claim.

## CMB tension snippet (M69)
M69 adds deterministic CMB compressed-priors tension snippets from:
`scripts/phase2_e2_cmb_tension_report.py`.

The snippet focuses on the selected best-eligible record (and best-eligible
plausible record when different) and reports prior-wise pulls in a compact table.

Standalone usage:

```bash
python3 scripts/phase2_e2_cmb_tension_report.py \
  --input /tmp/gsc_e2_iter0/merged.jsonl \
  --outdir /tmp/gsc_e2_iter0/cmb_tension \
  --emit-snippets \
  --snippets-outdir /tmp/gsc_e2_iter0/cmb_tension
```

Paper-assets integration (`phase2_e2_make_paper_assets.py --mode drift_closure_bound`):
- report files:
  - `cmb_tension_summary.json`
  - `cmb_tension_summary.md`
  - `cmb_tension_topk.csv`
  - `phase2_e2_cmb_tension.md`
  - `phase2_e2_cmb_tension.tex`
- canonical snippets:
  - `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_cmb_tension.md`
  - `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_cmb_tension.tex`

Interpretation note: pulls are shown against marginal sigma per prior; the total
CMB chi2 remains the full-covariance quantity when available.

## Scan-audit paper snippets (M67)
M67 adds deterministic scan-audit snippets generated from the same bundle/JSONL
inputs used for Phase-2 paper assets. The audit reports operational scan
coverage/status/error breakdown (not physical viability claims).

Generated files under
`paper_assets_cmb_e2_drift_constrained_closure_bound/`:
- `phase2_e2_scan_audit.json`
- `phase2_e2_scan_audit.md`
- `phase2_e2_scan_audit.tex`
- canonical snippet copies:
  - `snippets/phase2_e2_scan_audit.md`
  - `snippets/phase2_e2_scan_audit.tex`

The snippet includes:
- records parsed + invalid-line counts,
- deterministic status counts (`status -> count`),
- deterministic error bucket summary,
- plan coverage summary (`coverage_any`, `coverage_eligible`) when plan metadata
  is available (otherwise marked unknown).

## Paper integration for Phase-2 snippets (M54)
When paper build runs in Phase-2 mode (`build_paper.sh --phase2-e2-bundle ...`),
the gated appendix is now loaded through one deterministic aggregator snippet:

- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.tex`
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.md`

These snippets are generated via `phase2_e2_make_paper_assets.py` and extracted
from a verified E2 bundle. Default paper build (without Phase-2 flag) is unchanged.

## Phase-2 paper snippet aggregation (`phase2_e2_all`, M70)

`phase2_e2_make_paper_assets.py` now builds `phase2_e2_all.{tex,md}` after
emitting individual snippets. The canonical order is fixed and deterministic:

1. `phase2_e2_summary`
2. `phase2_e2_scan_audit`
3. `phase2_e2_best_candidates`
4. `phase2_e2_drift_table`
5. `phase2_e2_cmb_tension`
6. `phase2_e2_closure_bound`
7. `phase2_e2_physical_knobs`

Adding future snippets now requires updates in paper-assets generation and
bundle verify wiring, without changing the main paper source include block.

## Paper assets in bundle workflow (M43)
M43 makes paper-assets generation a first-class optional bundle step.

Standalone assets + snippets:

```bash
python3 scripts/phase2_e2_make_paper_assets.py \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --mode all \
  --emit-snippets \
  --snippets-format both \
  --outdir /tmp/gsc_e2_iter0/paper_assets \
  --overwrite
```

Integrated bundle path:

```bash
python3 scripts/phase2_e2_bundle.py \
  --in /tmp/gsc_e2_iter0/merged.jsonl \
  --outdir /tmp/gsc_e2_iter0/bundle_with_assets \
  --paper-assets snippets \
  --steps merge,pareto,diagnostics,tension,sensitivity,paper_assets,manifest,meta

python3 scripts/phase2_e2_verify_bundle.py \
  --bundle /tmp/gsc_e2_iter0/bundle_with_assets \
  --paper-assets require \
  --plan-coverage complete
```

`paper_assets_manifest.json` (`phase2_e2_paper_assets_manifest_v1`) is emitted
with SHA256 entries for generated tables/snippets and can be verified in bundle
mode with `--paper-assets require`.

M48 adds deterministic E2 summary snippets in drift assets:
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_summary.tex`
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_summary.md`
These summarize status counts and best records (overall/CMB/drift-positive) under
compressed-CMB diagnostics.

M51 also adds closure-bound snippets in drift assets:
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_closure_bound.tex`
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_closure_bound.md`
These are derived from `phase2_e2_closure_bound_report.*` and recorded in
`paper_assets_manifest.json`.

M68 adds drift-comparison snippets in drift assets:
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_drift_table.tex`
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_drift_table.md`
These summarize baseline LCDM drift vs best E2 candidates from the same run inputs.

M69 adds CMB-tension snippets in drift assets:
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_cmb_tension.tex`
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_cmb_tension.md`
These summarize compressed-priors pulls for best eligible/best plausible records.

M70 adds unified paper aggregators in drift assets:
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.tex`
- `paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/phase2_e2_all.md`
These aggregate all canonical Phase-2 snippets in deterministic order for a
single paper include path.

## E2 Certificate (M46)
M46 adds a deterministic stdlib certificate tool:
`scripts/phase2_e2_certificate_report.py`.

The certificate summarizes, in one canonical artifact:
- input provenance (`sha256`, line counts, optional plan metadata),
- status/eligibility counts under explicit filters,
- drift/CMB/plausibility gate counts and top records,
- optional plan-coverage completeness check.

Standalone certificate from merged JSONL:

```bash
python3 scripts/phase2_e2_certificate_report.py \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --outdir /tmp/gsc_e2_iter0/certificate \
  --status-filter ok_only \
  --plausibility plausible_only \
  --cmb-chi2-threshold 4.0 \
  --late-chi2-threshold 10.0 \
  --require-drift positive \
  --top-k 10
```

With plan coverage enforcement:

```bash
python3 scripts/phase2_e2_certificate_report.py \
  --jsonl /tmp/gsc_e2_iter0/merged.jsonl \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --require-plan-coverage complete \
  --outdir /tmp/gsc_e2_iter0/certificate
```

Paper-assets integration:
- `phase2_e2_make_paper_assets.py` now emits `e2_certificate.json` and
  `e2_certificate.md` in each mode directory by default;
- `paper_assets_manifest.json` includes certificate files and checksums.

Interpretation note:
- `n_joint_ok == 0` under explicit thresholds/filters means no joint-eligible
  point was found inside the scanned family/ranges and gates in that run;
- this is an empirical scan artifact, not by itself a proof of new physics.

## Paper build integration from E2 bundle (M47)
M47 adds bundle-to-paper wiring so a local strict paper build can consume a
single Phase-2 E2 bundle artifact.

Verify + extract paper assets from bundle (standalone):

```bash
python3 scripts/phase2_e2_verify_bundle.py \
  --bundle /tmp/gsc_e2_iter0/bundle_with_assets \
  --plan-coverage complete \
  --paper-assets require \
  --extract-paper-assets \
  --extract-root /path/to/GSC
```

Strict paper build directly from bundle:

```bash
bash scripts/build_paper.sh \
  --phase2-e2-bundle /tmp/gsc_e2_iter0/bundle_with_assets \
  --phase2-e2-extract-root /path/to/GSC
```

When `--phase2-e2-bundle` is provided, `build_paper.sh` runs verifier-driven
extraction before LaTeX compilation and enables the optional Phase-2 E2 appendix
via `\GSCWITHPHASE2E2`, loading the auto-generated
`phase2_e2_all.tex` aggregator snippet (which deterministically includes all
canonical Phase-2 snippets in fixed order).

## Drift-precheck gating (M44)
M44 adds an optional history-first skip gate in
`scripts/phase2_e2_scan.py`:

- `--drift-precheck {none,z2_5_positive,z2_5_negative}` (default: `none`)
- fixed precheck nodes: `z = [2, 3, 4, 5]`
- if precheck fails, scan emits a deterministic `status="skipped_drift"` record
  with drift metrics and chi2 sentinels (`1e99`), and skips heavy early-time/CMB
  evaluation for that point.

Single-machine toy example:

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm \
  --toy \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --drift-precheck z2_5_positive \
  --out-dir /tmp/gsc_e2_iter0/precheck_scan
```

Distributed slice flow (jobgen pass-through args):

```bash
python3 scripts/phase2_e2_jobgen.py \
  --plan /tmp/gsc_e2_iter0/refine_plan.json \
  --outdir /tmp/gsc_e2_iter0/jobpack_precheck \
  --slices 8 \
  --scheduler slurm_array \
  --scan-extra-arg --model \
  --scan-extra-arg lcdm \
  --scan-extra-arg --jobs \
  --scan-extra-arg 4 \
  --scan-extra-arg --drift-precheck \
  --scan-extra-arg z2_5_positive

bash /tmp/gsc_e2_iter0/jobpack_precheck/merge_shards.sh
bash /tmp/gsc_e2_iter0/jobpack_precheck/bundle.sh
bash /tmp/gsc_e2_iter0/jobpack_precheck/verify.sh
```

Downstream tools keep chi2-based best-fit selection on `status=="ok"` rows by
default; skipped rows remain useful for plan coverage/accounting.
For Pareto/debug runs, `phase2_e2_pareto_report.py` now defaults to
`--status-filter ok_only`; use `--status-filter any_eligible` only when you
explicitly need to inspect non-`ok` rows with complete metrics.

## Deterministic local optimization (Nelder-Mead, M56)
M56 adds optional deterministic local minimization per refine-plan seed:

- `phase2_e2_scan.py --optimize nelder_mead`
- objective key via `--opt-objective-key` (default: `chi2_total`)
- additive metadata in each optimized point: `refine_meta` (`n_eval`,
  `converged`, `stop_reason`, seed/best objective)

This is a search/diagnostic tool for tightening candidates and no-go checks; it
does not by itself prove closure.

Local example:

```bash
python3 scripts/phase2_e2_scan.py \
  --model lcdm \
  --plan /path/to/refine_plan.json \
  --resume \
  --jobs 4 \
  --optimize nelder_mead \
  --opt-objective-key chi2_total \
  --opt-max-eval 200 \
  --opt-step-frac 0.05 \
  --out-dir /tmp/gsc_e2_opt
```

Distributed/jobgen pass-through example (token-based args):

```bash
python3 scripts/phase2_e2_jobgen.py \
  --plan /path/to/refine_plan.json \
  --outdir /tmp/gsc_e2_jobpack_opt \
  --slices 8 \
  --scheduler slurm_array \
  --scan-extra-arg --model \
  --scan-extra-arg lcdm \
  --scan-extra-arg --optimize \
  --scan-extra-arg nelder_mead \
  --scan-extra-arg --opt-objective-key \
  --scan-extra-arg chi2_total \
  --scan-extra-arg --opt-max-eval \
  --scan-extra-arg 200
```

## Plan identity & distributed invariants (M57)
M57 hardens plan workflows around stable plan identity:

- In `phase2_e2_scan.py --plan ... --resume`, dedupe is keyed by
  `plan_point_id` plus matching `plan_source_sha256` (not by `params_hash`).
- Non-error statuses are treated as completed plan points for resume; `error`
  points are retried on resume.
- `phase2_e2_merge_jsonl.py --dedupe-key auto` now dedupes by
  `plan_point_id+plan_source_sha256` when present, and falls back to
  `params_hash` for legacy/non-plan JSONL.
- Plan source mismatches for the same `plan_point_id` fail merge by default to
  avoid mixing shards from different plans.
- Plan coverage / bundle verify continue to use `plan_point_id`-based accounting.

Distributed optimize remains compatible with slicing/jobgen by passing scan args
as tokens:

```bash
python3 scripts/phase2_e2_jobgen.py \
  --plan /path/to/refine_plan.json \
  --outdir /tmp/gsc_e2_jobpack_opt_m57 \
  --slices 8 \
  --scheduler slurm_array \
  --scan-extra-arg --model \
  --scan-extra-arg lcdm \
  --scan-extra-arg --optimize \
  --scan-extra-arg nelder_mead \
  --scan-extra-arg --opt-objective-key \
  --scan-extra-arg chi2_total \
  --scan-extra-arg --opt-max-eval \
  --scan-extra-arg 200
```

## Monitoring long scans (M58)
Use `phase2_e2_live_status.py` for deterministic progress snapshots during
single-file or distributed shard runs:

```bash
# Aggregated status over a shard directory.
python3 scripts/phase2_e2_live_status.py \
  --input /path/to/jobpack/shards \
  --plan /path/to/jobpack/plan.json \
  --mode summary

# Per-file breakdown + JSON output artifact.
python3 scripts/phase2_e2_live_status.py \
  --input /path/to/jobpack/shards \
  --plan /path/to/jobpack/plan.json \
  --mode by_file \
  --format json \
  --json-out /path/to/jobpack/status.json
```

The report includes deterministic status counts, error summary, best eligible
point(s), and plan coverage (`plan_points_seen_any`, `coverage_any`) when a
plan is provided.

For active writers, enable tail-safe parsing to ignore a single partial trailing
JSONL line (no newline + invalid JSON) while the file is still being written:

```bash
python3 scripts/phase2_e2_live_status.py \
  --input /path/to/jobpack/shards \
  --plan /path/to/jobpack/plan.json \
  --tail-safe \
  --include-slice-summary
```

`--include-slice-summary` adds deterministic per-slice rows (`I/N`) with record
counts, status counts, eligible counts, best eligible chi2, and slice-level
coverage fields when plan matching by `plan_point_id` is available.

Cluster packs generated by `phase2_e2_jobgen.py` now include:
- `status.sh` (uses `--tail-safe --include-slice-summary` by default)
- `watch.sh` (interval loop for repeated snapshots; default 60s)

## Requeue missing/unresolved plan points (M59)
Use `phase2_e2_requeue_plan.py` to derive a deterministic rerun plan from an
existing plan plus shard/merged outputs:

```bash
# Select unresolved points (default): no final record (ok or skipped_*).
python3 scripts/phase2_e2_requeue_plan.py \
  --plan /path/to/jobpack/plan.json \
  --input /path/to/jobpack/shards \
  --select unresolved \
  --output-plan /path/to/jobpack/plan_requeue.json

# Select only errors-only points.
python3 scripts/phase2_e2_requeue_plan.py \
  --plan /path/to/jobpack/plan.json \
  --input /path/to/jobpack/shards \
  --select errors \
  --output-plan /path/to/jobpack/plan_requeue_errors.json \
  --format json \
  --json-out /path/to/jobpack/requeue_status.json
```

Cluster packs now include `requeue.sh` as a wrapper that writes
`plan_requeue.json` with `--select unresolved` by default. The emitted plan
keeps the same refine-plan schema and can be fed back into `phase2_e2_scan.py`
or `phase2_e2_jobgen.py` for targeted reruns.

## Avoiding mixed-plan merges (M60)
`plan_source_sha256` guardrails are now enforced by default in distributed pack
merge/verify steps to prevent accidental mixing of shards from different plan
campaigns.

- `merge_shards.sh` uses:
  `phase2_e2_merge_jsonl.py --plan plan.json --plan-source-policy match_plan`
- `verify.sh` uses:
  `phase2_e2_verify_bundle.py --require-plan-source match_plan`

If mixed shards are present, merge/verify fails deterministically with an
explicit `mixed plan_source_sha256` error and non-zero exit.

Unsafe overrides (manual only; use with caution):

```bash
# Merge without plan-source guardrail (unsafe).
python3 scripts/phase2_e2_merge_jsonl.py \
  shard_a.jsonl shard_b.jsonl \
  --out merged.jsonl \
  --plan-source-policy ignore

# Verify without plan-source guardrail (unsafe).
python3 scripts/phase2_e2_verify_bundle.py \
  --bundle /path/to/bundle_dir \
  --require-plan-source off
```

## Provenance guardrails (`scan_config_sha256`, M61)
Each scan record now carries `scan_config_sha256`, a deterministic hash of the
effective non-volatile scan configuration (`phase2_e2_scan_config_v1`). This
prevents accidental mixing of shards produced with different scan settings even
when the refine plan is the same.

- `phase2_e2_merge_jsonl.py` enforces `--scan-config-sha-policy auto` by default:
  - legacy all-missing values pass,
  - mixed present/missing fails,
  - multiple distinct SHA values fail.
- Cluster packs now use strict checks by default:
  - `merge_shards.sh` passes `--scan-config-sha-policy require`
  - `verify.sh` passes `--require-scan-config-sha 1`
- `phase2_e2_live_status.py` (and pack `./status.sh`) reports one chosen SHA when
  consistent, or emits `MIXED_SCAN_CONFIG_SHA256` when mixed input is detected.

If merge/verify fails due to mixed scan-config values, do not continue with that
bundle: isolate shards from a single campaign/config first, then re-merge.

## Merging huge JSONL safely (M71)
`phase2_e2_merge_jsonl.py` now has a memory-bounded external-sort path for very
large shard sets:

```bash
python3 scripts/phase2_e2_merge_jsonl.py \
  /path/to/shards/*.jsonl \
  --out /tmp/gsc_e2_large/merged.jsonl \
  --external-sort \
  --chunk-records 200000 \
  --tmpdir /tmp/gsc_e2_merge_tmp
```

Notes:
- external-sort keeps deterministic merge semantics (same dedupe/conflict/guard
  policies as in-memory mode);
- `--chunk-records` tunes memory usage vs I/O throughput;
- `--tmpdir` controls where chunk files are written;
- all provenance guardrails remain enforced (`plan_source_sha256`,
  `scan_config_sha256`), so mixed campaigns still fail fast.

Cluster packs now wire this by default in `merge_shards.sh` with env overrides:
- `GSC_MERGE_CHUNK_RECORDS` (default `200000`)
- `GSC_MERGE_TMPDIR` (default `./tmp_merge`)
- `GSC_MERGE_KEEP_TMP=1` for debug retention

## Compressed shard workflow (`.jsonl.gz`, M72)
For very large distributed runs, shard outputs can be gzip-compressed without
changing JSONL record semantics.

- `phase2_e2_scan.py` can write gzip shards when output filename ends with
  `.jsonl.gz` (for example via jobgen `--shards-compress gzip`).
- `phase2_e2_merge_jsonl.py` accepts mixed `.jsonl` and `.jsonl.gz` inputs,
  including in `--external-sort` mode.
- `phase2_e2_live_status.py` scans `.jsonl` and `.jsonl.gz` transparently for
  progress/coverage reporting.

Example jobgen pack with gzip shards:

```bash
python3 scripts/phase2_e2_jobgen.py \
  --plan /tmp/gsc/plan.json \
  --outdir /tmp/gsc/pack \
  --slices 64 \
  --scheduler slurm_array \
  --shards-compress gzip \
  -- --model lcdm --toy
```

Inspect one compressed shard quickly:

```bash
gzip -cd /tmp/gsc/pack/shards/slice_000_of_064/e2_scan_points.jsonl.gz | head
```

## Gzip artifacts end-to-end (`merged.jsonl.gz`, M73)
For gzip shard packs, merged output can stay compressed to reduce disk pressure.

- Jobgen packs now default to `MERGED_JSONL=merged.jsonl.gz` when generated with
  `--shards-compress gzip`.
- Generated `merge_shards.sh`, `status.sh`, `bundle.sh`, and `requeue.sh` all
  use `MERGED_JSONL` consistently; override to plain when needed:
  `MERGED_JSONL=merged.jsonl ./merge_shards.sh`.
- Phase-2 reporting/paper-assets tools accept `.jsonl` and `.jsonl.gz`
  transparently, so merged gzip files can be used directly.

Example direct merge to gzip:

```bash
python3 scripts/phase2_e2_merge_jsonl.py \
  /tmp/gsc/pack/shards/*.jsonl.gz \
  --out /tmp/gsc/pack/merged.jsonl.gz \
  --external-sort --chunk-records 200000
```

## Cataloging multiple runs (M63)
When you have many Phase-2 bundles from different runs/campaigns, use
`phase2_e2_bundle_catalog.py` for a deterministic dashboard across bundles.

Basic summary over a directory of bundles:

```bash
python3 scripts/phase2_e2_bundle_catalog.py \
  --bundle /path/to/bundles_dir
```

Machine-readable JSON output:

```bash
python3 scripts/phase2_e2_bundle_catalog.py \
  --bundle /path/to/bundles_dir \
  --format json \
  --json-out /tmp/e2_bundle_catalog.json
```

Gated checks (coverage + compatibility):

```bash
python3 scripts/phase2_e2_bundle_catalog.py \
  --bundle /path/to/bundles_dir \
  --require-coverage complete \
  --require-same config_sha
```

The catalog is read-only and prefers existing bundle metadata/certificate files
for speed. It reports best eligible points, status totals, coverage (when
available), and compatibility fields (`config_sha`, `plan_source_sha`) so mixed
or non-comparable bundles are easy to detect.

## Selecting a bundle for Phase-2 paper build (M64)
When multiple candidate bundles exist, use deterministic auto-selection before a
Phase-2 paper build.

Selector tool (standalone):

```bash
python3 scripts/phase2_e2_select_bundle.py \
  --input /path/to/bundles/ \
  --select best_plausible \
  --format text
```

Resolve-only through `build_paper.sh` (no LaTeX run):

```bash
bash scripts/build_paper.sh \
  --phase2-e2-bundle-dir /path/to/bundles/ \
  --phase2-e2-bundle-select best_plausible \
  --phase2-e2-resolve-only
```

`build_paper.sh` keeps explicit-bundle precedence:
`--phase2-e2-bundle /path/to/bundle.tar.gz` disables auto-select for that run.

## Reviewer-safe phrasing (M66)
Use wording that stays within the current Phase-2 evidence boundary:

- Say: "Phase-2 E2 uses compressed priors diagnostics; it is not a full CMB
  power-spectrum/peak-level fit."
- Say: "Under tested families/knobs, we do not find a joint region that
  satisfies drift-sign targets and strict compressed-priors closure."
- Say: "This is an open early-time closure problem with reproducible bundle
  evidence (`bundle -> verify -> paper assets`)."
- Avoid: "fits CMB", "consistent with Planck", "solves CMB peaks", or
  equivalent overclaims without explicit compressed-priors/diagnostic context.

Canonical response lines:
- "Current Phase-2 E2 results are compressed-priors diagnostics and do not
  claim peak-level CMB closure."
- "Within tested families/ranges, no joint drift-positive + strict
  compressed-priors closure region has been identified so far."

## Interpreting Outputs
- `n_drift_pass`: number of sampled points with positive drift over the configured window.
- `chi2_parts` (JSONL): structured breakdown per point:
  - `cmb`: chi2 + keys + pull diagnostics (worst key)
  - `drift`: sign check + optional penalty when `--require-positive-drift` is set
  - `invariants`: strict numerics status
- `best_overall`: minimum CMB chi2 among numerically valid points.
- `best_drift_pass`: minimum CMB chi2 among points with `drift_pass=true`.
- `best_drift_fail`: minimum CMB chi2 among points with `drift_pass=false`.

If `best_drift_pass` is `null`, then no point in the tested family/range satisfied both the strict numerics checks and the drift-pass condition.

## M112 robustness and audit hooks (optional)

- Multi-start local optimization is now available for plan refine runs:
  `--opt-multistart K --opt-init random|latin_hypercube|grid --opt-seed N`.
  This is a robustness helper only; default behavior remains unchanged with
  `--opt-multistart 1`.
- Optional BBN-inspired prior term can be enabled with
  `--bbn-prior weak|standard` (default: `none`), adding `chi2_bbn` as an
  additive diagnostic term.
  The current anchors are conservative Gaussian priors on `omega_b_h2`:
  `weak: μ=0.0224, σ=0.0010`, `standard: μ=0.0224, σ=0.00035`
  (`gsc/bbn/priors.py`; BBN deuterium-era anchor values, used here as
  diagnostic priors rather than a standalone BBN likelihood claim; see
  representative BBN summaries such as Cooke et al. 2018 and PDG review tables).
- Optional rs/z* reference audit is available via
  `scripts/phase2_cmb_rs_zstar_reference_audit.py`; this is an audit
  artifact and not a full-spectra validation claim.

## Current Status
Current Phase-2 interpretation remains: under tested deformation families/ranges, E2 tension can persist between a required **history-level** drift-sign behavior and compressed-CMB priors. This is a history-closure tension, not a frame-vs-frame discriminator. This page and script are the canonical reproducible path to confirm (or falsify) that statement for any explicit range/model choice.

## Next Steps
- Extend the tested family with additional early-time knobs (beyond late-time-only H-boost style deformations).
- Revisit freeze-frame mapping for CMB observables on the E2-C branch with stricter early-time derivation.
