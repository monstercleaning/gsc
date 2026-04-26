# Scorecard — Prediction P7 (GW-memory atomic-clock signature)
**Outcome:** ⏸ SUB-THRESHOLD
**Scored at:** `2026-04-26T13:53:11Z`
**Pipeline output hash:** `4ac7c362f4c0d9237c8afdb44e88fa51024660085d7a1397a67c393a4b8e9742`
**Observed source:** Best current optical-lattice clock instabilities (Sr, Yb+, Al+, ITOC, BACON) (released 2024-12-31)

## Detectability check (current technology)
| Quantity | Value |
|---|---|
| Stacked predicted signal | 1.000e-20 |
| N events (pipeline) | 100 |
| N events (realistic estimate) | 100 |
| Best clock instability (10⁴ s) | 8e-19 |
| SNR vs best clock | 0.0125 |
| Detectable at 3σ | ✗ |

## Interpretation
SUB-THRESHOLD: stacked signal of 1.00e-20 is below the 3× best clock-array instability (2.40e-18). Either (i) the σ-GW coupling k_GW must be larger than the registered value (FRG-derived from Paper B), (ii) more events must be stacked than the registered N, or (iii) clock-array instability must improve by orders of magnitude. The framework is NEITHER confirmed NOR refuted by P7 with current technology — this is itself useful information.

## Reproduce

```bash
python3 scripts/predictions_compute_P7.py
python3 scripts/predictions_score_P7.py
```
