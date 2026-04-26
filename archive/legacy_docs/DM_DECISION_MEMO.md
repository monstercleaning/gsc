# DM Decision Memo (Phase-4, current v11 series)

Introduced in M139; maintained through current Phase-4 milestones.

Purpose: prevent claim drift while Phase-4 focuses on credibility, reproducible
falsification tooling, and reviewer clarity.

## Decision frame

This memo defines three project stances for dark-matter interpretation.

### A) Immediate replacement narrative

- Position: claim that current framework already supersedes standard
  dark-matter phenomenology.
- Assessment: rejected for current phase.
- Reason: required perturbation/lensing/halo-level evidence is not yet part of
  the shipped canonical pipeline.

### B) Diagnostic-first with explicit baseline comparison (selected)

- Position: keep standard matter-content baselines in diagnostics and report
  differences with transparent assumptions.
- Assessment: selected for Phase-4.
- Reason: maximizes falsifiability and reviewer trust with current tooling.

### C) Strictly agnostic interpretation channel

- Position: publish only methodology and no dark-matter interpretation layer.
- Assessment: kept as fallback for conservative submissions.
- Reason: useful when a venue requests narrower scope.

## Selected stance for Phase-4

The repository adopts **B (diagnostic-first with explicit baseline comparison)**.

Operational consequences:

- Keep low-z and growth diagnostics anchored to explicit baseline models.
- Treat any dark-matter interpretation as a deferred hypothesis layer.
- Keep wording in docs/artifacts tied to measurable outputs and testable deltas.

## Explicit non-claims (current branch)

- No claim that the repository has completed perturbation-level closure for a
  dark-matter interpretation.
- No claim that galaxy/halo/lensing observables are fully explained by the
  current shipped pipeline.
- No claim that full CMB anisotropy likelihood validation has been completed.

## Must-pass evidence gates before any future DM interpretation upgrade

A future claim tier requires all gates below to pass on tagged releases:

1. **Background + growth consistency**
   - Deterministic low-z diagnostics with stable residual behavior.
2. **Perturbation closure gate**
   - Reproducible external Boltzmann pipeline with documented assumptions and
     stable verification artifacts.
3. **Lensing/dynamics cross-check gate**
   - Explicit, reproducible checks that include lensing-sensitive channels.
4. **Claim-lint and portability gate**
   - `docs_claims_lint` and portable-content checks remain green.
5. **Independent replay gate**
   - Reviewer snapshot replay reproduces the same acceptance summaries.

## Review policy

When these gates are not all satisfied, the canonical language remains
"diagnostic and falsification-oriented" with baseline comparisons, not
interpretive closure.
