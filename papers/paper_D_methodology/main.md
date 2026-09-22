# A Pre-Registration Reproducibility Stack for Falsifiable Cosmological Models

## Abstract

We describe an open-source software stack that combines deterministic, schema-validated computational pipelines with an append-only register of content-hashed, publicly time-stamped numerical predictions, intended to make speculative cosmological model-building falsifiable in practice rather than only in principle. The stack is implemented around the Gravitational Structural Collapse (GSC) framework — a scale-covariant alternative to ΛCDM organised as a four-tier epistemic hierarchy — but the architecture is independent of the specific physical claims and is reusable for any model whose predictions can be expressed as numerical functions of well-defined parameter sets.

The contribution is methodological rather than physical: a *publication discipline* designed to make "moving the goalposts" structurally difficult, by separating prediction-generation from data-comparison through a content hash and public (git) timestamp recorded before scoring, with a per-prediction scoring algorithm that resolves to a public pass/fail outcome at the originally-registered confidence level when the corresponding observational data are released. We are explicit (Section 6) that the present release relies on git-history timestamps rather than executed cryptographic signatures, and that most of the worked examples are retrodictive consistency checks rather than genuine forward pre-registrations.

We document the protocol, demonstrate the implementation on fourteen registered predictions (BAO ruler shift, 21cm Cosmic-Dawn signal, neutron-lifetime beam–trap test, CMB cosmic birefringence, strong-CP θ-bound, Kibble–Zurek defect spectrum, gravitational-wave-memory atomic-clock signature, Sandage–Loeb redshift drift, proton-electron mass-ratio constancy, TeV blazar arrival-time dispersion, the distance-duality relation, nuclear–electronic clock-ratio drift, gravitational-wave–electromagnetic distance duality, and early-universe
gravity), describe a self-verification layer that checks the documentation against the package, and discuss adoption considerations for other research programmes.

**Keywords:** reproducibility, pre-registration, cosmology, falsifiability, scientific software.

## 1. Introduction

Cosmological model-building exhibits a structural tension between two desirable properties. Models that are *empirically rich* — explaining many disparate observational signatures with a few parameters — tend to accumulate post-hoc adjustments as new data arrive, eroding their falsifiability. Models that are *strictly falsifiable* — pinned to a single sharp prediction — tend to make commitments early that, in retrospect, did not need to be so sharp. The result is a literature in which "successfully reproduced" cosmological observations were often anticipated by parameter choices made after the data were available, while "decisive falsifying tests" arrive a decade after the relevant model has already drifted.

This paper does not propose a new physical model. It proposes a methodology — implemented in an open-source software stack — that decouples the empirical-richness/falsifiability trade-off from the physical content of the model itself, by reorganising *how* predictions are recorded, time-stamped, and scored.

The proposed methodology has four components:

1. A **deterministic computational pipeline** that, given fixed inputs, always produces byte-identical output. This is implemented through deterministic serialisation, validation of every registered output against a published JSON schema, and SHA-256 content hashing, all standard practices in modern reproducible-research tooling.

2. A **layered claim hierarchy** that separates the model into tiers of epistemic confidence (kinematic, phenomenological, ansatz-level, speculative). Each tier carries an independent kill-test, so adverse review of one tier does not propagate to lower tiers.

3. A **pre-registration register** of numerical predictions, content-hashed and publicly time-stamped (via the append-only git history) ahead of the corresponding observational data for the forward-looking subset. Each entry captures the prediction, the producing pipeline, the scoring algorithm, and the frozen pipeline output as of the registration commit; a register manifest lists the SHA-256 of every registered file. GPG signing is specified by the protocol but is not executed in the current release (Section 6).

4. A **layered publication strategy** in which different model tiers are presented in separate papers, so journal review acts at the granularity at which it can resolve.

We implement these four components in the GSC framework's reproducibility stack and demonstrate the operational workflow end-to-end on fourteen registered cosmological predictions. The stack is licensed under MIT and available at the project repository.

## 2. The Falsifiability Problem in Cosmology

### 2.1 Goalpost-shifting as the dominant failure mode

