# Bridges (Support Packages)

These folders contain extracted **bridge/diagnostic** packages that connect
the v11.0.0 narrative to quick, dataset-facing checks.

Important:
- They were originally written using a **standard effective FLRW translation**
  (i.e. “observation → H(z), distances…” as in mainstream cosmology).
- In v11.0.0 we officially adopt **Option 2** (freeze-frame measurement model).
  Therefore, treat these packages as *support tools* and sanity harnesses, not
  as the canonical translation layer.

Canonical translation at v11.0.0 is defined by:
- `v11.0.0/docs/measurement_model.md`
- `v11.0.0/gsc/measurement_model.py`

## Contents

- `v11.0.0/bridges/phase2_action_to_observables_v0.2/`
  - Action → background → late-time observables bridge
  - Includes distance–drift tradeoff diagnostics

- `v11.0.0/bridges/phase3_cmb_growth_v0.2/`
  - Compressed diagnostics (θ*, BAO+FS consensus, growth curves)
  - Not a full Boltzmann/CMB pipeline

Each extracted folder contains a `.EXTRACTED_FROM_ARCHIVE` marker to keep the
extraction process idempotent.

