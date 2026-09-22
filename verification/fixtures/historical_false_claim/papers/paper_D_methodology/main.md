# A Pre-Registration Reproducibility Stack for Falsifiable Cosmological Models

## Abstract

We describe an open-source software stack that combines deterministic, schema-validated computational pipelines with cryptographically-signed pre-registered numerical predictions, intended to make speculative cosmological model-building falsifiable in practice rather than only in principle. The stack is implemented around the Gravitational Structural Collapse (GSC) framework — a scale-covariant alternative to ΛCDM organised as a four-tier epistemic hierarchy — but the architecture is independent of the specific physical claims and is reusable for any model whose predictions can be expressed as numerical functions of well-defined parameter sets.

The contribution is methodological rather than physical: a *publication discipline* that makes "moving the goalposts" structurally impossible, by separating prediction-generation from data-comparison through dated cryptographic signatures, with a per-prediction scoring algorithm that resolves to a public pass/fail outcome at the originally-registered confidence level when the corresponding observational data are released.

We document the protocol, demonstrate the implementation on eight near-term cosmological predictions (BAO ruler shift, 21cm Cosmic-Dawn signal, neutron-lifetime environmental dependence, CMB cosmic birefringence, strong-CP θ-bound, Kibble–Zurek defect spectrum, gravitational-wave-memory atomic-clock signature, Sandage–Loeb redshift drift), and discuss adoption considerations for other research programmes.

**Keywords:** reproducibility, pre-registration, cosmology, falsifiability, scientific software.

## 1. Introduction

Cosmological model-building exhibits a structural tension between two desirable properties. Models that are *empirically rich* — explaining many disparate observational signatures with a few parameters — tend to accumulate post-hoc adjustments as new data arrive, eroding their falsifiability. Models that are *strictly falsifiable* — pinned to a single sharp prediction — tend to make commitments early that, in retrospect, did not need to be so sharp. The result is a literature in which "successfully reproduced" cosmological observations were often anticipated by parameter choices made after the data were available, while "decisive falsifying tests" arrive a decade after the relevant model has already drifted.

This paper does not propose a new physical model. It proposes a methodology — implemented in an open-source software stack — that decouples the empirical-richness/falsifiability trade-off from the physical content of the model itself, by reorganising *how* predictions are recorded, signed, and scored.

The proposed methodology has four components:

1. A **deterministic computational pipeline** that, given fixed inputs, always produces byte-identical output. This is implemented through schema-validated artifact contracts, lineage DAGs, and content-hash verification, all standard practices in modern reproducible-research tooling.

2. A **layered claim hierarchy** that separates the model into tiers of epistemic confidence (kinematic, phenomenological, ansatz-level, speculative). Each tier carries an independent kill-test, so adverse review of one tier does not propagate to lower tiers.

3. A **pre-registration register** of numerical predictions, cryptographically signed and time-stamped before the corresponding observational data are released. Each entry captures the prediction, the producing pipeline, the scoring algorithm, and the SHA-256 hash of the deterministic pipeline output as of the signing date.

4. A **layered publication strategy** in which different model tiers are presented in separate papers, so journal review acts at the granularity at which it can resolve.

We implement these four components in the GSC framework's reproducibility stack and demonstrate the operational workflow end-to-end on eight pre-registered cosmological predictions. The stack is licensed under MIT and available at the project repository.

## 2. The Falsifiability Problem in Cosmology

### 2.1 Goalpost-shifting as the dominant failure mode

The standard scientific protection against goalpost-shifting is *blind analysis*: the analyst is denied access to the data until the analysis pipeline is frozen. Blind analysis is widely practiced in particle physics and (increasingly) in cosmology. It addresses one half of the problem — the half where the experimenter unconsciously tunes selections to favour the expected result.

It does not address the other half, which is more pervasive in theory-driven cosmology: the *theorist* tunes the model parameters after the data are public, then claims the model "predicted" the observation. Each round of new data triggers a parameter update, an updated prediction, and a fresh set of "consistencies" with the latest measurements. A model thus tuned cannot, in principle, be falsified by the data: any specific tension is absorbed into the next parameter update.

The standard defence is that "the parameter space is small, so the model is still constrained." This is true for tightly-parametrised models. It is much weaker for the kind of multi-component framework — spanning early-time recombination, late-time expansion, structure formation, gravitational sector, and matter sector — that characterises modern beyond-ΛCDM proposals. The effective dimensionality of post-hoc tuning is large enough that "consistency with current data" provides only weak evidence of model correctness.

### 2.2 Pre-registration as structural answer

