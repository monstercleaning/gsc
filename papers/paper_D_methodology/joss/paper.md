---
title: 'GSC: A Pre-Registration Reproducibility Stack for Falsifiable Cosmological Models'
tags:
  - Python
  - cosmology
  - reproducibility
  - pre-registration
  - falsification
  - scientific software
authors:
  - name: Dimitar Baev
    orcid: 0009-0009-7812-9203
    affiliation: 1
affiliations:
 - name: "Independent researcher; Founder, Monster Cleaning Ltd. (https://monstercleaning.com)"
   index: 1
date: 28 May 2026
bibliography: paper.bib
---

# Summary

`GSC` is an open-source Python framework that combines deterministic computational pipelines, a layered claim hierarchy, and an append-only register of content-hashed, publicly time-stamped numerical predictions to make speculative cosmological model-building falsifiable in operational practice. The stack is implemented around the Gravitational Structural Collapse framework — a scale-covariant alternative to standard cosmology — but the architecture is independent of any specific physical claim and is reusable for any model whose predictions can be expressed as numerical functions of well-defined parameters.

The methodological contribution is the *protocol and open-source tooling* for this discipline: a deterministic compute step, a content hash and public (git) timestamp recorded in an append-only register, and a per-prediction scoring algorithm fixed in the register before scoring. The aim is to move the reproducibility infrastructure (schema-validated artifacts, lineage DAGs, content hashing) from a purely defensive tool ("here are our results, you can re-run them") toward a falsification engine ("here is our prediction, hashed and dated; the scoring rule is fixed in advance"). The repository ships with ten worked examples (P1–P10) covering BAO standard-ruler shifts, 21cm Cosmic-Dawn signals, neutron-lifetime experiments, CMB cosmic birefringence, strong-CP θ-bounds, Kibble–Zurek defect spectra, gravitational-wave-memory atomic-clock signatures, redshift drift, proton-electron mass-ratio constancy, and TeV blazar dispersion. We are deliberately explicit about how far the present demonstration reaches: most of these worked examples are scored against already-public data and therefore serve as *retrodictive consistency checks* that exercise the tooling end-to-end, while a forward-looking subset targets unreleased datasets and is registered now to be scored on release (see *Scope and honest limitations*).

# Statement of need

Cosmological model-building exhibits a structural tension between empirical richness — many disparate observations explained by few parameters — and strict falsifiability — pinning to single sharp predictions. Models that are empirically rich tend to accumulate post-hoc adjustments as new data arrive; models that are strictly falsifiable tend to make commitments early that, in retrospect, did not need to be so sharp. The result is a literature in which "successfully reproduced" cosmological observations were often anticipated by parameter choices made after the data were available, while "decisive falsifying tests" arrive a decade after the relevant model has already drifted [@OpenScienceFramework].

The standard scientific protection against this drift is *blind analysis*: the analyst is denied access to the data until the analysis pipeline is frozen. Blind analysis is widely practiced in particle physics and increasingly in cosmology [@LIGO_Open_Science]. It addresses one half of the problem — the half where the experimenter unconsciously tunes selections to favour the expected result. It does not address the other half: the *theorist* tunes the model parameters after the data are public, then claims the model "predicted" the observation.

`GSC` addresses this gap by extending pre-registration discipline — well-established in clinical medicine [@AllPrePost] and increasingly in psychology and economics [@Nosek] — to *theoretical* model predictions. The technical requirements are: (i) deterministic prediction pipelines that produce byte-identical output for byte-identical input; (ii) content-hashing and public time-stamping of registered predictions in an append-only history; and (iii) per-prediction scoring algorithms fixed before scoring. The `GSC` stack provides all three as a working open-source framework and exercises them end-to-end on ten worked examples in cosmology and adjacent fields, with the genuine forward-pre-registration claim restricted to the subset that targets unreleased data.

# Software architecture

The framework is structured around four explicit tiers of epistemic confidence:

- **Tier T1** — kinematic frame (e.g., conformal equivalence FRW ↔ freeze-frame);
- **Tier T2** — phenomenological fit (e.g., σ(t) reproduces SN, BAO, fσ8 data);
- **Tier T3** — physical ansatz (e.g., RG-running gravitational coupling);
- **Tier T4** — speculative extensions (e.g., vortex dark matter from Kibble–Zurek defect formation).

Each tier carries an independent kill-test, so adverse review of one tier does not propagate to lower tiers. The publication strategy mirrors this: separate papers for separate tiers, so journal review acts at the granularity at which it can resolve.

The deterministic pipeline core is implemented in Python with minimal external dependencies (`numpy`, `scipy`, `matplotlib`). The register tooling (`predictions_score.py`, `predictions_scoreboard.py`, and per-prediction `predictions_compute_PN.py` and `predictions_score_PN.py`) is stdlib-only; the GPG-signing helper `predictions_sign.py` is provided as a reference scaffold that is not exercised in this release (see *Scope and honest limitations*). Continuous integration runs three layers: footprint audit, stdlib-only test suite, and full-stack pipeline tests. JSON schemas validate every major artifact; lineage DAGs trace every output back to its inputs through SHA-256 content hashing. A repository footprint cap (10 MB strict) prevents bloat.

