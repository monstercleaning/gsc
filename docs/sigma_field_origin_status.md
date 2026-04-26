# Sigma-Field Origin Status

## What is implemented today

- The release uses a phenomenological `sigma(t)` background sector in late-time and bridge diagnostics.
- Scale-identification statements (`k(sigma)` / `k ~ 1/sigma`) are treated as working ansatz choices.
- Current tests focus on reproducible observable consequences (`H(z)`, drift, compressed priors, linear structure diagnostics), not on first-principles derivation of the ansatz.

## What we do not claim

- We do not claim a first-principles FRG/asymptotic-safety derivation of `sigma(t)` in the current framework.
- We do not claim that `k(sigma)` is uniquely derived from a completed RG flow analysis.
- We do not claim that `k_*` scale placement is settled from fundamental theory in this release.

## AS/FRG bridge stance (claim-safe)

- Asymptotic-safety and FRG references are conceptual motivation for the running-coupling picture.
- The current implementation is approximation-first and explicitly labels the mapping as ansatz/working identification.
- Derivation-level support is deferred to future milestones.

## FRG flow-table interface (diagnostic scaffold, M92)

M92 adds a stdlib-only ingestion/report scaffold for external FRG flow outputs:

- input: user-provided CSV with required columns `k,g` and optional `lambda,G,Lambda,notes`
- output: deterministic summary (`k`/`g` ranges, optional `lambda` range, heuristic `k_*` threshold crossing)
- purpose: reproducible interface layer for external flow tables, not a derivation claim

Example minimal CSV header:

```csv
k,g,lambda,notes
```

Example report command:

```bash
python3 scripts/phase2_rg_flow_table_report.py \
  --input frg_flow.csv \
  --k-star-g-threshold 1.0 \
  --format json \
  --json-out frg_flow_report.json
```

Non-claims (explicit):

- This tool does not derive `sigma(t)` from FRG.
- It does not remove the ansatz status of `k(sigma)` in the current release.
- `k_*` from threshold crossing is a diagnostic heuristic, not a fundamental definition.

## Quantitative bridge: Padé `k_*` fit to flow tables (M93)

M93 adds a deterministic Padé-fit report for externally provided flow tables:

- tool: `scripts/phase2_rg_pade_fit_report.py`
- model: `G(k) = G_IR / (1 - (k/k_*)^2)` (pole/Padé ansatz fit)
- method: stdlib-only linearized OLS on `1/G = a + b k^2`
- output: per-file fit status, `G_IR`, `k_*`, and fit-quality diagnostics (`r2`, relative RMSE, max relative error)

Example command:

```bash
python3 scripts/phase2_rg_pade_fit_report.py \
  --input frg_flow.csv \
  --format json \
  --json-out rg_pade_fit_report.json
```

Optional snippet emission:

```bash
python3 scripts/phase2_rg_pade_fit_report.py \
  --input frg_flow.csv \
  --emit-snippets phase2_rg_snippets \
  --mode summary
```

Interpretation notes (claim-safe):

- `k_*` is an exploratory fit parameter tied to the supplied table conventions/units.
- A successful Padé fit is a quantitative bridge check, not a first-principles FRG derivation.
- `k <-> sigma` identification sensitivity remains an open roadmap topic.

## Generated snippets for Phase-2 paper assets (M98)

Phase-2 paper-assets generation now includes deterministic Sigma-origin RG
snippets:

- `phase2_rg_flow_table.{md,tex}`
- `phase2_rg_pade_fit.{md,tex}`

These snippets are produced by `phase2_e2_make_paper_assets.py` in `--mode all`
and are also available directly from the RG report tools via
`--emit-snippets <DIR>`.

Example (direct report tools):

```bash
python3 scripts/phase2_rg_flow_table_report.py --emit-snippets /tmp/rg_snippets
python3 scripts/phase2_rg_pade_fit_report.py --emit-snippets /tmp/rg_snippets
```

Example (integrated paper-assets path):

```bash
python3 scripts/phase2_e2_make_paper_assets.py \
  --jsonl /path/to/merged.jsonl.gz \
  --mode all \
  --outdir /tmp/paper_assets_phase2 \
  --overwrite
```

Scope reminder:
- snippets summarize status-level diagnostics and illustrative fit outputs;
- they do not upgrade the ansatz into a first-principles FRG derivation.

## Open problems / roadmap

- Derive `sigma(t)` dynamics from a first-principles FRG setup.
- Justify or replace the operational `k <-> 1/sigma` identification with a derivation-level map.
- Clarify the physical interpretation and scale-setting logic for `k_*` in a UV-to-IR bridge.
- Connect derivation-level sigma-sector results to early-time CMB and perturbation-level structure tests.

## Pointers

- `docs/rg_scale_identification.md`
- `docs/rg_asymptotic_safety_bridge.md`
- `docs/project_status_and_roadmap.md`
- `docs/reviewer_faq.md`