The standard scientific protection against goalpost-shifting is *blind analysis*: the analyst is denied access to the data until the analysis pipeline is frozen. Blind analysis is widely practiced in particle physics and (increasingly) in cosmology. It addresses one half of the problem — the half where the experimenter unconsciously tunes selections to favour the expected result.

It does not address the other half, which is more pervasive in theory-driven cosmology: the *theorist* tunes the model parameters after the data are public, then claims the model "predicted" the observation. Each round of new data triggers a parameter update, an updated prediction, and a fresh set of "consistencies" with the latest measurements. A model thus tuned cannot, in principle, be falsified by the data: any specific tension is absorbed into the next parameter update.

The standard defence is that "the parameter space is small, so the model is still constrained." This is true for tightly-parametrised models. It is much weaker for the kind of multi-component framework — spanning early-time recombination, late-time expansion, structure formation, gravitational sector, and matter sector — that characterises modern beyond-ΛCDM proposals. The effective dimensionality of post-hoc tuning is large enough that "consistency with current data" provides only weak evidence of model correctness.

### 2.2 Pre-registration as structural answer

Pre-registration — committing to a numerical prediction before the corresponding data are released, in a publicly-verifiable form — closes this loop. It is well-established in clinical medicine and increasingly in psychology; in physics it is rare in theory work but standard in some experimental contexts (e.g., blind analyses in gravitational-wave and particle physics).

Pre-registration in a theory context requires three operational ingredients:

1. **Deterministic prediction pipelines**: the same parameters and the same code must produce byte-identical numerical predictions, so that the prediction can be exactly reproduced from the registered inputs.

2. **Cryptographic signing and time-stamping**: the prediction record must be unforgeable and dated, so that "we predicted X" claims can be distinguished from "we constructed the prediction after seeing the data." The present release implements the time-stamping half (public git history, and a register digest quoted in public deposits); the signing half is specified but not executed (Section 6).

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

All registered pipelines produce byte-identical output for byte-identical input. This is enforced through:

- **Standard library only**: the whole package — pipelines, scorers, tests and checks — runs on a bare Python 3.9+ interpreter, eliminating numerical-library version drift as a source of non-reproducibility.
- **Sorted-output ordering**: every output is serialised with sorted keys, eliminating insertion-order dependence.
- **Deterministic number formatting**: floating-point values are written with Python's shortest round-trip representation, and most pipelines also round to an explicit precision; no output contains a timestamp.
- **Schema validation**: every registered output is validated against the published JSON schema it declares; the claim checker (Section 4.3) runs the validation on every invocation.
- **Content hashing**: every scorecard records the SHA-256 of the output it scored, and a register manifest lists the SHA-256 of every registered statement, output and input-data file.

The combination ensures that the bit-string of any pipeline output is a function only of the registered inputs and the registered code commit. This is the precondition for meaningful pre-registration: if the prediction's value can drift even slightly between runs, the recorded hash is meaningless.

### 3.3 The register manifest

`predictions/MANIFEST.sha256` lists the SHA-256 of every registered statement, frozen output and input-data file. Its own digest summarises the entire register in 64 hexadecimal characters. Quoting that digest in the description of a public deposit (for example on Zenodo or figshare) turns the deposit's date into an independent, third-party timestamp of the exact register content, one that does not depend on the project's own git history. The claim checker verifies that the manifest matches the files and lists every covered file.

### 3.4 The pre-registration register

The register is an append-only directory of one-subdirectory-per-prediction entries, each containing:

- `prediction.md` — the prediction statement, tier label, ansatz and parameters, pipeline reference, target observation, scoring algorithm, and signing fields that are populated only at sign time;
- `pipeline_output.json` — the deterministic pipeline output as of the registration date, validated against its declared JSON schema; its SHA-256 is listed in the register manifest;
- `observed_data.json` — the published measurement the entry is scored against, when one exists;
- `scorecard.md` — produced when the target observational data are available and the scoring algorithm is run; it records the SHA-256 of the output it scored.

The signing protocol (specified; not executed in this release) mutates `prediction.md`'s YAML front-matter to record:

