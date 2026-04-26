# Publication Strategy

The GSC framework is published as four layered papers, isolated by tier, so that adverse review of any one layer does not invalidate the others. See [docs/tier_hierarchy.md](../docs/tier_hierarchy.md) for the architectural rationale.

## The four papers

| Paper | Scope | Tier | Length | Venue | Status |
|---|---|---|---|---|---|
| **[A](paper_A_late_time/)** | Late-time empirical fit | T1 + T2 | ~30 pp | Phys. Rev. D / JCAP | Drafting |
| **[B](paper_B_rg_mechanism/)** | RG mechanism for G(σ) | T3 | ~25 pp | CQG / JHEP | Outline |
| **[C](paper_C_extensions/)** | Speculative extensions | T4 | ~40 pp | Found. Phys. / Universe | Outline |
| **[D](paper_D_methodology/)** | Methodology and software | meta | ~15 pp | JOSS / SoftwareX | Drafting |

## Why this structure

A reviewer can:

- Reject Paper C's vortex-DM derivation without affecting acceptance of Paper A;
- Reject Paper B's σ-θ coupling claim without affecting Paper A's empirical fit;
- Cite Paper D's reproducibility methodology without endorsing any specific physical claim;
- Endorse Paper B's RG ansatz while remaining agnostic on Paper C's extension modules.

This is the operational realization of the tier hierarchy.

## Cross-paper consistency

While each paper stands alone, all four share:

- The same framework cycle (current canonical specification in [../GSC_Framework.md](../GSC_Framework.md));
- The same canonical late-time fit results;
- The same pre-registration register (predictions referenced by ID);
- The same software stack (this repository).

Cross-references between papers use stable artifact identifiers from `artifacts.json`.

## Submission order

Recommended order for submission:

1. **Paper D** (methodology) — submit first to JOSS. Establishes the reproducibility infrastructure as an independently citable contribution. Lowest review risk.
2. **Paper A** (late-time empirical) — submit to Phys. Rev. D after JOSS acceptance. Cite Paper D's methodology.
3. **Paper B** (RG mechanism) — submit after Paper A. Cite Paper A's empirical results.
4. **Paper C** (extensions) — submit last, with selective journal targeting based on which extension modules have matured.

This sequencing ensures that the methodology and empirical core are both independently citable before the more speculative content is exposed to review.

## Where to start

- New contributors: read [paper_A_late_time/README.md](paper_A_late_time/) first.
- Methodology focus: see [paper_D_methodology/README.md](paper_D_methodology/).
- Theory focus: see [paper_B_rg_mechanism/README.md](paper_B_rg_mechanism/).
- Speculative discussions: see [paper_C_extensions/README.md](paper_C_extensions/).
