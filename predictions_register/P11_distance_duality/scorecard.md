# Scorecard — Prediction P11 (distance-duality eta(z) = 1 null)

> **RETRODICTIVE CURRENT-BOUNDS CHECK + STANDING FALSIFICATION CHANNEL.**
> Scored against already-public DESI-DR2-era DDR constraints. The forward
> content is the sudden-death clause: any future robust DDR violation at
> ≥ 3σ falsifies T1 — a single confirmed violation suffices (no majority rule).

**Outcome:** ✅ PASS  (at the registered |z| < 3 rule)
**Scored at:** `2026-07-27T07:51:27Z`
**Pipeline output hash:** `38bb489a7c50dbe10f155c28e940acbb3a84de429fc43de9ad913e1574795198`
**Observed source:** Zhang et al. 2025, 'Testing Cosmic Distance Duality Relation and Transparency with DESI DR2' (arXiv:2506.17926): DESI DR2 BAO + Pantheon+ SNe + cosmic chronometers; eta1 = 0.023 +/- 0.027, statistically consistent with zero.

## Prediction vs observation
| Quantity | Predicted | Observed | σ_obs | z-score |
|---|---|---|---|---|
| η₁ (linear DDR deviation) | 0 | 0.023 | 0.027 | +0.852 |

## Interpretation
PASS (retrodictive current-bounds check): the exact GSC null eta1 = 0 is consistent with the DESI-DR2-era linear-parametrization constraint at the registered |z| < 3 rule. Shared with ΛCDM — this check does not discriminate GSC from the standard model; its value is the standing sudden-death clause: any future robust (calibration-robust, model-independent) DDR violation at ≥ 3σ falsifies T1 outright, and no correction may be invoked to rescue it (GSC_Framework.md §12.2.1/§12.2.1a).

## Reproduce

```bash
python3 scripts/predictions_compute_P11.py
python3 scripts/predictions_score_P11.py
```
