# Pre-Registration

Pre-registration of numerical predictions before observational data are released is a defining methodological *commitment* of the GSC framework, and the register tooling is built to enforce it. The pre-registration register at [predictions_register/](../predictions_register/) is an append-only directory whose entries are content-hashed and publicly time-stamped through git commit history. Cryptographic (GPG) signing is specified by the protocol below but is **not yet executed** in the current release, and most of the worked examples shipped so far are retrodictive consistency checks against already-public data rather than genuine forward pre-registrations — see *Current implementation status* at the end of this document.

## Why pre-register

The single most common failure mode in cosmological model-building is post-hoc parameter adjustment: a model "predicts" data that was already known, with parameters tuned after the fact. Pre-registration eliminates this failure mode by committing to a numerical prediction *before* the corresponding observational data are released.

The goal is to convert the reproducibility infrastructure (deterministic pipelines, schema validation, lineage DAGs) from a *defensive* tool ("here are our results, you can re-run them") toward a *falsification engine* ("here is our prediction, hashed and dated; the scoring rule is fixed in advance") — for the forward-looking predictions to which the discipline genuinely applies.

## What constitutes a pre-registration

Each register entry contains:

- **Prediction statement** — the numerical claim, including its uncertainty band;
- **Tier label** — which tier of the framework the prediction tests (T2, T3, or T4);
- **σ(t) ansatz and parameters** — the specific framework configuration producing the prediction;
- **Pipeline reference** — the script and arguments to compute the prediction;
- **Target observation** — the dataset, the measuring instrument, the expected release date;
- **Scoring algorithm** — how the prediction will be compared to the eventual data;
- **Output hash** — SHA-256 of the deterministic pipeline output as of registration date;
- **Signature and timestamp** — author signature and ISO-8601 timestamp.

## Append-only discipline

Once a prediction is registered, it cannot be modified. If the underlying framework changes (e.g., a parameter is updated, a new σ(t) ansatz is adopted), the *new* configuration produces a *new* register entry; the original entry remains intact for historical scoring.

When the target observational data are released, the corresponding scoring pipeline is run, and a scorecard is produced and added to the register. The scorecard contains:

- The observed value and its uncertainty;
- The pre-registered prediction;
- Pass/fail at the registered confidence level;
- Date of scoring;
- Independent reproducer signatures (optional but encouraged).

## Failure handling

If a prediction is falsified, the corresponding tier or module is **demoted** in the framework. The framework version is incremented, the demoted claim is moved to historical record, and the surviving tiers continue.

Failure of a Tier-4 prediction does not propagate to T1–T3.
Failure of a Tier-3 prediction may eliminate the corresponding T3 ansatz but leaves T1+T2 intact.
Failure of a Tier-2 prediction is structural and triggers framework-wide review.

These demotion rules are themselves bounded. A framework-level kill condition (see `GSC_Framework.md`) converts a pre-specified majority of *forward* pre-registration failures into abandonment of the GSC core — so that per-tier demotion cannot be used to rescue the framework indefinitely, and no new tier-demotion or non-universal extension may be introduced to save a prediction after it has been registered.

## Current pre-registered predictions

See [predictions_register/](../predictions_register/) for the full list. Brief summary:

| ID | Prediction | Tier | Target | Expected release |
|---|---|---|---|---|
| P1 | BAO standard-ruler shift | T2 | DESI Year-3 | 2027 |
| P2 | 21cm Cosmic-Dawn signal | T2/T3 | HERA Phase-II / SKA-Low | 2027–2030 |
| P3 | Neutron-lifetime beam–trap discrepancy | T4 | Ongoing UCNτ etc. | continuous |
| P4 | CMB cosmic birefringence | T3 | Planck (current) / LiteBIRD | 2030 |
| P5 | Strong-CP θ-bound consistency | T3 | nEDM (continuous) | continuous |
| P6 | Kibble-Zurek defect spectrum | T4 | NANOGrav / EPTA / LISA | continuous / 2035 |
| P7 | GW-memory atomic-clock signatures | T4 | ITOC / BACON post-LIGO events | continuous |
| P8 | Redshift-drift sign and amplitude | T2 (supporting) | ELT/ANDES | 2040+ |

## Pre-registration vs. blind analysis

These are complementary, not equivalent. *Blind analysis* hides observational data from the analyst until the analysis pipeline is frozen. *Pre-registration* freezes the prediction before the data are taken. Both can be combined: a pre-registered prediction with a blind scoring step gives the strongest discipline.

For predictions where the target data are already partially public (e.g., DESI Year-1), pre-registration must be done with respect to the *next* unreleased increment, with the prediction including the relevant systematics propagation.

## Implementation

The register is a directory of one-file-per-entry markdown documents with structured front-matter, accompanied by:

- A signing script (`scripts/predictions_sign.py`);
- A scoring orchestrator (`scripts/predictions_score.py`);
- A scoreboard generator (`scripts/predictions_scoreboard.py`).

The scoring orchestrator and scoreboard generator are implemented and exercised by the worked examples. The signing script (`scripts/predictions_sign.py`) is a **reference scaffold and has not been run**: no register entry is GPG-signed in the current release.

## Current implementation status

To avoid the exact post-hoc failure mode this document warns against, we state plainly where the implementation stands as of v12.3:

- **Signing:** Not executed. Every `prediction.md` carries `status: SCAFFOLD`. Pre-registration integrity currently rests on git's public, append-only commit history (content hash + commit timestamp), not on cryptographic signatures.
- **Retrodictive vs. forward:** Seven worked examples (P1, P3, P4, P5, P6, P7, P9) are scored against data that was already public when written; they are consistency checks that exercise the tooling, not forward pre-registrations. Three (P2, P8, P10), plus the BAO test against the *future* DESI Year-3 release, target unreleased data and are the genuine forward pre-registrations.
- **P1 caveat:** The worked P1 `scorecard.md` scores against DESI **Year-1** (public 2024) using a relative-shift statistic; this is a retrodictive consistency check. The *registered* P1 prediction targets DESI **Year-3** (≈2027) and remains unscored.
- **Framework-level falsifiability:** A pre-committed kill condition (see `GSC_Framework.md`) prevents the tier hierarchy from absorbing every failure by demotion.

Promoting the register from git-timestamped to GPG-signed, and scoring the forward predictions when their data arrive, is the principal remaining work.