- `signed_by` — author identity (typically email address; resolvable to a GPG key);
- `signature_timestamp` — ISO-8601 UTC timestamp;
- `repo_commit_at_signing` — git commit SHA at the moment of signing;
- `pipeline_output_hash` — SHA-256 of `pipeline_output.json` at the moment of signing;
- `status` — transitions from `SCAFFOLD` to `SIGNED`.

Registered entries are append-only whether or not they are signed. Errors are recorded as superseding revisions that explicitly reference the original, which is preserved: when the redshift-drift prediction P8 was found to use an expansion history excluded by the package's own BAO data, its output was kept as `pipeline_output.r1_superseded.json` and a revision r2 was registered beside it.

### 3.5 The scoring protocol

When the target observational data are released, the scoring pipeline is invoked:

1. Record the SHA-256 of the `pipeline_output.json` being scored; the claim checker later verifies that the recorded hash still matches the frozen output (no silent drift);
2. Load the observational data file in the format declared in `prediction.md`;
3. Run the per-prediction scoring algorithm (typically a z-score against the registered rule |z| < 3);
4. Generate `scorecard.md` with pass/fail outcome at the registered confidence level;
5. Write the scorecard beside the entry without modifying the prediction or its frozen output. Scorecards are deterministic, so rescoring unchanged inputs never changes a file.

Pass/fail outcomes drive tier or module promotion/demotion in the next framework cycle. A failed prediction at the T4 level eliminates the corresponding speculative module; the tiers below survive. A failed prediction at the T2 level triggers framework-wide review.

## 4. Implementation

### 4.1 Technology choices

The stack is implemented in standard-library Python (3.9 or newer). It imports nothing outside the standard library, so there is no dependency list to drift: pipelines, scorers, tests and checks run on a bare interpreter. This minimalism is a design choice: dependency churn is the dominant source of "reproducibility decay" in research software, and an empty dependency list extends the half-life of the reproducibility guarantees. The price is that the registered pipelines are simplified, often parametric computations rather than full Boltzmann-code runs (`OPEN_PROBLEMS.md`, problem 6).

The register tooling (`pipelines/predictions_score.py`, `pipelines/predictions_scoreboard.py`, and the per-prediction compute and score scripts) is part of the same package; the signing helper `pipelines/predictions_sign.py` is a scaffold that has not been executed (Section 6).

### 4.2 Continuous integration

The CI workflow runs four steps:

1. **Unit tests**: `python3 -m unittest discover -s tests` runs the whole test base under the standard library alone.

2. **Claim verification**: `python3 verification/verify_claims.py --include-slow` binds the documentation's load-bearing sentences to facts about the package (Section 4.3); the slow pass recomputes every registered prediction.

3. **Negative control**: `python3 verification/retro_test.py` proves the checker still catches a historical false claim.

4. **Register reproduction**: `bash pipelines/predictions_compute_all.sh --verify` recomputes every registered prediction twice and requires byte-identical agreement with the frozen register.

CI runs on every push; a failure in any step marks the commit as failing.

### 4.3 Self-verification

A methodology paper can overstate its own tooling like any other document. The claim checker (`verification/verify_claims.py`) binds each load-bearing sentence of the documentation to a machine-checkable fact about the package, listed in `verification/claims.json`: prose counts must match the register, stated verdicts must match the scorecards, recorded hashes must match their files, every registered output must validate against its schema, withdrawn claims must not reappear unhedged, and every file a document names must exist in the package. It fails when the documents assert something the package does not do.

The checker is itself tested against a negative control: a verbatim copy of an earlier release that overstated the register as cryptographically signed, when no entry was, must still be caught on at least 10 of its 18 assertion sites (`verification/retro_test.py`). The layer earns its keep on this paper too. Preparing the present revision, the checker's rules were extended after an earlier draft was found to describe tooling from a previous release that this package does not contain, to repeat a retracted claim about the neutron-lifetime anomaly, and to state verdicts that later corrections had changed; the extended rules catch each of these mechanically.

## 5. Case Study: Pre-registered Predictions

