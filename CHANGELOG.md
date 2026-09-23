# Changelog

## 20.2.0 — in progress

- **a0 tied to dark energy** ([analyses/a0_evolution.md](analyses/a0_evolution.md)): read as a0 ≈ c √Λ, Milgrom's
  coincidence ties the scale at which galaxies show dark matter to the dark-energy density. With DESI DR2's evolving
  dark energy it predicts a0 falling at high redshift, with no free shape parameter. On the 100 RC100 rotation
  curves it fits better than a constant a0 in every variant, weakly (about 2σ at most). It predicts a0 at 38–78% of
  today's at z ≈ 3–5. Recorded in problem 11. The idea was suggested by the same data, so this is a hint to test,
  not evidence.

## 20.1.0 — 2026-09-23 — open problems computed

Physics work on the open problems, starting with the computation that problem 1 called decisive. One forward
prediction was added (P14; fourteen in total), and no registered output changed. Register manifest digest:
`c578bbc1e67f4cdd0653bbfd94e7f7e48736d01a4a104d09c9736a1b4354694f`.

- **Joint CMB + BAO fit** ([analyses/joint_fit.md](analyses/joint_fit.md)). The only coherent reading of P1's shift,
  particle masses drifting relative to the Planck mass before z ≈ 10, was fitted with the cosmological parameters
  free to the Planck 2018 CMB distance priors and the DESI DR2 BAO measurements. It fits as well as ΛCDM
  (Δχ² = −0.09), but the fit absorbs it into H₀ (−0.9%), after which its BAO signature is below 0.005%. P1's
  registered statistic therefore cannot distinguish GSC from ΛCDM. P1 carries an editorial flag, which changes the
  register manifest digest; the kill-condition count is unchanged. What remains distinct is early-universe gravity,
  which no registered test probed before P14, below (OPEN_PROBLEMS.md problems 1, 4 and 5).
- The fit is validated against the priors themselves and against DESI's published ΛCDM results. The
  recombination-redshift formula as printed in the prior paper misses the priors' own central value by 1.8σ; it is
  rescaled once to Planck's z*, as documented in the code. A slow check recomputes every fit in CI.
- **P14 registered** ([predictions/P14_early_gravity/](predictions/P14_early_gravity/)): the early-universe content of
  that reading, gravity weaker relative to atoms by 0.79% at recombination and 2.98% at nucleosynthesis with a fixed
  relation between the two, as a new forward prediction under K0.3. Its registration adds a kill clause: if P14
  fails, K0.4 applies. It is not scored yet, because no current measurement can tell it from G = G₀. The register
  now holds fourteen predictions.
- **Timescape tested** ([analyses/timescape_fit.md](analyses/timescape_fit.md)): Wiltshire's cosmology, in which
  gravity makes clocks and rulers in galaxies differ from the void-dominated average and so mimics dark energy, is
  the published version of GSC's intuition with a known cause. Implemented from Wiltshire (2009) and validated
  against its published numbers, it fits the DESI DR2 BAO shape much worse than ΛCDM (Δχ² = +52; the
  calibration-free Alcock–Paczyński ratio alone gives +45), robustly across checks. Recorded as problem 9; its
  redshift-drift prediction is documented but not registered, because existing data already disfavour the model.
- **Coupled black holes tested** ([analyses/ccbh_fit.md](analyses/ccbh_fit.md)): black holes that grow with the
  expansion and act as dark energy (Ahlen et al., PRL 2025). The expansion history fits nearly as well as ΛCDM
  (Δχ² = +1.7 and +2.6 for two star-formation histories; H₀ ≈ 70.3; about half the baryons converted). H₀ and
  the converted fraction are close to the published analysis, whose fit penalty is larger (Δχ² = +6.1, disfavoured
  at about 2σ). The black-hole growth the model needs is in tension with Gaia, globular-cluster and
  gravitational-wave measurements of black-hole masses. Recorded as problem 10; not registered.
- **Milgrom's acceleration scale tested** ([analyses/a0_evolution.md](analyses/a0_evolution.md)): the scale below
  which galaxies show dark matter, a0, is close to c H₀/2π, so tying it to the expansion rate at each epoch would
  link dark matter to the shrinking itself. Fitted to the 100 rotation curves of RC100 at z = 0.6–2.5 (Table 3
  transcribed and checked; new file [data/rc100_table3.csv](data/rc100_table3.csv)), a0 ∝ H(z) is disfavoured at
  5.1σ (2.8–5.4σ across nine variants), and a constant a0 = 1.18 fits. The one sample in which a0 rises (Ciocan et
  al. 2026, z < 1.44) follows H(z) in its MOND fits but disagrees with RC100 where the two overlap. Recorded as
  problem 11; not registered.
- The P8 r2 history at the canonical p fits the CMB + BAO data worse than ΛCDM (Δχ² = +2.5); added to problem 2.
- New verified data files: DESI DR2 BAO (arXiv:2503.14738 v3) and the Planck 2018 distance priors (Chen, Huang &
  Wang 2019). The old compact DR1 table disagrees with the DESI DR1 paper in several places, including a quasar
  measurement the paper does not contain; it is flagged in [data/README.md](data/README.md), not changed.
- Paper A cited the distance priors to a nonexistent "Chen-Howlett-Whitebook 2018" with "Reference TBD"; it now cites
  Chen, Huang & Wang (2019).
- **Correction: v20.0.0 was not deposited.** The v20.0.0 tag message says the package was deposited on Zenodo and
  figshare. It was not: the upload was postponed, and those records still hold the v12.2 upload. Tags are not
  rewritten, so the correction is recorded here. Wording elsewhere that implied the deposit now calls it planned,
  and the register digest is described as meant for a deposit description, not as already quoted in one.
- **Pre-release review.** An independent review of every 20.1 change found the following, corrected here:
  - P1's editorial flag put the scorer's failure point at the size of the shift instead of a third of it.
  - P14 says that scoring it now would give a PASS; its rule gives SUB-THRESHOLD. An editorial flag records this,
    and P14 stays unscored as registered.
  - Problem 5 counted P5 as distinguishing content, contrary to P14's registration.
  - The comparison with the published black-hole analysis called its fit penalty close.
  - The timescape Alcock–Paczyński range held only for void fractions of 0.6–0.9; the ratio is at least 1.33 for
    every void fraction.
  - THEORY, Paper A, problem 8, the data notes and two planning documents still described the state before the
    joint fit. The data notes also missed a sign error in the DR1 Lyα correlation.

  The P1 and P14 flags change the register manifest digest; no registered text or output changed.

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

**Deposit review.** Checking the package before its planned public deposit found documents that still described an
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
- The reorganization's own reference rewriting had altered history in two places: Paper E attributed a false
  signing statement to METHOD.md (it was made by a file of the earlier release, now linked in its verbatim fixture
  copy), and the claim-verification findings table named THEORY.md where the findings were made on its
  predecessor. Both records are restored.
- The same rewriting renamed the former framework document to THEORY.md inside five registered statements (P1, P4,
  P5, P6, P9), but the two documents number their sections differently, so those statements pointed at the wrong
  section (one at a section that does not exist). The pointers now name the matching section. The statements'
  predictions are unchanged; the register manifest was regenerated, so its digest differs from the first 20.0
  commit.
- Paper A reports a late-time fit whose table holds illustrative values and placeholder Δχ² entries, produced by
  code that is not in this package. Its conclusions and Paper B now carry a flag, and the issue is recorded as
  open problem 8. No registered prediction depends on the fit.
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
