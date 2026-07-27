# Scorecard — Prediction P1 (BAO ruler shift)

> **RETRODICTIVE CONSISTENCY CHECK — not a score of the registered forward prediction.**
> This card scores against **already-public DESI DR1-era** data using the registered
> relative-shift statistic, to exercise the scoring pipeline end-to-end. The *registered*
> forward target is the **full five-year DESI BAO release** (DESI DR2, containing the
> Year-3 data, is itself already public since 2025-03). See `docs/pre_registration.md`
> → *Current implementation status*.

**Outcome:** ✅ PASS  (at the registered |z| < 3 rule)
**Scored at:** `2026-07-27T07:51:27Z`
**Pipeline output hash:** `a6228f68b3b7b7e28c792a92c9202d61b0e317f59de510e07289c385ac5835fe`
**Observed source:** DESI Year-1 BAO (DESI Collaboration 2024) — preliminary near-term constraint pending DESI Y3 (2027) (released 2024-04-04)
**Observed r_d:** 147.09 ± 0.26 Mpc

## Per-ansatz results (relative-shift test)
Test: predicted Δr/r vs DESI Y1 relative precision (σ_DESI / r_DESI).

| Ansatz | parameters | Δr/r predicted | z-score | Pass |
|---|---|---|---|---|
| powerlaw | p=0.0006 | +0.4166% | +2.357 | ✓ |
| transition | dz=0.5, p_high=0.0029999999999999996, p_low=0.0006, z_t=1.0 | +2.1005% | +11.883 | ✗ |
| rg_profile | alpha=0.5, p_eff=0.0006, sigma_star_z=1000000.0 | +0.4167% | +2.357 | ✓ |

## Interpretation
PASS (retrodictive consistency check): at least one registered σ(z) ansatz is consistent with the DESI DR1-era constraint at the registered |z| < 3 rule. Context from public data: DESI DR2 (released 2025-03; aggregate isotropic BAO precision ~0.24%, arXiv:2503.14742) is also already public — the canonical powerlaw shift of +0.417% sits at ~1.7σ of that aggregate precision. The genuine forward test is the full five-year DESI BAO release (~0.2% forecast, arXiv:2402.14070), scored at the registered rule when it is released. No unimplemented correction may be invoked to modify this verdict (GSC_Framework.md §12.2.1).

## Reproduce

```bash
python3 scripts/predictions_compute_P1.py
python3 scripts/predictions_score_P1.py
```