We demonstrate the workflow on the fourteen registered predictions of the GSC framework. Detailed records are in `predictions/`, one folder per prediction; here we summarise the methodological aspects.

### 5.1 P1 — BAO standard-ruler shift (forward target: the full five-year DESI release)

The prediction `Δr_s/r_s |_{GSC − ΛCDM}` is computed by `predictions_compute_P1.py`, which extends the existing Eisenstein–Hu (1998) sound-horizon implementation with a parametrised σ-shift factor. The pipeline output is a single JSON record with the ΛCDM baseline `r_d`, the GSC-predicted `r_d`, the relative shift, and the cosmology inputs used.

Its forward target is the full five-year DESI release (the Year-3 data became public in 2025 and serve as retrodictive context). At the canonical parameter the shift is about 2σ at full-survey precision — indicative alone, and its physical coherence is an open problem (OPEN_PROBLEMS.md).

### 5.2 P2 — 21cm Cosmic-Dawn signal

The prediction is the globally-averaged differential brightness temperature `δT_b(ν)` over 70–200 MHz, distinct from ΛCDM through σ-evolution of recombination, Lyman-α coupling, and X-ray heating. The registered implementation is a parametric pipeline (`pipelines/predictions_compute_P2.py`) whose amplification factor is not derived; the full cosmic-dawn module it was meant to become was never built (see OPEN_PROBLEMS.md, problems 3 and 6). Pre-registration is staged for HERA Phase-II precision data (≈ 2027) and SKA-Low (≈ 2030).

### 5.3 P3 — Neutron-lifetime beam–trap test

The pipeline computes the beam and trap lifetimes `(τ_n^beam, τ_n^trap)` under a σ-environmental coupling. Under the canonical, universal scaling the predicted difference is zero, so the registered prediction is a null, and the scorer records a FAIL against the observed ~9-second discrepancy. An earlier release presented this entry as an explanation of the discrepancy; that result came from two cancelling errors and was retracted, and the claim checker now blocks its return (Section 4.3).

### 5.4 P4–P14

The remaining entries follow the same pattern: a pipeline computes the prediction, the output is frozen and hashed in the register, and a scorer compares it with released data when they exist. Two features are worth noting. P8 (redshift drift) is the register's worked example of a correction: its first revision used an expansion history that the package's own data exclude, and the re-registered revision r2 is indistinguishable from ΛCDM at foreseeable precision. P9 and P11–P13 are exact nulls: they predict exactly what ΛCDM predicts in four sectors (matter, photons, nuclear clocks, gravitational waves), so they cannot favour GSC, but a single robust violation would end the framework. P14 shows how the register handles a finding of that
kind: when a joint fit showed that P1's statistic cannot distinguish its only coherent reading from ΛCDM, the
reading's remaining distinct content, weaker gravity in the early universe, was registered as a new forward
prediction rather than used to rescue P1. Per-prediction details are in each entry's `prediction.md`.

## 6. Discussion

### 6.1 What the methodology does and does not provide

The methodology provides:

- A protective barrier against post-hoc parameter tuning for the forward-looking subset (predictions are content-hashed and git-time-stamped before their data exist; GPG signing is future work);
- A structural protection against tier-cross-contamination in journal review (each paper presents one tier);
- A reproducibility guarantee at the byte-identical level for any registered prediction;
- A mechanism for independent checking (anyone can recompute every registered output and rescore it; the result must be byte-identical).

The methodology does *not* provide:

- A guarantee of physical correctness (a model can be wrong even if all its predictions are honestly registered);
- A protection against the *choice* of which observations to register against (the choice of P1–P14 itself reflects researcher selection);
- Evidence of predictive success from retrodictive checks: nine of the fourteen entries were scored against data that were public when their pipelines were written, so their passes exercise the tooling rather than test a prediction made in advance;
- A guarantee against bugs in the prediction pipeline (only that the bug, if present, is reproducibly present).

The first two limitations are inherent to all model-building. The third is removed only by forward registrations scored when their data arrive. The fourth is mitigated by deterministic pipelines and content hashing: a bug is at least exactly reproducible, allowing later identification and correction with an explicit superseding revision, as happened with P8.

