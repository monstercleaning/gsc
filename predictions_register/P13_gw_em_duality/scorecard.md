# Scorecard — Prediction P13 (GW-EM duality Xi_0 = 1 null)

> **RETRODICTIVE CURRENT-BOUNDS CHECK + STANDING FALSIFICATION CHANNEL.**
> Scored against the already-public GWTC-4.0 dark-siren constraint. The
> forward content is the sudden-death clause: any future robust Xi_0 != 1
> at ≥ 3σ falsifies T1 — a single confirmed violation suffices.

**Outcome:** ✅ PASS  (at the registered |z| < 3 rule)
**Scored at:** `2026-07-28T11:57:17Z`
**Pipeline output hash:** `c5b974036f8885c81fd5df9abc089d5c36c1f6a218f4e628a9441436e63635a1`
**Observed source:** LVK GWTC-4.0 cosmology paper, 'GWTC-4.0: Constraints on the Cosmic Expansion Rate and Modified Gravitational-wave Propagation' (arXiv:2509.04348): 142 of 218 GW sources x GLADE+ galaxy catalog; Xi_0 = 1.2 +0.8/-0.4 (68.3%), 'Xi_0 = 1 recovers the behavior of general relativity' (abstract, verified via INSPIRE record 2026-07-27). H0 = 76.6 +13.0/-9.5 km/s/Mpc from the same analysis.

## Prediction vs observation
| Quantity | Predicted | Observed | σ (toward null) | z-score |
|---|---|---|---|---|
| Ξ₀ (modified GW propagation) | 1 | 1.2 (+0.8/−0.4) | 0.4 | +0.500 |

## Interpretation
PASS (retrodictive current-bounds check): the exact GSC null Xi_0 = 1 is consistent with the GWTC-4.0 dark-siren constraint at the registered |z| < 3 rule. Shared with ΛCDM+GR — this check does not discriminate GSC from the standard model; its value is the standing sudden-death clause: any future robust (systematics-stable, independently reproduced) Xi_0 != 1 at ≥ 3σ falsifies T1 outright, and no correction may be invoked to rescue it (GSC_Framework.md §12.2.1/§12.2.1a). The constraint tightens every observing run with no involvement from this project.

## Reproduce

```bash
python3 scripts/predictions_compute_P13.py
python3 scripts/predictions_score_P13.py
```