# Pre-registration register and signing protocol

The pre-registration register is an append-only directory with one subdirectory per prediction. Each entry contains:

1. `prediction.md` — the prediction statement, tier label, ansatz and parameters, pipeline reference, scoring algorithm, signing fields populated at sign time;
2. `pipeline_output.json` — deterministic pipeline output as of registration date, with SHA-256 hash recorded in `prediction.md`;
3. `observed_data.json` (when available) — the observational dataset to score against;
4. `scorecard.md` (after scoring) — pass/fail outcome at the registered confidence level.

The signing protocol is *designed* to mutate `prediction.md`'s YAML front-matter to record `signed_by`, `signature_timestamp`, `repo_commit_at_signing`, `pipeline_output_hash`, and to transition `status: SCAFFOLD → SIGNED`, after which the entry is treated as immutable and errors are recorded as superseding predictions referencing the original. In the present release this GPG-signing step has **not** been executed: all register entries remain at `status: SCAFFOLD`, and pre-registration integrity for the forward-looking subset therefore rests on git's public, append-only commit history (content hash plus commit timestamp) rather than on detached cryptographic signatures. The scoring protocol *is* implemented: it runs the per-prediction scoring algorithm and appends `scorecard.md` without modifying the original prediction. Promoting the register from git-timestamped to GPG-signed is the principal piece of future work.

# Scope and honest limitations

We state the boundaries of what this release demonstrates, because overstating them would defeat the purpose of the tool.

**Retrodictive vs. forward predictions.** Of the ten worked examples, seven (P1, P3, P4, P5, P6, P7, P9) are scored against datasets that were already public when their pipelines were written. They are therefore *retrodictive consistency checks* that exercise the compute–score–scoreboard path end-to-end; they are **not** evidence that a prediction was committed ahead of its data. Only the subset targeting unreleased data — P2 (HERA Phase-II / SKA-Low), P8 (ELT/ANDES), P10 (CTAO), and the BAO test against the future DESI Year-3 release rather than the Year-1 data used in the worked P1 scorecard — can constitute genuine forward pre-registration, and only once that data arrives.

**The register is git-timestamped, not GPG-signed.** No entry carries a cryptographic signature in this release; integrity rests on the public commit history. We consider this honest but weaker than the signed protocol the tooling is designed for, and we flag it rather than letting the word "signed" stand unqualified.

**Framework-level falsifiability.** A layered tier hierarchy can degenerate into unfalsifiability if every failed prediction is absorbed by demoting it to a lower tier or by adding a bespoke extension. To guard against this we adopt an explicit, pre-committed framework-level kill condition (stated in `GSC_Framework.md`): if a pre-specified majority of the genuinely forward-pre-registered tests fail at their registered confidence, the GSC *core* — not merely the implicated module — is abandoned, and no post-hoc tier-demotion or non-universal extension may be introduced to rescue a prediction after it has been registered.

**The cosmology case study is largely disfavoured, and we report it as such.** The scale-covariant case study's kinematic tier is, by construction, conformally equivalent to ΛCDM and makes no independent observational claim; the apparent BAO and redshift-drift deviations originate in a phenomenological $H(z)$ ansatz rather than in the frame relabeling, and the genuinely scale-symmetry-breaking couplings (birefringence, strong-CP) sit at or beyond current bounds. The methodology — not the cosmology — is the contribution; we make this split explicit precisely so it cannot be used as an escape hatch, and the framework-level kill condition above applies to the case study like any other claim.

# Two hostile-audit cycles as proof-of-concept

To demonstrate that the discipline works as intended, the framework's eight initial predictions (v12.0) were subjected to two independent hostile-review audits. Both audits identified critical errors: the first identified a sign-and-magnitude error in the neutron-lifetime sensitivity coefficient (initially presented as a positive result; corrected to a null result post-audit), an artefactual joint-constraint scan claim, missing citations to directly contradicting literature, and a schema-enforcement gap. The second audit identified the universality contradiction underlying multiple predictions, dimensional inconsistency in another, and stale documentation. All identified issues were either corrected or explicitly retracted in subsequent v12.1 and v12.2 sprints, with the corrections themselves recorded in the changelog and reflected in the public scoring landscape.

This two-audit cycle is the methodology working as intended: errors caught before submission, retracted explicitly, framework status updated transparently. The honest scientific position of GSC after the audits is markedly less flattering than the v12.0 initial release, which is itself the value the discipline provides.

A third audit (v12.3) turned the same hostile scrutiny on this paper and found that an earlier draft overstated its own central claim — describing the register as "cryptographically-signed" and the predictions as "signed and dated before the data" when the signing step was an unexecuted scaffold and most worked examples were retrodictive. That overclaim has been corrected in the text above and documented in the changelog. We report it here rather than quietly editing it, because a methodology paper that could not catch its own most consequential overstatement would not be worth submitting.

# Acknowledgements

We acknowledge the foundational scale-covariant cosmology lineage [@Wetterich2013; @CanutoEtAl1977], the asymptotic-safety quantum-gravity programme [@Reuter1998; @PercacciSaueressig2017], and the operational reproducibility-stack patterns developed by the open-science software community.

# References
