# Reproducibility: Late‑time pipeline

This document explains how to **reproduce the late‑time results** (fits + figures + tables + manifest)
for the the current framework release under **Option 2 (freeze‑frame measurement model)**.

**Scope of v10.1.x:** late‑time kinematics/observables (roughly 0 ≲ z ≲ 5) and the redshift‑drift
discriminant. Early‑universe observables (CMB acoustic peaks, recombination microphysics, etc.)
are intentionally out of scope for this pipeline.

---

## What this pipeline produces

Running the reproduce script generates a complete, publication‑ready output tree under:

- `results/late_time_fit/`
  - `*_bestfit.json` (best‑fit + χ² breakdown + best nuisance values)
  - `*_top.csv` (top grid points for contour/profiling)
  - `bestfit_summary.csv` (includes AIC/BIC + Δ vs LCDM)
  - `bestfit_summary.tex` (LaTeX table snippet)
  - `manifest.json` (env + git + sha256 of actual inputs used)
  - `figures/` (publication figures)
  - `confidence/` (1D profiles + 2D contours + `intervals.json`)

Optionally (if `--sync-paper-assets` is used), it also produces a **git‑ignored**
paper‑asset staging directory:

- `paper_assets/figures/`
- `paper_assets/tables/`
- `paper_assets/manifest.json`

---

## Canonical release bundle (late-time freeze)

The canonical late-time freeze is published as tag/release `v10.1.1-late-time-r4` and includes a strict
paper-assets snapshot:

- `paper_assets_v10.1.1-late-time-r4.zip`
  - SHA256: `b29d5cb0e30941d2bb0cb4b2930f21a4a219a7e0a8439f7fec82704134cf4823`
  - Contents: `paper_assets/` (`tables/`, `figures/`, `manifest.json`)

Offline verification (recommended after download):

```bash
bash scripts/verify_release_bundle.sh /path/to/paper_assets_v10.1.1-late-time-r4.zip
```

Submission bundle builder (offline-safe, no LaTeX required):

```bash
# Build an arXiv/referee source zip from the canonical assets bundle (preflight verified).
bash scripts/make_submission_bundle.sh /path/to/paper_assets_v10.1.1-late-time-r4.zip
```

By default, it writes `submission_bundle_v10.1.1-late-time-r4.zip` in the current directory.
You can also pass an explicit output path as the second argument.

Canonical pre-release pointer:

- Tag/Release: `v10.1.1-submission-r2`
- Bundle: `submission_bundle_v10.1.1-late-time-r4.zip`
  - SHA256: `fa06a2ce85a7991fa63670eb867a03fda4213989ca981b437e2ae2c5d8c3efe5`

Verify the submission bundle (offline-safe):

```bash
bash scripts/verify_submission_bundle.sh submission_bundle_v10.1.1-late-time-r4.zip
```

Optional: standalone smoke compile from the bundle (runs `pdflatex` if available):

```bash
bash scripts/verify_submission_bundle.sh --smoke-compile submission_bundle_v10.1.1-late-time-r4.zip
```

Referee pack builder (docs + minimal tooling + nested submission bundle; excludes `docs/popular/**`):

```bash
bash scripts/make_referee_pack.sh /path/to/paper_assets_v10.1.1-late-time-r4.zip
```

By default, it writes `referee_pack_v10.1.1-late-time-r4.zip` in the current directory.

Canonical pre-release pointer:

- Tag/Release: `v10.1.1-referee-pack-r7`
- Pack: `referee_pack_v10.1.1-late-time-r4-r7.zip`
  - SHA256: `4faf0f4d5754bcd18c401c709396965229d4da7dc73cd4aa7bec38cebca1a2b0`

Verify the referee pack (offline-safe; also verifies the nested submission bundle structure):

```bash
bash scripts/verify_referee_pack.sh referee_pack_v10.1.1-late-time-r4-r7.zip
```

---

## One‑command reproduction

From the repository root:

```bash
bash scripts/reproduce_v10_1_late_time.sh --with-drift --sync-paper-assets
```

To build the paper PDF (reproduce + sync + compile LaTeX):

```bash
bash scripts/build_paper.sh
```

To reproduce an **opt-in E1.1 strict** bundle (CHW2018 distance priors), without changing the
canonical late-time paper assets:

```bash
bash scripts/reproduce_v10_1_late_time_e1_strict.sh --with-drift --sync-paper-assets
```

To reproduce an **opt-in E1.2 strict (r1)** bundle (CHW2018 distance priors + scoped `r_s(z*)`
calibration; repo-relative manifest), without changing the canonical late-time paper assets:

```bash
bash scripts/reproduce_v10_1_late_time_e1_2_strict.sh --with-drift --sync-paper-assets
```

Other common modes:

