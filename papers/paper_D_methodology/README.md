# Paper D — Methodology and Software

**Working title:** *A Pre-Registration Reproducibility Stack for Falsifiable Cosmological Models.*

**Tier scope:** Meta — orthogonal to physics tiers. Stands independently of any specific theoretical claim.

**Length target:** ≈ 15 pages.

**Venue target:** Journal of Open Source Software (JOSS); SoftwareX; Astronomy and Computing.

**Status:** Drafting from the existing reproducibility stack; scheduled for first submission.

## Scope

Paper D documents the deterministic, schema-validated, lineage-tracked reproducibility infrastructure underlying the GSC framework, and the pre-registration discipline that converts it from a defensive tool into a falsification engine.

### Sections

1. Introduction: the problem of unfalsifiable cosmological model-building;
2. Architecture: deterministic pipelines, schema-validated artifacts, lineage DAGs;
3. The pre-registration register: format, signing protocol, scoring protocol;
4. Case studies:
   - Case 1: BAO ruler-shift prediction (Paper A);
   - Case 2: CMB birefringence consistency check (Paper B);
   - Case 3: 21cm Cosmic Dawn (extension);
5. Software stack: gsc/, scripts/, schemas/, tests/, CI;
6. Operator workflows: one-button reproduction, release-candidate gating;
7. Limitations and design trade-offs;
8. Adoption notes for other projects.

## Key sources

- This paper documents the infrastructure that lives in this very repository:
  - [gsc/](../../gsc/) — core Python package;
  - [scripts/](../../scripts/) — pipeline entry points;
  - [schemas/](../../schemas/) — JSON schemas;
  - [tests/](../../tests/) — unit and integration tests;
  - [predictions_register/](../../predictions_register/) — pre-registration register;
  - [docs/pre_registration.md](../../docs/pre_registration.md) — pre-registration methodology;
  - [docs/tier_hierarchy.md](../../docs/tier_hierarchy.md) — tier-based publication architecture.

## Why this paper matters

Paper D is the framework's *insurance policy*. Even if Papers A, B, C are all eventually disfavoured by data:

- The reproducibility methodology remains a contribution;
- The pre-registration register format may be adopted by other groups;
- The tier-based publication strategy may inform other speculative-but-disciplined research programs;
- The deterministic-pipeline + schema-validation pattern is broadly applicable to scientific software.

A successful Paper D — published, cited, possibly templated by other groups — is independent of the truth or falsehood of GSC's specific physical claims.

## Outstanding work

- [ ] JOSS preflight checklist completion;
- [ ] Case-study writeups (one per pre-registered prediction);
- [ ] Independent reproducer testimonials (request collaborators to re-run from scratch);
- [ ] Container-based reproducer (Docker / Singularity);
- [ ] Cross-platform validation report;
- [ ] Migration guide for projects adopting the stack.

## Submission priority

**Submit Paper D first.** A successfully published methodology paper provides credibility for the more speculative content of A, B, C, and gives the framework a citable contribution that survives any physics outcome.
