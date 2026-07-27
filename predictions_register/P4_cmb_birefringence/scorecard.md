# Scorecard — Prediction P4 (CMB cosmic birefringence)
**Outcome:** ✅ PASS  (at 3.0σ confidence)
**Scored at:** `2026-07-27T07:51:27Z`
**Pipeline output hash:** `261f3d5736d4cf08f034c6c2bfec257dbb5772261ecbccb703924bfb235d23c5`
**Observed data source:** Minami & Komatsu 2020 (Planck 2018 polarization re-analysis) (released 2020-11-23)

## Prediction vs observation
| Quantity | Predicted | Observed | σ_obs | z-score |
|---|---|---|---|---|
| β (degrees) | 0.0009 | 0.35 | 0.14 | -2.4936 |

## Interpretation
PASS: GSC-predicted CMB birefringence is consistent with the Planck (Minami & Komatsu 2020) hint at the registered confidence level.

## Reproduce

```bash
python3 scripts/predictions_compute_P4.py
python3 scripts/predictions_score_P4.py
```
