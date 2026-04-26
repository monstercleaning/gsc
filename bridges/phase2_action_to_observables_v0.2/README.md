# GSC Phase 2 (v0.2): Action-to-Observables Bridge

This package extends **GSC v10.1** with a minimal, *action-based* derivation of the
phenomenological power-law collapse/expansion rate used in the Phase 1 / v10.1
redshift-drift simulations.

## What this adds (relative to v10.1)

- A concrete **scalar-field action** (Einstein-frame prototype) that yields
  power-law solutions and explains why a **power-law H(z)** is not an arbitrary
  curve-fit.
- A mapping between the model’s action parameter **λ** (slope of an exponential potential)
  and the phenomenological exponent **p** used in `H(z)=H0(1+z)^p`:
  **p = λ²/2**.
- Diagnostics showing the **distance–drift tradeoff**: forcing a globally positive
  redshift drift is generically in tension with matching ΛCDM luminosity distances
  unless the exponent becomes z-dependent.

## Structure

- `scripts/`
  - `phase2_action_solver.py` – integrates the autonomous system for a canonical scalar
    with an exponential potential; produces attractor plots and a derived drift curve.
  - `phase2_action_distance_compare.py` – compares H(z), distance modulus, and velocity drift
    between ΛCDM and a power-law model (p=0.5 by default).
  - `phase2_distance_drift_tradeoff.py` – diagnostic scan illustrating distance vs drift
    tension, with a fast preset best-fit (set `DO_OPTIMIZE=True` to refit).
  - `phase2_action_tradeoff_scan.py` – *pre-data* scan over p<1 quantifying the
    detectability vs distance-tension tradeoff and highlighting “feasible” windows.
  - `run_all.py` – regenerates all outputs into `outputs/`.

- `outputs/` – generated figures and small CSV summaries.

- `report/` – a short technical note (md/tex/pdf).

## Quick start

```bash
python scripts/run_all.py
```

## Notes

This Phase 2 prototype is **not** a full replacement for the RG-flow/Landau-pole
mechanism in the main GSC framework. It is a *bridge* that makes the Phase 1
power-law modeling derivable from an action, improving methodological defensibility.

