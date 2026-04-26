# Quick Start

A five-minute tour of the GSC framework: read the theory, reproduce a prediction, sign and score it.

## Prerequisites

- Python 3.9+
- Git (for commit-SHA capture in the signing protocol)
- Optional: `numpy`, `scipy`, `matplotlib` for the full late-time fit pipeline. The pre-registration scripts are stdlib-only.

## Five minutes, end-to-end

### 1. Read the framework (1 min)

```bash
less GSC_Framework.md            # canonical theoretical specification
less docs/tier_hierarchy.md      # the four-tier architectural principle
less docs/pre_registration.md    # the methodological commitment
```

### 2. List the pre-registered predictions (10 sec)

```bash
python3 scripts/predictions_scoreboard.py
```

Output:

```
ID    TIER            STATUS      TITLE
--------------------------------------------------------------------------------
P1    T2              UNSIGNED    BAO standard-ruler shift in DESI Year-3
P2    T2/T3           UNSIGNED    21cm Cosmic-Dawn signal ...
...
```

### 3. Compute a prediction (10 sec)

```bash
python3 scripts/predictions_compute_P1.py
```

Produces `predictions_register/P1_bao_ruler_shift/pipeline_output.json` with the GSC-predicted BAO ruler shift Δr_s/r_s, computed from the registered σ(z) ansatz parameters. Output is deterministic — running it twice yields identical SHA-256.

For the redshift-drift prediction:

```bash
python3 scripts/predictions_compute_P8.py
```

Output shows the Sandage–Loeb drift Δv at z = 0.1 to 5.0 for both ΛCDM and GSC, including which redshifts exhibit a *sign flip* between the two.

### 4. Sign the prediction (1 sec)

```bash
GSC_SIGNER="your.email@example.com" python3 scripts/predictions_sign.py P1
```

This mutates `predictions_register/P1_bao_ruler_shift/prediction.md`'s YAML front-matter to record:

- `status: SIGNED`
- `signed_by: your.email@example.com`
- `signature_timestamp: <ISO-8601 UTC>`
- `repo_commit_at_signing: <git SHA>`
- `pipeline_output_hash: <SHA-256 of pipeline_output.json>`

After signing, the prediction is treated as immutable. Errors discovered post-signature are recorded as superseding entries (`P1.r2`).

Use `--dry-run` to preview without modifying.

### 5. Score against observed data

For predictions where the observational data already exists, dedicated scoring
scripts produce a `scorecard.md` with pass/fail at the registered confidence
level. The framework currently ships scorers for P3, P4, P5, P6, P7, P9:

```bash
# P3 — neutron lifetime vs PDG 2024  → FAIL (universal scaling predicts no anomaly)
python3 scripts/predictions_score_P3.py

# P4 — CMB birefringence vs Planck 2020 hint  → FAIL at 2σ
python3 scripts/predictions_score_P4.py

# P5 — strong-CP θ vs n2EDM  → PASS within bound
python3 scripts/predictions_score_P5.py

# P6 — KZ defect spectrum vs PTA upper bounds  → FAIL (excludes M_* near GUT)
python3 scripts/predictions_score_P6.py

# P7 — GW-memory + atomic clocks  → SUB-THRESHOLD
python3 scripts/predictions_score_P7.py

# P9 — μ = m_p/m_e constancy vs HD+ and H₂ bounds  → PASS (null prediction holds)
python3 scripts/predictions_score_P9.py
```

In v12.1 (post-correction), the scoring landscape is **2 PASS (P5, P9), 4 FAIL
(P3, P4, P6, joint σ-axion), 1 SUB-THRESHOLD (P7), 3 PENDING (P1, P2, P8)**, and
P10 (TeV blazar dispersion) awaits CTAO data. The FAIL on P3 reverses an
earlier (v12.0) PASS verdict — a sign that the pre-registration discipline is
working: errors caught early, retracted explicitly, framework status updated.

The FAIL verdict for P4 is itself useful: it tells us the σ-Chern-Simons
coupling g_CS must be larger than the registered value (FRG-dependent, Paper B),
the σ-evolution stronger than the late-time fit allows, or the Planck hint
originates from a different mechanism. Pre-registration lets us discover this
constraint cleanly, without post-hoc tuning.

