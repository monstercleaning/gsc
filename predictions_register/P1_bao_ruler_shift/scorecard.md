# Scorecard — Prediction P1 (BAO ruler shift)
**Outcome:** ❌ FAIL  (at 2.0σ confidence)
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
FAIL: all registered σ(z) ansätze produce r_d values outside the DESI Y1 confidence band. Either the σ(z) parametrisation is incompatible with DESI Y1 BAO at the registered confidence, or the σ-modified recombination correction (gating M201) reverses the verdict. The framework's σ(z) parameter region must be restricted to small p (≲ 10^-3 for powerlaw).

## Reproduce

```bash
python3 scripts/predictions_compute_P1.py
python3 scripts/predictions_score_P1.py
```
