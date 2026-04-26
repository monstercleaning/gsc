# Scorecard — Prediction P6 (Kibble-Zurek defect spectrum)
**Outcome:** ❌ FAIL
**Scored at:** `2026-04-26T13:53:11Z`
**Pipeline output hash:** `04d1715e4758465ebf1923f4fc5111821362a0edc0a3db002920eb4264f36a21`
**Observed source:** NANOGrav 15-yr (Agazie et al. 2023) + EPTA DR2 (Antoniadis et al. 2023) + LIGO O3 stochastic upper bound (released 2023-06-29)

## PTA stochastic-bound check
| Quantity | Value |
|---|---|
| Predicted Ω_GW | 0.6719 |
| PTA upper bound | 1e-09 |
| Ratio (pred/bound) | 671900000.0 |
| G μ (string tension) | 6.719e-07 |
| M_* (registered) | 1e+16 GeV |
| Pass | ✗ |

## Interpretation
FAIL: predicted Ω_GW = 6.72e-01 exceeds the PTA upper bound 1.00e-09 by a factor of 6.72e+08. Default M_* = 1e+16 GeV is excluded; reduce M_* (or modify ν, z critical exponents) until the prediction is below the PTA bound. As a rough rule of thumb, M_* ≲ TeV-scale is required.

## Reproduce

```bash
python3 scripts/predictions_compute_P6.py
python3 scripts/predictions_score_P6.py
```