For predictions whose target data have not yet been released (P1 BAO Year-3,
P8 ELT drift, P2 SKA 21cm, P7 future GW events with clock-array stacking, P6
LISA stochastic background, P5 future tighter nEDM), the corresponding
scorers are added once the data arrive, with the same template as
`predictions_score_P3.py` / `predictions_score_P4.py`.

The generic `predictions_score.py` (hash-verification only) is also available
as a sanity check on any prediction:

```bash
python3 scripts/predictions_score.py P3
```

## What just happened?

You exercised the full pre-registration workflow:

1. **Computed** a prediction from the registered framework parameters using a deterministic pipeline;
2. **Signed** it with a cryptographic record (hash + timestamp + git commit);
3. **Prepared** to score it against observational data when released.

This is the operational core of the framework: predictions are signed *before* observation, and scoring is purely mechanical — there is no opportunity for post-hoc parameter tuning.

## Where to go next

| If you want to... | Read this |
|---|---|
| Understand the physics | [GSC_Framework.md](GSC_Framework.md) |
| Understand the methodology | [docs/pre_registration.md](docs/pre_registration.md) and [docs/tier_hierarchy.md](docs/tier_hierarchy.md) |
| Add a new prediction | The eight existing prediction directories at `predictions_register/PN_*` are templates |
| Read or contribute to a paper | [papers/README.md](papers/README.md) lists the four-paper publication strategy |
| Run the full late-time fit | `bash scripts/bootstrap_venv.sh && .venv/bin/python -m scripts.late_time_fit_grid --help` |
| Audit the repository | `python3 scripts/audit_repo_footprint.py --max-mb 10` |
| Run the test suite | `python3 -m unittest discover -s tests -p test_*.py` (stdlib-only smoke) |
| Verify a release bundle | `bash scripts/release_candidate_check.sh` |

## Common operations

**List predictions in markdown format:**

```bash
python3 scripts/predictions_scoreboard.py --format markdown > scoreboard.md
```

**List predictions in JSON format:**

```bash
python3 scripts/predictions_scoreboard.py --format json
```

**Run a P1 with a specific σ-ansatz exponent:**

```bash
python3 scripts/predictions_compute_P1.py --ansatz powerlaw --p 0.0005
```

**Run a P8 with a different ELT integration time:**

```bash
python3 scripts/predictions_compute_P8.py --years 20
```

**Verify the deterministic output hash matches between two runs:**

```bash
python3 scripts/predictions_compute_P1.py 2>&1 | grep SHA
python3 scripts/predictions_compute_P1.py 2>&1 | grep SHA
# the two SHA values must be identical
```

## Troubleshooting

**`error: prediction.md missing required front-matter fields`** — the prediction has not been initialised. Check `predictions_register/PN_*/prediction.md` exists and has YAML front-matter at the top.

**`error: missing pipeline_output.json`** — run `python3 scripts/predictions_compute_PN.py` first to generate it.

**`error: prediction status is SIGNED; only SCAFFOLD/DRAFT predictions may be signed`** — the prediction has already been signed. To register a corrected version, copy the directory to `PN.r2_*/` and edit the front-matter to `status: SCAFFOLD`.

**Two consecutive runs of `predictions_compute_PN.py` produce different SHA-256** — this is a determinism violation. Open an issue immediately. Likely culprits: timestamps embedded in the output, dictionary iteration order, or floating-point platform dependencies.

## Limits and caveats

- The current P1 implementation includes only the **leading-order σ-metrology shift**. Second-order σ-modified recombination physics (modified z_drag, modified c_s(z) inside the sound-horizon integral) is gating work for the M201 milestone.
- The signing protocol records signature metadata in YAML front-matter but does not yet GPG-sign the prediction directory bundle. GPG integration is scheduled for M201.
- P2–P7 have detailed prediction.md scaffolds but no compute pipelines yet. P3 (neutron lifetime) is the next-priority implementation.
- The σ(z) ansatz parameters used in the default P1 and P8 runs are illustrative defaults, not the values from the actual late-time fit. Calibration against the late-time fit is part of the M201 work.

These caveats are explicitly documented in each prediction's `prediction.md` and in `GSC_Framework.md §12 (Honest Limitations)`.
