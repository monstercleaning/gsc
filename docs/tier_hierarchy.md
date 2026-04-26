# Tier Hierarchy

The GSC framework is organized into four tiers of epistemic confidence. Each tier carries an independent kill-test, so that the failure of any higher tier does not propagate downward.

## The four tiers

| Tier | Type | Example | Kill-test | Survives if false |
|---|---|---|---|---|
| **T1** | Kinematic frame | Conformal equivalence FRW ↔ freeze-frame | Mathematical inconsistency in coordinate transformation | — |
| **T2** | Phenomenological fit | σ(t) reproduces SN, BAO, structure data | χ²/dof above threshold for all reasonable σ(t) ansätze | T1 |
| **T3** | Physical ansatz | G(σ) follows specific RG-running near σ_* | First-principles FRG derivation incompatible, or all parameter regions excluded | T1 + T2 |
| **T4** | Speculative extension | Vortex DM, holographic proton, σ-θ coupling, σ as QRF | Per-module observational kill-test | T1 + T2 + T3 |

## Why this matters

Past framework iterations had two failure modes:

- **Maximalism**: a unified bold thesis where adverse review of one component risked dismissal of the whole;
- **Defensiveness**: protective scope-narrowing that preserved nothing of the original explanatory ambition.

The tier hierarchy resolves this. Each section, claim, prediction, and paper carries an explicit tier label. Reviewers and readers can reject a T4 module without affecting their stance on T2; can accept T3 while remaining agnostic about T4; can endorse the methodology (T1+T2 plus reproducibility infrastructure) independently of any specific physical mechanism.

## Tier annotation conventions

In `GSC_Framework.md` and across the documentation:

- Section headers carry `(T1)`, `(T2)`, `(T3)`, or `(T4)` markers;
- The claim ledger ([docs/claim_ledger.json](claim_ledger.json) — to be updated for the current cycle) labels every claim by tier;
- Pre-registered predictions in [predictions_register/](../predictions_register/) link to the tier they test;
- Paper boundaries (A, B, C, D) align with tier boundaries.

## Promotion and demotion

A claim can be **promoted** (e.g., from T3 phenomenological ansatz to T2 derivation) when independent first-principles work supports it. A claim can be **demoted** (or removed) when its kill-test is triggered. All promotions and demotions are logged with date, evidence, and references.

The current framework version is the **floor** for what is claimed. Higher claims (e.g., a complete σ_* derivation from non-commutative IR) are documented as outstanding work, not as established results.

## Relation to the publication strategy

The four-paper publication structure mirrors the tier hierarchy:

- **Paper A** — T1 + T2 (empirical core);
- **Paper B** — T3 (theoretical mechanism);
- **Paper C** — T4 (speculative extensions);
- **Paper D** — methodology and software (orthogonal to physics tiers).

This means each paper can be reviewed and accepted on its own merits. A reviewer who endorses Paper A is not implicitly endorsing Paper C's vortex-DM module; a reviewer who rejects Paper B's RG ansatz is not invalidating Paper A's measurement-model fit.

See [GSC_Framework.md §0](../GSC_Framework.md) for the full architectural rationale.