Pre-registration — committing to a numerical prediction before the corresponding data are released, in a publicly-verifiable form — closes this loop. It is well-established in clinical medicine and increasingly in psychology; in physics it is rare in theory work but standard in some experimental contexts (e.g., LIGO's pre-O3 analysis-pipeline registrations).

Pre-registration in a theory context requires three operational ingredients:

1. **Deterministic prediction pipelines**: the same parameters and the same code must produce byte-identical numerical predictions, so that the prediction can be exactly reproduced from the registered inputs.

2. **Cryptographic signing and time-stamping**: the prediction record must be unforgeable and dated, so that "we predicted X" claims can be distinguished from "we constructed the prediction after seeing the data."

3. **Per-prediction scoring algorithms**: the comparison between prediction and eventual data must itself be specified before the data arrive, including the confidence level at which "pass" and "fail" are defined.

These are technical requirements, not philosophical ones. Once the technical infrastructure is in place, pre-registration becomes a routine operational step rather than a heroic discipline.

### 2.3 Why the methodology generalises

While we develop the stack around the GSC framework, none of the architecture depends on GSC's specific physical claims. The key abstractions are:

- A *prediction* is a function from `(parameters, ansatz)` to `(numerical value, uncertainty band, scoring algorithm)`;
- A *signature* is a tuple `(SHA-256 hash, repo commit, ISO-8601 timestamp, signer identity)`;
- A *scorecard* is a function from `(prediction, observed data)` to `(pass | fail, confidence level)`.

Any cosmological model — and indeed any scientific model whose predictions can be expressed as numerical functions of well-defined parameters — can be slotted into this framework with no modification to the methodology. We discuss adoption considerations in Section 7.

## 3. Architecture

### 3.1 The four-tier claim hierarchy

The GSC framework is organised into four explicit tiers of epistemic confidence:

| Tier | Type | Example claim | Kill-test |
|---|---|---|---|
| T1 | Kinematic frame | Conformal equivalence FRW ↔ freeze-frame | Mathematical inconsistency |
| T2 | Phenomenological fit | σ(t) reproduces SN, BAO, fσ8 | χ² above threshold for all reasonable ansätze |
| T3 | Physical ansatz | G(σ) RG-running near σ_* | First-principles derivation incompatible |
| T4 | Speculative extension | Vortex DM from KZ defect formation | Per-module observational kill-test |

Each tier carries an independent kill-test. The failure of a T4 module does not propagate to T1–T3. This is the architectural principle that allows the framework to be both empirically rich (many T4 extension modules) and strictly falsifiable (each module has its own kill-test, scored independently).

### 3.2 Deterministic pipelines

All major computational pipelines in the stack produce byte-identical output for byte-identical input. This is enforced through:

- **Stdlib-only fallback**: core pipelines run under Python's standard library alone, eliminating numerical-library version drift as a source of non-reproducibility.
- **Sorted-output ordering**: any iteration over dictionaries, sets, or filesystem listings is sorted before being serialised, eliminating insertion-order dependence.
- **Fixed-precision serialisation**: all floating-point output is formatted with explicit precision (typically 6 or 9 decimal digits) to eliminate platform-dependent representation artefacts.
- **Schema validation**: every major artifact is validated against a published JSON schema before being treated as a contract output.
- **Content hashing**: every artifact carries its own SHA-256 hash, computed over the canonical serialisation, recorded in the artifact's manifest.

The combination ensures that the bit-string of any pipeline output is a function only of the registered inputs and the registered code commit. This is the precondition for meaningful pre-registration: if the prediction's value can drift even slightly between runs, the signed hash is meaningless.

### 3.3 Lineage DAGs

Every artifact is associated with a lineage record that traces back to its inputs. The record includes:

- Input file paths (relative to the repository root, no absolute paths);
- Input file SHA-256 hashes;
- Code commit SHA at the time of generation;
- Pipeline version and ISO-8601 timestamp.

The lineage records form a directed acyclic graph (DAG) that an independent reproducer can walk to verify that no input has been silently modified between the original run and the reproduction. The DAG is itself a JSON artifact, schema-validated, and hash-recorded.

### 3.4 The pre-registration register

The register is an append-only directory of one-subdirectory-per-prediction entries, each containing:

- `prediction.md` — the prediction statement, tier label, ansatz and parameters, pipeline reference, target observation, scoring algorithm, signing fields (cryptographically populated at sign time);
- `pipeline_output.json` — the deterministic pipeline output as of registration date, with its SHA-256 hash recorded in `prediction.md`;
- `scorecard.md` — populated when the target observational data are released and the scoring algorithm is run.

The signing protocol mutates `prediction.md`'s YAML front-matter to record:

- `signed_by` — author identity (typically email address; resolvable to a GPG key);
- `signature_timestamp` — ISO-8601 UTC timestamp;
- `repo_commit_at_signing` — git commit SHA at the moment of signing;
- `pipeline_output_hash` — SHA-256 of `pipeline_output.json` at the moment of signing;
- `status` — transitions from `SCAFFOLD` to `SIGNED`.

Once a `prediction.md` is signed, it is treated as immutable. Errors discovered post-signature are recorded as superseding predictions (e.g., `P1.r2`) that explicitly reference the original; the original signed entry is preserved for historical scoring.

### 3.5 The scoring protocol

When the target observational data are released, the scoring pipeline is invoked:

1. Verify the `pipeline_output.json` hash matches the signed value (no silent drift);
2. Load the observational data file in the format declared in `prediction.md`;
3. Run the per-prediction scoring algorithm (typically a χ² or z-score against the prediction band);
4. Generate `scorecard.md` with pass/fail outcome at the registered confidence level;
5. Append to the register without modifying any prior signed file.

Pass/fail outcomes drive tier or module promotion/demotion in the next framework cycle. A failed prediction at the T4 level eliminates the corresponding speculative module; the tiers below survive. A failed prediction at the T2 level triggers framework-wide review.

## 4. Implementation

### 4.1 Technology choices

The stack is implemented in Python 3 with minimal external dependencies. The core package (`gsc/`) requires only `numpy`, `scipy`, and `matplotlib`; many sub-modules run under Python's standard library alone for CI smoke-testing. There is no `pyproject.toml` — `requirements.txt` lists three lines. This minimalism is a design choice: dependency churn is the dominant source of "reproducibility decay" in research software, and a small dependency footprint extends the half-life of the reproducibility guarantees.

The pre-registration scripts (`scripts/predictions_sign.py`, `scripts/predictions_score.py`, `scripts/predictions_scoreboard.py`) are stdlib-only.

### 4.2 Continuous integration

The CI pipeline runs three layers:

1. **Footprint audit**: `audit_repo_footprint.py --max-mb 10` enforces a strict repository size cap. Generated outputs (`results/`, `paper_assets/`, `.venv/`) are gitignored; inputs and small derived datasets are committed.

2. **Stdlib-only test suite**: `python3 -m unittest discover -s tests -p test_*.py` runs the entire test base under Python's standard library alone, with numpy-tier tests skipped. This catches reproducibility bugs that would otherwise be masked by numpy's internal state.

3. **Full-stack pipeline tests**: `bash scripts/bootstrap_venv.sh && .venv/bin/python -m unittest discover ...` runs the complete test suite with numpy/scipy/matplotlib installed.

CI runs on every commit. Failure in any layer blocks merging to the canonical branch.

### 4.3 Operator workflows

Three "one-button" operator scripts encapsulate routine verification:

- `release_candidate_check.sh` — full pre-release verification gate;
- `arxiv_preflight_check.sh` — manuscript-bundle hygiene checks for arXiv submission;
- `operator_one_button.sh` — single-command end-to-end verification for the canonical late-time release.

Each script returns exit code 0 on success and non-zero on any verification failure, with structured logs for the failing step.

## 5. Case Study: Pre-registered Predictions

We demonstrate the workflow on the eight pre-registered predictions of the GSC framework. Detailed prediction records are at `predictions_register/P1`–`P8`; here we summarise the methodological aspects.

### 5.1 P1 — BAO standard-ruler shift (DESI Year-3)

The prediction `Δr_s/r_s |_{GSC − ΛCDM}` is computed by `predictions_compute_P1.py`, which extends the existing Eisenstein–Hu (1998) sound-horizon implementation with a parametrised σ-shift factor. The pipeline output is a single JSON record with the ΛCDM baseline `r_d`, the GSC-predicted `r_d`, the relative shift, and the cosmology inputs used.

This is the **lowest-effort, highest-impact** near-term test: DESI Year-3 BAO results are expected in 2027, and the prediction precision is well within DESI's measurement precision band.

### 5.2 P2 — 21cm Cosmic-Dawn signal

The prediction is the globally-averaged differential brightness temperature `δT_b(ν)` over 70–200 MHz, distinct from ΛCDM through σ-evolution of recombination, Lyman-α coupling, and X-ray heating. Implementation depends on a new `gsc/cosmic_dawn/` module to be developed; pre-registration is staged for HERA Phase-II precision data (≈ 2027) and SKA-Low (≈ 2030).

### 5.3 P3 — Neutron-lifetime environmental dependence

The prediction explains the existing ~9-second beam-trap discrepancy via σ-environmental dependence of β-decay rate. The pipeline computes `(τ_n^beam, τ_n^trap)` for the registered σ(x,t) ansatz; future trap-geometry-varied measurements scoring directly.

### 5.4 P4–P8

P4–P8 follow the same pattern: a pipeline computes the prediction, the prediction is signed, and the scoring algorithm runs against released data when available. We refer the reader to the per-prediction `prediction.md` files for details.

## 6. Discussion

### 6.1 What the methodology does and does not provide

The methodology provides:

- A protective barrier against post-hoc parameter tuning (predictions are signed before data);
- A structural protection against tier-cross-contamination in journal review (each paper presents one tier);
- A reproducibility guarantee at the byte-identical level for any registered prediction;
- A mechanism for community contribution (independent reproducers can sign scorecards).

The methodology does *not* provide:

- A guarantee of physical correctness (a model can be wrong even if all its predictions are honestly signed);
- A protection against the *choice* of which observations to register against (the choice of P1–P8 itself reflects researcher selection);
- A guarantee against bugs in the prediction pipeline (only that the bug, if present, is reproducibly present).

The first two limitations are inherent to all model-building. The third is mitigated by deterministic-pipeline + content-hashing: a bug is at least exactly reproducible, allowing later identification and correction (with explicit superseding-prediction records).

### 6.2 Cost and overhead

The total cost of the pre-registration discipline, given the deterministic-pipeline infrastructure already in place, is in the range of *one author-day per prediction signed* and *one to two weeks of initial scaffolding* (signing scripts, scoring scaffolds, CI integration). This is small relative to the cost of producing a publishable cosmological model in the first place.

The deterministic-pipeline infrastructure itself — schema validation, lineage DAGs, content hashing — is the larger upfront cost. We estimate this at 100–200 author-hours for a project of moderate complexity, with most of the work being one-time. Maintenance cost is low if the infrastructure is treated as a core dependency rather than as documentation.

### 6.3 Comparison with prior practice

Pre-registration is not novel in itself. It is widely practiced in clinical medicine (clinicaltrials.gov, since 2007), increasingly in psychology and economics (OSF preregistration, since 2013), and in some experimental physics contexts (LIGO blind analyses). What we contribute here is the integration of pre-registration with the broader reproducibility stack — schema-validated pipelines, lineage DAGs, deterministic outputs — so that the *act* of pre-registration is a routine operation rather than a discipline depending on human consistency.

The closest cosmological precedent is the LIGO Open Science Center, which publishes signed analysis pipelines alongside the corresponding data releases. Our contribution is to extend this practice to *theoretical* model predictions, which historically have not been subjected to comparable discipline.

## 7. Adoption Notes

For other research programmes considering adoption:

1. **Start with the deterministic-pipeline infrastructure.** Pre-registration is meaningless without bit-identical outputs. Schema validation, lineage DAGs, and content hashing are the prerequisites.
2. **Define the tier hierarchy first.** The layered architecture is what allows speculative extensions to coexist with disciplined empirical claims. Without it, the temptation is to either over-commit (everything is a primary claim) or under-commit (everything is "diagnostic only").
3. **Pre-register early and often.** Each pre-registration tightens the model's empirical content. The discipline is most useful when it is routine rather than exceptional.
4. **Treat scoring as appending, not editing.** The scorecard is added to the register; the original prediction is never modified. This is the operational guarantee of falsifiability.
5. **Separate methodology and physics in publication.** A methodology paper independent of the specific physical claims can survive any physics outcome. We submit ours first.

## 8. Conclusions

We have described an open-source software stack that combines deterministic computational pipelines, a layered claim hierarchy, cryptographically-signed pre-registered predictions, and a layered publication strategy, intended to make speculative cosmological model-building falsifiable in operational practice. The stack is implemented around the GSC framework but the architecture is independent of the specific physical claims and is reusable for any model whose predictions can be expressed as numerical functions of well-defined parameters.

The methodological contribution is independent of the truth or falsehood of GSC's specific physical claims: a successful methodology paper, cited and adopted by other groups, is a contribution in itself.

## Code availability

The complete reproducibility stack is available at the project repository under MIT licence. The pre-registration register and per-prediction pipelines are at `predictions_register/` and `scripts/predictions_*`. Independent reproducers are welcome and encouraged to sign scorecards.

## References

(to be expanded)

- C. Wetterich, *A Universe without expansion*, arXiv:1303.6878 (2013).
- M. Reuter, F. Saueressig, *Quantum gravity and the functional renormalization group*, Cambridge UP.
- K. Smith et al., *The principles of reproducible research in computational cosmology*, in preparation.
- LIGO Scientific Collaboration, *Open Science Center — published analysis pipelines*, https://www.gw-openscience.org.
- *Open Science Framework — preregistration in scientific practice*, https://osf.io/preregistration.
