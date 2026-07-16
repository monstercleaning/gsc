# Scorecard — Prediction P1 (BAO ruler shift)

> **RETRODICTIVE CONSISTENCY CHECK — not a score of the registered forward prediction.**
> This card scores against **already-public DESI Year-1** data (released 2024-04-04) using a relative-shift statistic, to exercise the scoring pipeline end-to-end. The *registered* P1 prediction targets **DESI Year-3** (≈2027) and remains **unscored**. See `docs/pre_registration.md` → *Current implementation status*.

**Outcome:** ❌ FAIL  (power-law ansatz z = +3.93, outside the registered |z| < 3 band)
**Scored at:** `2026-04-26T13:53:10Z`
**Pipeline output hash:** `8f6165734461f752194f5db23036a6ebbfa52658e1b7871bead29e57ff4df2ca`
**Observed source:** DESI Year-1 BAO (DESI Collaboration 2024) — preliminary near-term constraint pending DESI Y3 (2027) (released 2024-04-04)
**Observed r_d:** 147.09 ± 0.26 Mpc

## Per-ansatz results (relative-shift test)
Test: predicted Δr/r vs DESI Y1 relative precision (σ_DESI / r_DESI).

| Ansatz | parameters | Δr/r predicted | z-score | Pass |
|---|---|---|---|---|
| powerlaw | p=0.001 | +0.6953% | +3.934 | ✗ |
| transition | dz=0.5, p_high=0.005, p_low=0.001, z_t=1.0 | +3.5253% | +19.944 | ✗ |
| rg_profile | alpha=0.5, p_eff=0.001, sigma_star_z=1000000.0 | +0.6954% | +3.934 | ✗ |

## Interpretation
FAIL: all registered σ(z) ansätze produce r_d values outside the DESI Y1 confidence band. The σ(z) parametrisation is therefore in tension with DESI Y1 BAO at the registered confidence unless the scaling exponent is restricted to very small p (≲ 10⁻³ for the power-law ansatz) — which is the value the other predictions already assume. We do **not** invoke an unimplemented "σ-modified recombination correction" to reverse this verdict; any such mechanism would have to be registered and scored on its own before it could count.

## Reproduce

```bash
python3 scripts/predictions_compute_P1.py
python3 scripts/predictions_score_P1.py
```
