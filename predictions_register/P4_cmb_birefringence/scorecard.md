# Scorecard — Prediction P4 (CMB cosmic birefringence)
**Outcome:** ❌ FAIL  (at 2.0σ confidence)
**Scored at:** `2026-04-26T13:53:11Z`
**Pipeline output hash:** `5817d364df088b4e92696a8e8780db4669f83d90e9e2f46b2e74f762e544c0b1`
**Observed data source:** Minami & Komatsu 2020 (Planck 2018 polarization re-analysis) (released 2020-11-23)

## Prediction vs observation
| Quantity | Predicted | Observed | σ_obs | z-score |
|---|---|---|---|---|
| β (degrees) | 0.0015 | 0.35 | 0.14 | -2.4894 |

## Interpretation
FAIL: GSC-predicted birefringence amplitude is in tension with the Planck (Minami & Komatsu 2020) hint at the registered confidence level. Either (i) the σ-Chern-Simons coupling g_CS must be larger than the registered value (requires FRG-derived f_σ from Paper B), (ii) the σ-evolution amplitude p must be larger (would conflict with the late-time fit), or (iii) the Planck hint originates from a different mechanism (e.g., systematic effect; SARAS3 disputes the EDGES analogue). LiteBIRD (~2030) will sharpen this test.

## Reproduce

```bash
python3 scripts/predictions_compute_P4.py
python3 scripts/predictions_score_P4.py
```
