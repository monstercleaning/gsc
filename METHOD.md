# Method

How GSC commits to predictions before seeing data, and how the package checks that its own documents tell the
truth about it. This part of the project is independent of whether the physics survives.

## 1. The prediction register

Every prediction lives in one folder under [predictions/](predictions/):

| File | What it is |
|---|---|
| `prediction.md` | The registered statement: claim, tier, target data, scoring rule, kill-test |
| `pipeline_output.json` | The frozen output of the deterministic pipeline that computes the prediction |
| `observed_data.json` | The published measurement it is scored against (when one exists) |
| `scorecard.md` | The verdict at the registered rule, with the SHA-256 of the output it scored |

The pipelines are in [pipelines/](pipelines/) (`predictions_compute_P<N>.py` and `predictions_score_P<N>.py`),
and [PREDICTIONS.md](PREDICTIONS.md) is the status table generated from the register.

**Append-only.** A registered prediction is not to be edited into a different prediction. A correction becomes a
new revision: when the P8 pipeline was found to use a history the package's own data exclude, the old output was
kept as `pipeline_output.r1_superseded.json`, a revision r2 was registered, and both are in the entry. The rule was
broken once. In v12.5 (27 July 2026) six outputs (P1, P2, P4, P5, P8, P9) were regenerated in place after the
canonical exponent was lowered, and P1's verdict went from FAIL to a retrodictive PASS. The change was disclosed, and
the original outputs are now kept as `pipeline_output.v12_2_superseded.json`;
[predictions/HISTORY.md](predictions/HISTORY.md) has the full record. No registered output has been edited in place
since.

**Frozen records.** Registered pipelines and their outputs are records, not documentation. They are not edited
(the one exception is recorded above), and a reorganization must reproduce them byte for byte (it did: every output is byte-identical after the move to
this layout). Document names inside frozen records therefore use the names from the time of registration:

| Name in a frozen record | Current name |
|---|---|
| `GSC_Framework.md` | [THEORY.md](THEORY.md) |
| §12.2.1 / §12.2.1a / §12.2.1b | Kill conditions K0 / K1 / K2 in [THEORY.md](THEORY.md) §8 |
| `predictions_register`, `P1_…` | `predictions/`, `P01_…` |
| `scripts/predictions_…` | `pipelines/predictions_…` |

**Scoring.** Each scorer compares the frozen output with the recorded observation at the registered rule, |z| < 3.
Scorecards are deterministic (no wall-clock stamp; the git commit dates each scoring), so rescoring unchanged
inputs never changes a file.

## 2. What the verdicts do and do not show

- **Retrodictive checks** (P1's worked check, P3, P4, P5, P6, P7, P9, P11, P13) were scored against data that was
  already public when the pipelines were written. They exercise the tooling; they are not evidence that a prediction
  came before its data. P1's check is weaker still: its exponent was chosen from the data it is checked against, and
  its reference value is Planck's r_d, not a DESI measurement (see the flag in the entry).
- **Genuine forward registrations** target unreleased data: P2 (a sky-mean 21 cm spectrum), P8 (ELT/ANDES), P10
  (CTAO) and P12 (two qualifying nuclear-clock epochs). The entries flag limits on these tests. Other targets are
  P1's full five-year DESI target, P14 (the next determinations of early-universe G) and P15 (rotation curves at z ≥ 2). The first five are the tests kill condition K0 counts; P14 carries its own
  clause (THEORY.md §8), and P15 tests a T4 module.
- **Exact nulls** (P9, P11, P12, P13) predict what standard cosmology predicts. They do not distinguish GSC from
  ΛCDM; their value is that one robust violation would end the framework (kill conditions K1 and K2).

### Repeated tests

For N independent qualifying determinations with a two-sided 3σ failure threshold, the chance of at least one
false FAIL is 1 − (1 − 0.0027)ᴺ under the prediction. It reaches 5.3% at N = 20 and 23.7% at N = 100. Shared data
or systematics change this calculation. For future registrations, specify one primary joint likelihood per data
release and require independent confirmation before a core kill, as K1 and K2 already require.

## 3. Timestamping and signing — honest status

The register is content-hashed and timestamped by the public git history. Two further layers:

- **Deposit notarization.** [predictions/MANIFEST.sha256](predictions/MANIFEST.sha256) lists the SHA-256 of every
  registered statement, frozen output and input-data file. Quoting the manifest's own SHA-256
  (`python3 pipelines/make_register_manifest.py --digest`) in a public deposit description makes the deposit date an
  independent, third-party timestamp of the exact register content.
- **GPG signing.** A signing protocol is specified (`pipelines/predictions_sign.py`, a scaffold), but it has not
  been executed: no entry carries a signature. An earlier release overstated this, and the correction is recorded in
  [CHANGELOG.md](CHANGELOG.md).

## 4. Self-verification

`verification/verify_claims.py` binds each load-bearing sentence of the documentation to a machine-checkable fact
about the package, listed in [verification/claims.json](verification/claims.json). It fails when the documents
assert something the package does not do. It checks, among other things:

- that every prose count (predictions, papers, active scorers) matches the register, with a liveness floor so a
  pattern that matches nothing fails instead of passing vacuously;
- that every scorecard's recorded hash matches the output it scored, and every registered output validates against
  the JSON schema it names;
- that every verdict a document states for a prediction matches its scorecard;
- that withdrawn claims (an explained anomaly, a drift sign flip, a signed register) do not reappear unhedged;
- that no registered pipeline uses the coasting toy history with the canonical parameter;
- that every file a living document names, by path or by bare file name, exists in the package (the package is
  standalone);
- that the register manifest and the prediction table are current;
- with `--include-slow`, that every pipeline reproduces its registered output and is deterministic.

`verification/retro_test.py` is the negative control for the checker itself: it must still catch the historical
false signing claim, kept verbatim in `verification/fixtures/historical_false_claim/` (provenance:
[verification/fixtures/README.md](verification/fixtures/README.md)), on at least 10 of its 18 sites. Narrowing the
detector until the inconvenient finding goes quiet breaks this test. More design notes:
[docs/claim_verification.md](docs/claim_verification.md).

## 5. Reproduce everything

Python 3.9 or newer; no third-party packages.

```bash
python3 -m unittest discover -s tests
python3 verification/verify_claims.py --include-slow
python3 verification/retro_test.py
bash pipelines/predictions_compute_all.sh --verify
```

## 6. Adding a prediction

1. Create `predictions/P<NN>_<name>/prediction.md` with the front matter used by existing entries.
2. Add `pipelines/predictions_compute_P<N>.py` (deterministic, no timestamps, `--output` option) and a schema in
   [schemas/](schemas/); run it to write `pipeline_output.json`.
3. If data exist, add `observed_data.json` and `pipelines/predictions_score_P<N>.py`.
4. Add a `### Prediction P<N>` section to [THEORY.md](THEORY.md), then regenerate the table and manifest:
   `python3 pipelines/make_predictions_table.py` and `python3 pipelines/make_register_manifest.py`.
5. Run the verification commands above; the prose counts are checked automatically.
