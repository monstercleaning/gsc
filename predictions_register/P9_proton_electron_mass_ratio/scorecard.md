# Scorecard — Prediction P9 (μ = m_p/m_e constancy)
**Outcome:** ✅ PASS
**Scored at:** `2026-04-26T13:53:11Z`
**Pipeline output hash:** `879864e244195b36056a7a5b148159f831c350e155ad78ba710ea0e6cfb46366`
**Observed source:** Combination: HD+ ion-trap (Patra et al. 2020, Science 369, 1238) + H2 absorbers at z~2-3 (Ubachs/Bagdonaite review) (released 2024-12-31)

## Laboratory check (HD+ ion trap)
| Quantity | Value |
|---|---|
| |μ̇/μ| predicted | 0.0 /yr |
| Observed bound | 5e-17 /yr |
| Pass | ✓ |

## Cosmological check (H2 absorbers at z~2-3)
| Quantity | Value |
|---|---|
| |Δμ/μ| predicted at z=2 | 0.0 |
| Observed bound at z=2-3 | 1e-06 |
| Pass | ✓ |

## Interpretation
PASS: μ̇/μ and Δμ/μ predictions (both 0 under universal coherent scaling) are consistent with current laboratory (HD+) and cosmological (H2 absorbers) bounds. The geometric-lock condition (T1) is not falsified by current data on the proton-electron mass ratio.

## Reproduce

```bash
python3 scripts/predictions_compute_P9.py
python3 scripts/predictions_score_P9.py
```
