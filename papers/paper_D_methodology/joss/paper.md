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
date: 26 April 2026
bibliography: paper.bib
---

# Summary

`GSC` is an open-source Python framework that combines deterministic computational pipelines, a layered claim hierarchy, and cryptographically-signed pre-registered numerical predictions to make speculative cosmological model-building falsifiable in operational practice. The stack is implemented around the Gravitational Structural Collapse framework — a scale-covariant alternative to standard cosmology — but the architecture is independent of any specific physical claim and is reusable for any model whose predictions can be expressed as numerical functions of well-defined parameters.

The methodological contribution is the *publication discipline* that the stack enables: predictions are signed and time-stamped before the corresponding observational data are released, with the per-prediction scoring algorithm specified in advance. This converts the existing reproducibility infrastructure (schema-validated artifacts, lineage DAGs, content hashing) from a defensive tool ("here are our results, you can re-run them") into a falsification engine ("here is our prediction, signed and dated; you cannot move the goalposts"). The repository ships with ten worked examples (P1–P10) covering BAO standard-ruler shifts, 21cm Cosmic-Dawn signals, neutron-lifetime experiments, CMB cosmic birefringence, strong-CP θ-bounds, Kibble–Zurek defect spectra, gravitational-wave-memory atomic-clock signatures, redshift drift, proton-electron mass-ratio constancy, and TeV blazar dispersion.

# Statement of need

Cosmological model-building exhibits a structural tension between empirical richness — many disparate observations explained by few parameters — and strict falsifiability — pinning to single sharp predictions. Models that are empirically rich tend to accumulate post-hoc adjustments as new data arrive; models that are strictly falsifiable tend to make commitments early that, in retrospect, did not need to be so sharp. The result is a literature in which "successfully reproduced" cosmological observations were often anticipated by parameter choices made after the data were available, while "decisive falsifying tests" arrive a decade after the relevant model has already drifted [@OpenScienceFramework].

The standard scientific protection against this drift is *blind analysis*: the analyst is denied access to the data until the analysis pipeline is frozen. Blind analysis is widely practiced in particle physics and increasingly in cosmology [@LIGO_Open_Science]. It addresses one half of the problem — the half where the experimenter unconsciously tunes selections to favour the expected result. It does not address the other half: the *theorist* tunes the model parameters after the data are public, then claims the model "predicted" the observation.

`GSC` addresses this gap by extending pre-registration discipline — well-established in clinical medicine [@AllPrePost] and increasingly in psychology and economics [@Nosek] — to *theoretical* model predictions. The technical requirements are: (i) deterministic prediction pipelines that produce byte-identical output for byte-identical input; (ii) cryptographic signing and time-stamping of registered predictions; and (iii) per-prediction scoring algorithms specified in advance. The `GSC` stack provides all three as a working open-source framework, demonstrated end-to-end on ten predictions in cosmology and adjacent fields.

# Software architecture

The framework is structured around four explicit tiers of epistemic confidence:

- **Tier T1** — kinematic frame (e.g., conformal equivalence FRW ↔ freeze-frame);
- **Tier T2** — phenomenological fit (e.g., σ(t) reproduces SN, BAO, fσ8 data);
- **Tier T3** — physical ansatz (e.g., RG-running gravitational coupling);
- **Tier T4** — speculative extensions (e.g., vortex dark matter from Kibble–Zurek defect formation).

Each tier carries an independent kill-test, so adverse review of one tier does not propagate to lower tiers. The publication strategy mirrors this: separate papers for separate tiers, so journal review acts at the granularity at which it can resolve.

The deterministic pipeline core is implemented in Python with minimal external dependencies (`numpy`, `scipy`, `matplotlib`). The pre-registration scripts (`predictions_sign.py`, `predictions_score.py`, `predictions_scoreboard.py`, and per-prediction `predictions_compute_PN.py` and `predictions_score_PN.py`) are stdlib-only. Continuous integration runs three layers: footprint audit, stdlib-only test suite, and full-stack pipeline tests. JSON schemas validate every major artifact; lineage DAGs trace every output back to its inputs through SHA-256 content hashing. A repository footprint cap (10 MB strict) prevents bloat.

# Pre-registration register and signing protocol

The pre-registration register is an append-only directory with one subdirectory per prediction. Each entry contains:

1. `prediction.md` — the prediction statement, tier label, ansatz and parameters, pipeline reference, scoring algorithm, signing fields populated at sign time;
2. `pipeline_output.json` — deterministic pipeline output as of registration date, with SHA-256 hash recorded in `prediction.md`;
3. `observed_data.json` (when available) — the observational dataset to score against;
4. `scorecard.md` (after scoring) — pass/fail outcome at the registered confidence level.

The signing protocol mutates `prediction.md`'s YAML front-matter to record `signed_by`, `signature_timestamp`, `repo_commit_at_signing`, `pipeline_output_hash`, and transitions `status: SCAFFOLD → SIGNED`. Once signed, the entry is treated as immutable; errors discovered post-signature are recorded as superseding predictions explicitly referencing the original. The scoring protocol verifies the recorded hash against the on-disk pipeline output (no silent drift), runs the per-prediction scoring algorithm, and appends `scorecard.md` without modifying the original prediction.

# Two hostile-audit cycles as proof-of-concept

To demonstrate that the discipline works as intended, the framework's eight initial predictions (v12.0) were subjected to two independent hostile-review audits. Both audits identified critical errors: the first identified a sign-and-magnitude error in the neutron-lifetime sensitivity coefficient (initially presented as a positive result; corrected to a null result post-audit), an artefactual joint-constraint scan claim, missing citations to directly contradicting literature, and a schema-enforcement gap. The second audit identified the universality contradiction underlying multiple predictions, dimensional inconsistency in another, and stale documentation. All identified issues were either corrected or explicitly retracted in subsequent v12.1 and v12.2 sprints, with the corrections themselves recorded in the changelog and reflected in the public scoring landscape.

This two-audit cycle is the methodology working as intended: errors caught before submission, retracted explicitly, framework status updated transparently. The honest scientific position of GSC after the audits is markedly less flattering than the v12.0 initial release, which is itself the value the discipline provides.

# Acknowledgements

We acknowledge the foundational scale-covariant cosmology lineage [@Wetterich2013; @CanutoEtAl1977], the asymptotic-safety quantum-gravity programme [@Reuter1998; @PercacciSaueressig2017], and the operational reproducibility-stack patterns developed by the open-science software community.

# References
