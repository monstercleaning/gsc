# Prior Art And Novelty Map

This note makes prior art explicit and keeps novelty claims bounded.
It is a reviewer aid, not a publication claim.

## Map: prior art vs repository scope

| Concept / module / doc | Prior art references (examples) | How GSC differs operationally | Claim boundary |
|---|---|---|---|
| Late-time FLRW distance and expansion observables (`measurement_model`, SN/BAO diagnostics) | Standard FLRW distance ladder and observational cosmology literature | Deterministic script-first packaging, schema-tagged artifacts, and reproducible reviewer packs | No claim of new FLRW theory; this is an operational reproducibility layer |
| CMB compressed-priors bridge (`early_time` compressed diagnostics) | Planck compressed distance priors, CHW2018-style compressed constraints | Uses compressed priors as a bridge diagnostic integrated into deterministic scan/bundle tooling | Not a full TT/TE/EE likelihood or peak-level Boltzmann closure claim |
| Structure diagnostics (`fσ8`, RSD overlays) | Linear growth formalism and RSD observational summaries | Deterministic report tooling with portable outputs and optional nuisance profiling | Not a full perturbation/nonlinear structure-formation closure claim |
| Variable-constants and multi-probe consistency analyses | Toda & Seto (2025), arXiv:2504.09136 (alpha, m_e, combined probes) and broader varying-constants reviews | Explicit epsilon measurement-layer parameterization with deterministic intervention levels and consistency-triangle diagnostics in repository-native artifacts | No claim of a final combined-constraints result; current outputs are scaffold diagnostics with explicit non-claims |
| External Boltzmann integration (CLASS/CAMB export/run/results harness) | Existing CLASS/CAMB ecosystems and standard external-solver workflows | Portable metadata, deterministic pack contracts, and reviewer-facing provenance checks | No in-repo Boltzmann physics reimplementation claim |
| SigmaTensor Phase-3 background scaffolding (`phase3_sigma_tensor_model_v1`) | Canonical scalar-field dark-energy background models and EFT notation | Deterministic background + consistency + export diagnostics wired into candidate triage flow | Background-only scaffolding; no claim of complete perturbation closure |
| Scan/dossier orchestration (`phase3_scan_*`, `phase3_make_*_dossier_pack.py`) | Common parameter-grid and candidate-ranking workflows in computational cosmology | Portable, deterministic scan JSONL contracts with redaction/lint gates and reviewer quicklook reports | No claim that ranking equals global best-fit inference |
| Claim-discipline docs (`REVIEW_START_HERE`, verification matrix, claim lint) | Reproducibility and research-governance best practices | Repo-native, executable claim boundaries tied to tests/scripts | Governance tooling does not by itself validate physics correctness |

## Novelty audit checklist

Use this checklist before adding a new claim or module:

1. Identify prior art explicitly in docs and name at least one external baseline.
2. State what is operationally new (tooling, determinism, packaging, validation) vs scientifically new.
3. Add a bounded claim sentence and at least one explicit non-claim sentence.
4. Wire claim checks to scripts/tests in `docs/VERIFICATION_MATRIX.md`.
5. Add required files to `scripts/phase2_repo_inventory.py` when they become contract-critical.
6. Ensure outputs are portable (no machine-local absolute paths) and deterministic.
7. Run `docs_claims_lint.py` and full unittest discovery before merging.

## Additional prior-art guardrails (M150 update)

- Toda & Seto (2025) style analyses focus on combined probe constraints for varying constants (`alpha`, `m_e`) and data-level consistency.
- Current repository additions differ by making epsilon an explicit measurement-layer parameterization with deterministic intervention levels and consistency-triangle tooling; this is software/methodology scaffolding, not a claim of superior cosmological fit.

## Reviewer guidance

For this repository, the novelty center is reproducible falsification infrastructure and transparent scope boundaries.
Interpret any model-facing diagnostics through that lens unless a stronger claim is explicitly backed by new derivations and tests.
