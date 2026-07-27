# Scorecard — Prediction P5 (Strong-CP θ-bound)
**Outcome:** ✅ PASS  (mode: nedm-only)
**Scored at:** `2026-07-27T07:51:27Z`
**Pipeline output hash:** `5f6f45074bc10c041e18c4f0d66f323c0d8089b975c249a5a1b8b02aef8f9300`
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
| Predicted |Δθ| at z=2 | 2.372e-05 |
| Rough bound | 1e-05 |
| Pass (soft) | ✗ |

## Interpretation
PASS: σ-axion-equivalence parameters are consistent with the current nEDM bound on |θ_eff(z=0)|.

## Reproduce

```bash
python3 scripts/predictions_compute_P5.py
python3 scripts/predictions_score_P5.py
```
