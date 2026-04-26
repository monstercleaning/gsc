# Scorecard — Prediction P3 (Neutron-lifetime beam-trap)
**Outcome:** ❌ FAIL  (at 2.0σ confidence)
**Scored at:** `2026-04-26T13:53:11Z`
**Pipeline output hash:** `bb9bc0e922ef044f361583e2f2fcf3f7324f170f998ee41df2c3acfd99cb1a97`
**Observed data source:** PDG 2024 world averages (released 2024-08-31)

## Predictions vs observations
| Quantity | Predicted | Observed | σ_obs | z-score | Pass |
|---|---|---|---|---|---|
| τ_n^beam (s) | 887.7000 | 887.7 | 2.2 | +0.0000 | ✓ |
| τ_n^trap (s) | 887.7000 | 878.4 | 0.5 | +18.6000 | ✗ |
| Δ (beam-trap) (s) | 0.0000 | 9.3 | 2.2561 | -4.1222 | ✗ |

## Interpretation
FAIL: predicted τ_n values are inconsistent with PDG world averages at the registered confidence level. Re-examine σ-environmental coupling or look for alternative explanations of the discrepancy.

## Reproduce

```bash
python3 scripts/predictions_compute_P3.py
python3 scripts/predictions_score_P3.py
```
