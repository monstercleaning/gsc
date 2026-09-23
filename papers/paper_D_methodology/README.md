# Paper D — Methodology and Software

**Working title:** *A Pre-Registration Reproducibility Stack for Falsifiable Cosmological Models.*

**Tier scope:** Meta — orthogonal to physics tiers. Stands independently of any specific theoretical claim.

**Length target:** ≈ 15 pages.

**Venue target:** Journal of Open Source Software (JOSS); SoftwareX; Astronomy and Computing.

**Status:** An earlier version (v12.2) is deposited as a preprint on Zenodo and figshare; the JOSS checklist is in [joss/SUBMIT.md](joss/SUBMIT.md). Revised in the v12.3 honesty pass (corrected an overclaim that the register was cryptographically signed / predictions signed-before-data) and again for the 20.0 package, whose architecture, counts and case studies it now describes ([CHANGELOG.md](../../CHANGELOG.md)).

## Scope

Paper D documents the deterministic, schema-validated, content-hashed and self-verifying reproducibility infrastructure underlying the GSC framework, and the pre-registration discipline intended to convert it from a defensive tool toward a falsification engine. The current release relies on git-history timestamps rather than executed GPG signatures, and most worked examples are retrodictive consistency checks; see the paper's *Scope and honest limitations*.

### Sections

1. Introduction: the problem of unfalsifiable cosmological model-building;
2. Architecture: deterministic pipelines, schema validation, content hashing, the register manifest;
3. The pre-registration register: format, signing protocol, scoring protocol;
4. Case studies:
   - P1: BAO ruler-shift prediction (Paper A);
   - P2: 21cm Cosmic Dawn (parametric);
   - P3: the retracted neutron-lifetime explanation;
   - P4–P14: including the P8 correction, the exact nulls and the early-gravity prediction;
5. Software stack: gsc/, pipelines/, verification/, schemas/, tests/, CI;
6. Self-verification: the claim checker and its negative control;
7. Limitations and design trade-offs;
8. Adoption notes for other projects.

## Key sources

- This paper documents the infrastructure that lives in this very repository:
  - [gsc/](../../gsc/) — core Python package;
  - [pipelines/](../../pipelines/) — pipeline entry points;
  - [schemas/](../../schemas/) — JSON schemas;
  - [tests/](../../tests/) — unit and integration tests;
  - [predictions/](../../predictions/) — pre-registration register;
  - [METHOD.md](../../METHOD.md) — pre-registration methodology;
  - [THEORY.md](../../THEORY.md) §2 — the tier architecture.

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
