---
prediction_id: P14
title: Early-universe gravity weaker relative to atoms — G/G0 = 0.992 at recombination, 0.970 at nucleosynthesis
tier: T2 (coherent reading of the canonical exponent; OPEN_PROBLEMS.md problem 1)
ansatz: early transition — particle masses drift relative to the Planck mass above z = 10 with exponent q = 8.65e-4, frozen below
target_dataset: cosmological determinations of G at recombination and at nucleosynthesis (full-spectrum CMB with BAO; primordial abundances)
target_release_date: continuous (each new determination of early-universe G scores it)
status: SCAFFOLD — git-timestamped, GPG-signing pending; FORWARD registration (v20.1; current bounds do not yet reach the predicted shifts)
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P14 — Early-universe gravity weaker relative to atoms (registered v20.1)

## Statement

The only coherent reading of the canonical exponent ([OPEN_PROBLEMS.md](../../OPEN_PROBLEMS.md), problem 1) lets
particle masses drift relative to the Planck mass before the transition redshift z_t = 10 and freezes them
afterwards. Measured in atomic units, this is a gravitational coupling that was weaker in the early universe:

```
G(z)/G0 = ((1 + z_E)/(1 + z_t))^(-2q)   above the transition (z_E: Einstein-frame redshift)
G(z)/G0 = 1                              below it
q = 8.65e-4,  z_t = 10
```

The registered values, computed by `pipelines/predictions_compute_P14.py`:

| Epoch | Observed redshift | G/G0 | Change |
|---|---|---|---|
| Recombination | 1089.95 | 0.9921 | −0.79% |
| Nucleosynthesis (deuterium formation, T ≈ 0.1 MeV) | 4.3×10⁸ | 0.9702 | −2.98% |
| Weak freeze-out (T ≈ 1 MeV) | 3×10⁹ | 0.9670 | −3.30% |
| Any z below 10, including today | — | 1 exactly | 0 |

The two main epochs are tied by the shape of the transition, whatever q is:

```
ln(G_BBN/G0) = 3.80 × ln(G_rec/G0)
```

## What this prediction is and is not

- **It is the only distinguishing content left in the GSC core** after the joint CMB + BAO fit
  ([analyses/joint_fit.md](../../analyses/joint_fit.md)), which absorbs the same reading's BAO signature into H0.
- **It is a new forward prediction under kill condition K0.3**, not a rescue of P1. P1 stands as registered, with its
  editorial flag; P14 neither scores nor replaces it. The scope and threshold of K0 are unchanged.
- **Its parameter is a commitment, not a fit.** q is the value for which the reading reproduces P1's registered shift
  at fixed cosmological parameters ([analyses/p_role_consistency.py](../../analyses/p_role_consistency.py)). Distance
  data do not constrain it; nucleosynthesis allows −1.4×10⁻³ < q < 1.8×10⁻³ at 2σ.
- **It is not unique to GSC.** Other theories with a time-varying G predict weaker early gravity. What is specific is
  the pair of values and the fixed relation between the two epochs, together with an exact null below z = 10.

## Tier

T2, in its coherent reading. The reading breaks the geometric lock only above z = 10, where no local test reaches;
below it, local physics is exactly that of T1, so kill condition K2 is unaffected.

## Pipeline

`pipelines/predictions_compute_P14.py` evaluates the formula above for the registered q; it fits nothing. Output:
`pipeline_output.json` (schema `predictions_p14_pipeline_output_v1`), deterministic, standard library only.

## Current observational status (not scored)

- **Nucleosynthesis.** Alvey, Sabti, Escudero & Fairbairn (EPJC 2020, doi:10.1140/epjc/s10052-020-7727-y,
  arXiv:1910.10730): G_BBN/G0 = 0.99 +0.06/−0.05 at 2σ. The predicted 0.970 lies within 1σ; the measurement cannot yet
  tell it from G = G0.
- **Recombination.** Lamine et al. (A&A 2025, doi:10.1051/0004-6361/202451602, arXiv:2407.15553) determine a single
  cosmological G to 1.8%, consistent with the laboratory value. The predicted −0.79% is below that precision; the
  comparison is indicative, because that analysis assumes one G at all epochs.