```bash
# No drift (H0 typically fixed because SN+BAO with profiled ΔM and free r_d is nearly degenerate in H0)
bash scripts/reproduce_v10_1_late_time.sh --no-drift

# With drift (profiles H0 from drift; may clamp to H0 bounds if requested)
bash scripts/reproduce_v10_1_late_time.sh --with-drift
```

---

## Environment / dependencies

There are two “python tiers”:

### Tier A: Self‑contained the current framework venv (recommended)

Bootstrap:

```bash
bash scripts/bootstrap_venv.sh
```

This creates `.venv` and installs:

* `numpy`
* `scipy`
* `matplotlib`

These are required for:

* SN full covariance χ² (Cholesky solve)
* BAO vector blocks with covariance (e.g. BOSS DR12 6×6, eBOSS Lyα/QSO 2×2)
* contours / figure generation

### Tier B: Fallback to Phase10 venv (if present)

If `.venv` is missing/incomplete, `reproduce_v10_1_late_time.sh` may fall back to:
`B/GSC_v10_8_PUBLICATION_BUNDLE/.venv/bin/python` (with a WARNING).

### Environment flags

* `GSC_FORCE_BOOTSTRAP=1`
  Always run bootstrap before reproduce.
* `GSC_SKIP_BOOTSTRAP=1`
  Never bootstrap; assume env already exists.
* `GSC_REQUIRE_V101_VENV=1`
  Require `.venv` and fail instead of falling back to the Phase10 venv.

---

## Data policy: what is committed vs fetched vs cached

### Committed (in git)

* Canonical CSV datasets used by the pipeline (late‑time safe):

  * SN `mu(z)` CSVs (lightweight, derived products)
  * BAO CSV blocks + small `.cov` matrices where applicable (e.g. 6×6, 2×2)
  * drift forecast CSV(s) (Asimov / mock variants)
* Data README/provenance docs under `data/**/README.md`

### Fetched on demand

Some upstream raw releases may be large and/or have redistribution constraints.
The pipeline uses fetch scripts for these when needed (example: Pantheon+SH0ES).

Typical fetch helper:

```bash
bash scripts/fetch_pantheon_plus_shoes.sh
```

### Cached (git‑ignored)

* SN covariance cache: `*.cov.npz` (created automatically on first load)
* Generated outputs under `results/**`
* Paper assets staging under `paper_assets/**`

---

## Models supported

The late‑time scorecard / fit layer supports:

* `lcdm`
* `gsc_powerlaw`
  A minimal parameterization (e.g. E(z) ~ (1+z)^p) used for stress‑testing the metrology layer.
* `gsc_transition`
  A piecewise late‑time history: LCDM‑like up to `z_transition`, then power‑law above it, with matching at `z_transition`.

**Important:** these are **late‑time history models**, not a full RG‑derived mechanism. They are
intended to:

* validate the Option‑2 measurement translation layer
* quantify how SN/BAO/drift prefer or reject “positive drift for all z” type histories
* produce publication‑ready plots/tables for v10.1.x

Guardrails (where enabled) include:

* checking `ż(z)` sign on a grid up to `z=5` for GSC models.

---

## Likelihood components and nuisance handling

### Supernovae (Pantheon+SH0ES)

- Uses full `STAT+SYS` covariance when `--sn-cov` is provided.
- Nuisance `ΔM` is profiled analytically (still counts as a fit parameter).

If an SN CSV includes `row_full` indexing, the loader can form sub-covariance by slicing
the full covariance matrix:
`C_sub = C[np.ix_(row_full, row_full)]`.

### BAO (late‑time safe)

* Uses ratios over `r_d` (treats `r_d` as a nuisance; profiled analytically where implemented).
* Supports scalar blocks (e.g. DV/rd) and vector blocks:

  * canonical vector order: `[DM/r_d, DH/r_d]`
* Supports covariance blocks (e.g. BOSS DR12 6×6; eBOSS Lyα/QSO 2×2).

#### BAO `r_d` modes (`late_time_fit_grid.py`)

Default behavior keeps `r_d` as a profiled nuisance (late-time safe):

```bash
.venv/bin/python scripts/late_time_fit_grid.py \
  --model lcdm \
  --sn data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv \
  --sn-cov data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov \
  --bao data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv \
  --rd-mode nuisance \
  --out-dir results/late_time_fit
```

E0 early-time bridge mode fixes `r_d` from early parameters (no BAO nuisance profiling):

```bash
.venv/bin/python scripts/late_time_fit_grid.py \
  --model lcdm \
  --sn data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv \
  --sn-cov data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov \
  --bao data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv \
  --rd-mode early \
  --rd-method eisenstein_hu_1998 \
  --omega-b-h2 0.02237 \
  --omega-c-h2 0.1200 \
  --Neff 3.046 \
  --Tcmb-K 2.7255 \
  --out-dir results/late_time_fit
```

