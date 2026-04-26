# Scorecard — Prediction P5 (Strong-CP θ-bound)
**Outcome:** ✅ PASS  (mode: nedm-only)
**Scored at:** `2026-04-26T13:53:11Z`
**Pipeline output hash:** `2db0b64bf46889d1b7c14e22884ab70e811fe9d27d473d2752e0cd9006563b7e`
**Observed source:** n2EDM 2024 (Abel et al.) (released 2020-02-28)

## nEDM bound check
| Quantity | Value |
|---|---|
| |θ_eff(z=0)| | 5e-11 |
| nEDM bound | 1e-10 |
| Fraction of bound | 50.0% |
| Pass | ✓ |

## Quasar bound check (rough, order-of-magnitude)
| Quantity | Value |
|---|---|
| Predicted |Δθ| at z=2 | 3.953e-05 |
| Rough bound | 1e-05 |
| Pass (soft) | ✗ |

## Interpretation
PASS: σ-axion-equivalence parameters are consistent with the current nEDM bound on |θ_eff(z=0)|.

## Reproduce

```bash
python3 scripts/predictions_compute_P5.py
python3 scripts/predictions_score_P5.py
```