- **CMB + BAO distances** fit this reading as well as ΛCDM and do not constrain q
  ([analyses/joint_fit.md](../../analyses/joint_fit.md)).

No current measurement can distinguish the prediction from G = G0, so the entry is not scored: a PASS now would say
nothing.

> **Editorial flag (v20.1; the registered text is unchanged):** the sentence above is wrong about the rule. Applied
> to the Alvey et al. determination (σ ≈ 0.025 on the side facing the prediction), the scoring rule below gives
> SUB-THRESHOLD, not PASS: z ≈ −0.8, and a PASS needs σ ≤ 0.015. The conclusion stands: no current measurement can
> tell the prediction from G = G0. The entry stays unscored as registered; its target is the next determinations of
> early-universe G.

> **Editorial flag (v20.2; the registered text is unchanged):** the status above missed results published before
> the registration. The LBT helium abundance (Aver et al. 2026, arXiv:2601.22238), read as the expansion rate during
> nucleosynthesis (Goldstein & Hill 2026, arXiv:2603.13226; Loverde, Saravanan & Weiner 2026, arXiv:2609.13140),
> gives G/G0 ≈ 0.989 ± 0.014: the prediction is 1.4σ away, G = G0 0.8σ. Deuterium depends on nuclear rates that are
> not settled. With data-driven rates (Yeh, Olive & Fields 2021) it is neutral. With PRIMAT's (Pitrou et al. 2021)
> and the Planck baryon density, it puts the prediction 3.3σ away. Helium and deuterium together put it 1.3σ away
> with the first rate set and 2.7–3.0σ with the second. None of this is scored: all of it predates the registration,
> and none of it is a determination of G. Two points on reading the rule:
>
> - A helium result like LBT's, published after the registration as a determination of G, would score PASS although
>   it lies closer to G = G0.
> - A determination from deuterium with PRIMAT's rates and the Planck baryon density would, on today's data, score
>   FAIL.
>
> Details: [analyses/p14_bbn_status.md](../../analyses/p14_bbn_status.md).

> **Addendum (v20.2, the same day; the registered text is unchanged):** a 2026 analysis of the same nuclear data
> (Launders, Giovanetti & Liu, arXiv:2604.16600) shows that the polynomial fits behind the first rate set over-predict
> deuterium; its unbiased fit agrees with PRIMAT. With these rates and the PDG 2025 deuterium average
> (2.508 ± 0.029), deuterium alone puts the prediction 2.8–3.2σ away, and helium and deuterium together 2.4–2.7σ,
> where G = G0 fits them about 17 times better. Such a combined determination, published after the registration,
> would still score PASS under the rule (σ ≈ 0.012, |z| < 3), which is why reports give both distances.

## Scoring algorithm

For each epoch with a published determination r_obs ± σ of G/G0 (1σ; for asymmetric errors, the side facing the
prediction) from an analysis that lets G at that epoch differ from today's:

```
z = (r_pred − r_obs) / σ
```

- **FAIL** if |z| ≥ 3 at any scored epoch, or if a fit of this one-parameter model to CMB, BAO and abundance data
  excludes the registered q at ≥ 3σ.
- **PASS** if |z| < 3 at every scored epoch and at least one measurement has σ ≤ |r_pred − 1|/2, so that it can tell the
  prediction from G = G0.
- **SUB-THRESHOLD** if |z| < 3 everywhere but no measurement is yet that precise.

## Kill-test

**If P14 fails, the GSC core (T1–T3) has no registered content that distinguishes it from ΛCDM, and the
conformal-reduction clause K0.4 applies ([THEORY.md](../../THEORY.md) §8): GSC is falsified as a distinct theory.**
This clause is part of the registration. Like K1 and K2, it only adds a way for the framework to die.

## Significance

The joint fit showed that the late-universe signature GSC registered in P1 is absorbed into H0. What survives is a
statement about gravity in the first minutes and the first 380,000 years. It is small, but sharp: two numbers and a
fixed relation between them, tested by measurements that are already within a factor of a few of the needed
precision.