`rd-mode=early` is the E0 closure assumption (derived `r_d` only). It does not yet include full
compressed CMB priors or full CMB spectra likelihoods.

### Redshift drift (Δv)

* CSV contract: `dv_cm_s` is the **total** drift over the baseline (not per year).
* The fit layer can profile `H0` from drift (if enabled), with optional clamp to `H0` bounds.
* When profiling a parameter analytically, the parameter is still considered “fit” for AIC/BIC.

### Compressed CMB priors (E1 bridge)

* `late_time_fit_grid.py` supports `--cmb` and optional `--cmb-cov` for compressed priors.
* Current implementation provides prior predictions for `lcdm` only.
* Supported prior keys from model predictions include: `theta_star`, `lA`, `R`, `omega_b_h2`.

Example (E1.1 strict; citation-grade CHW2018 vector+cov):

```bash
.venv/bin/python scripts/late_time_fit_grid.py \
  --model lcdm \
  --sn data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv \
  --sn-cov data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov \
  --bao data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv \
  --rd-mode early \
  --rd-method eisenstein_hu_1998 \
  --omega-b-h2 0.02237 \
  --omega-c-h2 0.1200 \
  --Neff 3.046 \
  --Tcmb-K 2.7255 \
  --cmb data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  --cmb-cov data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  --cmb-mode distance_priors \
  --out-dir results/late_time_fit
```

Note: CHW2018 distance priors require the published covariance (`--cmb-cov`) and must be run with
`--cmb-mode distance_priors` (strict path; the CHW2018-specific `r_s(z*)` stopgap calibration is only applied there).

E1.2 strict (CHW2018) introduces a tiny, explicit calibration factor applied only to `r_s(z*)` in the
CHW2018 distance-priors prediction path (to remove a known bridge-level approximation offset in `lA`).
This is a stopgap until a higher-precision early-time engine is integrated.

Canonical E1.2 strict artifact tag:
* `v10.1.1-bridge-e1.2-strict-r1`

Quick benchmark (Planck-like parameters; prints pulls + `chi2_cmb`):

```bash
.venv/bin/python scripts/cmb_chw2018_benchmark.py
```

Bridge caveat:
Planck distance-prior compression is an approximate bridge input, not a full CMB likelihood in Option 2.

---

## Repro manifest

Each reproduce run writes:

- `results/late_time_fit/manifest.json`

The manifest records:

- git commit / dirty status
- python executable and package versions
- sha256 hashes of the *actual* input files used by the run
- key CLI settings used to generate the outputs

This is the canonical provenance record for the plots/tables used in the paper.

---

## Paper asset sync

To stage assets for inclusion in the canonical LaTeX:

```bash
bash scripts/reproduce_v10_1_late_time.sh --with-drift --sync-paper-assets
```

Assets are copied into:

- `paper_assets/figures/`
- `paper_assets/tables/`
- `paper_assets/manifest.json`

These are git‑ignored by design.

---

## LaTeX inclusion

The canonical LaTeX file remains:

- `GSC_Framework_v10_1_FINAL.tex`

Include the generated table:

```tex
\input{paper_assets/tables/bestfit_summary.tex}
```

Include the generated figures (example names; see `paper_assets/figures/`):

```tex
\includegraphics[width=\linewidth]{figure_A_drift_dv_vs_z.png}
\includegraphics[width=\linewidth]{figure_B_sn_residuals.png}
\includegraphics[width=\linewidth]{figure_C_bao_ratios.png}
```

---

## CI quick smoke

For a fast local check (bootstrap venv + unit tests + synthetic smoke fit/plots/tables/manifest):

```bash
bash scripts/ci_quick.sh
```

A GitHub Actions workflow also exists to run the quick smoke on `main`.

---

## Troubleshooting

### “ModuleNotFoundError: numpy”

You are using a system python instead of the intended venv python.

Fix:

* Run `bash scripts/bootstrap_venv.sh`
* Re‑run the reproduce script

### “Covariance not positive definite / Cholesky fails”

Common causes:

* mismatch between SN CSV rows and covariance dimension
* wrong slicing indices (`row_full`) vs the full covariance ordering
* corrupted/partial download of `.cov`

Fix:

* re‑fetch raw files
* confirm N matches
* confirm `row_full` is 0‑based and in `[0, N_full-1]`

### Drift interpretation mistakes (baseline)

The canonical contract is:

* `dv_cm_s` = total Δv over `baseline_years` (not per‑year).

If you want per-year, you must divide explicitly before writing the CSV, or set the script to do so.

---

## What is intentionally NOT solved here

This pipeline is late‑time only; it does not attempt:

* early‑universe freeze‑frame microphysics (recombination, sound horizon derivation in Option 2)
* full CMB likelihoods / full perturbation treatment in freeze‑frame measurement language

Those are roadmap items beyond v10.1.x.
