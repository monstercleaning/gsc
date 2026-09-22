# Changelog

## 20.0.0 — 2026-09-22 — standalone reorganization

A structural release. The project had grown through versions 8 to 12 into a package of about 900 files whose
documents referred to one another across version directories, archives and legacy tooling. That structure
caused real failures: a repository sync twice overwrote a working CI configuration, legacy registries went
stale and reported phantom errors, and a correct result about the redshift drift, recorded in an archived
roadmap, was lost and later contradicted. Version 20 is a standalone package of about 150 files, organized by
purpose, with no references to other versions.

**Guarantees, each checked mechanically:**

- **No registered number changed.** All thirteen frozen pipeline outputs were recomputed in the new layout and are
  byte-identical to their registered versions; all nine scorers return the same verdicts (6 PASS, 2 FAIL,
  1 SUB-THRESHOLD). `pipelines/predictions_compute_all.sh` now verifies the register instead of overwriting it.
- **Scorecards are deterministic.** The wall-clock stamp was removed, so rescoring unchanged inputs no longer
  rewrites files; the git commit dates each scoring.
- **The negative control is self-contained.** The claim checker must still catch the historical false signing
  claim, now kept verbatim as a fixture (18 of 18 sites caught) instead of being read from git history, so the
  test works in shallow clones and unzipped deposits.
- **The package is standalone.** A new check fails if any living document names a file, by path or by bare file
  name, that the package does not contain.
- **The register is notarizable.** `predictions/MANIFEST.sha256` lists the SHA-256 of every registered file; its
  own digest can be quoted in a deposit description as a third-party timestamp.
- **The status table is generated.** [PREDICTIONS.md](PREDICTIONS.md) is produced from the register and checked
  for currency.

**Organization.** [THEORY.md](THEORY.md) replaces the former framework document: the same content, ordered by tier,
with every section consistent with the register's current verdicts (several sections of the old document still
described retracted or superseded claims) and the kill conditions given stable names K0, K1, K2.
[METHOD.md](METHOD.md) gathers the register, scoring, signing status and self-verification.
[OPEN_PROBLEMS.md](OPEN_PROBLEMS.md) records known issues instead of fixing them silently.

**Flagged, not fixed** (fixing them changes predictions, which requires new registrations): which sector carries
the canonical parameter, and the resulting tension between P1 and lunar laser ranging (problem 1); the history
behind the P8 revision r2 moves the BAO ruler the opposite way to P1 (problem 2); P2's underived amplification
factor (problem 3); the CMB acoustic-angle assumption (problem 4). The evidence is the deterministic diagnostic
`analyses/p_role_consistency.py`.

**Deposit review.** Checking the package before its public deposit found documents that still described an
earlier release. Each finding was corrected and became a mechanical check:

- The methodology papers described tooling this package does not contain (third-party dependencies, lineage
  records, a size audit, three operator scripts) and said each output's hash was recorded in its `prediction.md`.
  They now describe the package as it is: standard library only, schema validation, hashes in the scorecards and
  the register manifest, and the claim checker.
- The long-form methodology paper repeated the retracted neutron-lifetime explanation, called predictions signed,
  and still said "ten" predictions. Paper B and the frontier notes still gave P4's old FAIL and its pre-revival
  numbers; they now quote the registered output (a weak PASS at the |z| < 3 rule, a FAIL at 2σ).
- An uncited, unverifiable reference ("in preparation") was removed from the long-form methodology paper. In
  the JOSS paper, blind analysis was attributed to the LIGO Open Science Center, described as publishing
  "pre-registered analysis pipelines"; it now cites the review by Klein and Roodman (2005).
- The deposited preprint PDF was built by a script outside the package, with its own hard-coded reference list
  that could drift from `paper.bib`, and did. The renderer is now part of the package
  (`papers/paper_D_methodology/joss/render_preprint.py`), reads the citations and references from `paper.bib`,
  and fails on an unknown citation key.
- The checker's own manifest said the outputs were schema-validated while the check only resolved schema file
  names. Every registered output is now validated by a standard-library validator that agrees with the reference
  implementation on every output and several hundred mutated variants, and that rejects schema keywords it does
  not implement. New or extended checks: stated verdicts must match the scorecards; bare file names must exist;
  the count, retracted-explanation and signing patterns cover the phrasings that escaped. Each has a negative
  control in `tests/test_verification.py`.
- The JOSS version of the methodology paper is about 1,700 words, above the journal's 1,000-word limit; its
  submission guide said 750. The guide now gives the real count, and the paper workflow warns until it is cut.

**Left out** (retrievable from git history, tag `v12.7-final`): the phase 2–4 exploratory pipelines, the CMB and
structure-formation bridges, the ε-framework posteriors, referee and submission-bundle tooling, the archive, and
the 600 tests of that machinery. None of it is used by any registered prediction. The computational core kept
is the five modules the register actually imports.

## Before 20.0 — a short history

The full record is in git history. The events that shaped the current package:

- **Retracted: an "explained anomaly".** An early release claimed to explain the neutron-lifetime beam–trap
  discrepancy. The result came from two cancelling errors; under universal scaling the prediction is no effect.
- **Retracted: the "signed register" claim.** A deposited paper described the register as cryptographically
  signed, which was false: no entry was signed. An internal audit found it; the claim was withdrawn in a
  dedicated honesty pass, and the claim checker was built so that it cannot recur silently.
- **Revival within the data.** The canonical parameter was moved from 10⁻³ (which failed the registered DESI check)
  to 6×10⁻⁴, inside the region already-public data allow, and the registered |z| < 3 rule was restored in scorers
  that had silently tightened it.
- **Corrected: a stale bound.** Paper A had compared a predicted drift of G against a lunar-laser-ranging bound
  from 2007; current bounds exclude that module.
- **Added: exact nulls** in four sectors — matter (P9), photons (P11), nuclear/electronic clocks (P12) and
  gravitational waves (P13) — each with a sudden-death clause.
- **Withdrawn: a redshift-drift sign flip.** P8 had been computed with a toy history that is a coasting universe
  at the canonical parameter; revision r2 shows the drift is indistinguishable from ΛCDM's. The same review found a
  count check that had been passing vacuously and gave every count check a liveness floor.
