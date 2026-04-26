# Pre-Registration

Pre-registration of numerical predictions before observational data are released is a defining methodological commitment of the GSC framework. The pre-registration register at [predictions_register/](../predictions_register/) is append-only, time-stamped, and cryptographically signed.

## Why pre-register

The single most common failure mode in cosmological model-building is post-hoc parameter adjustment: a model "predicts" data that was already known, with parameters tuned after the fact. Pre-registration eliminates this failure mode by committing to a numerical prediction *before* the corresponding observational data are released.

This converts the reproducibility infrastructure (deterministic pipelines, schema validation, lineage DAGs) from a *defensive* tool ("here are our results, you can re-run them") into a *falsification engine* ("here is our prediction, signed and dated; you cannot move the goalposts").

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

These scripts are part of the current cycle deliverable and are scheduled for implementation in M201.