### 6.2 Cost and overhead

The total cost of the pre-registration discipline, given the deterministic-pipeline infrastructure already in place, is in the range of *one author-day per prediction registered* and *one to two weeks of initial scaffolding* (scoring scaffolds, register tooling, CI integration). This is small relative to the cost of producing a publishable cosmological model in the first place.

The deterministic-pipeline infrastructure itself — deterministic serialisation, schema validation, content hashing and the claim checker — is the larger upfront cost. We estimate this at 100–200 author-hours for a project of moderate complexity, with most of the work being one-time. Maintenance cost is low if the infrastructure is treated as a core dependency rather than as documentation.

### 6.3 Comparison with prior practice

Pre-registration is not novel in itself. It is widely practiced in clinical medicine (clinicaltrials.gov, since 2007), increasingly in psychology and economics (OSF preregistration, since 2013), and in some experimental physics contexts (blind analyses). What we contribute here is the integration of pre-registration with the broader reproducibility stack — deterministic outputs, schema validation, content hashing, and a checker that binds the documentation to the package — so that the *act* of pre-registration is a routine operation rather than a discipline depending on human consistency.

The closest precedent in gravitational-wave astronomy is the Gravitational Wave Open Science Center, which publishes open data releases together with documented analysis software. Our contribution is to extend comparable openness to *theoretical* model predictions, which historically have not been subjected to comparable discipline.

## 7. Adoption Notes

For other research programmes considering adoption:

1. **Start with the deterministic-pipeline infrastructure.** Pre-registration is meaningless without bit-identical outputs. Deterministic serialisation, schema validation and content hashing are the prerequisites.
2. **Define the tier hierarchy first.** The layered architecture is what allows speculative extensions to coexist with disciplined empirical claims. Without it, the temptation is to either over-commit (everything is a primary claim) or under-commit (everything is "diagnostic only").
3. **Pre-register early and often.** Each pre-registration tightens the model's empirical content. The discipline is most useful when it is routine rather than exceptional.
4. **Treat scoring as appending, not editing.** The scorecard is added to the register; the original prediction is never modified. This is the operational guarantee of falsifiability.
5. **Separate methodology and physics in publication.** A methodology paper independent of the specific physical claims is judged on its own merits, regardless of the physics outcome — but this separation is *not* an escape hatch: the case-study physics is reported honestly under the same framework-level kill condition (kill condition K0 in `THEORY.md`), and a methodology that could not survive scrutiny of its own central claim would not be worth submitting. We submit the methodology paper first.
6. **Check the documentation mechanically.** Bind each load-bearing sentence to a fact a machine can verify, and test the checker against a known false claim. This project's most consequential overstatement survived two hostile-review audits and was finally caught by a one-line mechanical check.

## 8. Conclusions

We have described an open-source software stack that combines deterministic computational pipelines, a layered claim hierarchy, an append-only register of content-hashed and publicly time-stamped predictions, a layered publication strategy, and a checker that binds the documentation to the package, intended to make speculative cosmological model-building falsifiable in operational practice. The stack is implemented around the GSC framework but the architecture is independent of the specific physical claims and is reusable for any model whose predictions can be expressed as numerical functions of well-defined parameters.

The methodological contribution is independent of the truth or falsehood of GSC's specific physical claims: a successful methodology paper, cited and adopted by other groups, is a contribution in itself.

## Code availability

The complete reproducibility stack is available at the project repository under MIT licence. The pre-registration register and per-prediction pipelines are in `predictions/` and `pipelines/`. Independent reproducers are welcome: the four commands in `METHOD.md` §5 reproduce and check everything.

## References

- C. Wetterich, *A Universe without expansion*, arXiv:1303.6878 (2013).
- M. Reuter, F. Saueressig, *Quantum Gravity and the Functional Renormalization Group*, Cambridge University Press (2019).
- Gravitational Wave Open Science Center, https://gwosc.org.
- *Open Science Framework — preregistration in scientific practice*, https://osf.io/preregistration.
