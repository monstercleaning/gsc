# GSC — Gravitational Structural Collapse

A scale-covariant cosmology framework with renormalization-group-running gravity, organized as a layered theory with pre-registered falsification.

## What this is

GSC reframes cosmological redshift via a *freeze-frame measurement model*: an approximately static background spacetime in which a universal scale field σ(t) drives the coherent shrinkage of bound matter (atoms, hadrons), while local dimensionless physics remains invariant. The mechanism for σ-evolution is renormalization-group flow of the gravitational coupling near a critical scale σ_*.

The framework is structured as four explicit tiers of epistemic confidence (kinematic frame → phenomenological fit → physical ansatz → speculative extensions), each with independent kill-tests, so that failure of any one module does not propagate to the others.

## Read first

- [GSC_Framework.md](GSC_Framework.md) — the canonical theoretical framework (start here).
- [docs/measurement_model.md](docs/measurement_model.md) — the freeze-frame measurement model (operational core).
- [docs/tier_hierarchy.md](docs/tier_hierarchy.md) — the architectural principle.
- [docs/pre_registration.md](docs/pre_registration.md) — pre-registration of predictions.

## Repository layout

```
.
├── GSC_Framework.md             # Canonical theoretical framework
├── README.md                    # This file
├── CITATION.cff                 # Citation metadata
├── LICENSE                      # MIT
├── requirements.txt             # Python dependencies
├── artifacts.json               # Machine-readable artifact manifest
│
├── gsc/                         # Core Python package
├── scripts/                     # Reproducible pipelines + CLI entry points
├── tests/                       # Unit and integration tests
├── schemas/                     # JSON schemas for artifact validation
├── data/                        # Committed datasets (SN, BAO, CMB, drift, structure)
├── docs/                        # Documentation, claim ledger, roadmaps
├── bridges/                     # Optional bridge packages (early-time, structure, QCD)
├── containers/                  # Reproducible container definitions
├── papers/                      # Multi-paper publication scaffold (A, B, C, D)
├── predictions_register/        # Pre-registered predictions and scoring pipelines
└── archive/                     # Historical framework drafts (provenance only)
```

## Quick start

Self-contained Python environment:

```bash
bash scripts/bootstrap_venv.sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Stdlib-only smoke (no extra deps):

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Reproducible late-time pipeline (fit + figures):

```bash
bash scripts/reproduce_late_time.sh
```

Repository footprint audit (size cap):

```bash
python3 scripts/audit_repo_footprint.py --max-mb 10
```

## The four-paper publication strategy

The framework is published as four layered papers, isolated by tier:

| Paper | Scope | Tier | Venue |
|---|---|---|---|
| **A** | [Late-time empirical fit](papers/paper_A_late_time/) | T1+T2 | Phys. Rev. D / JCAP |
| **B** | [RG mechanism for G(σ)](papers/paper_B_rg_mechanism/) | T3 | CQG / JHEP |
| **C** | [Speculative extensions](papers/paper_C_extensions/) | T4 | Foundations of Physics / Universe |
| **D** | [Methodology and software](papers/paper_D_methodology/) | meta | JOSS / SoftwareX |

Adverse review of any one layer does not invalidate the others.

## Pre-registered predictions

Eight central predictions are documented in [predictions_register/](predictions_register/), each with:

- The numerical prediction and its uncertainty band;
- The σ(t) ansatz and parameter values producing it;
- The relevant scripts and pipeline invocation;
- The target observational dataset and its expected release date;
- A SHA-256 hash of the corresponding scoring pipeline output.

The register converts the reproducibility infrastructure from a defensive tool into a falsification engine.

## Reproducibility guarantees

- Schema validation on all major artifacts.
- Deterministic ordering and lineage DAGs.
- Portable-content lints (no machine-local paths in shared bundles).
- Operator scripts: `release_candidate_check.sh`, `arxiv_preflight_check.sh`, `operator_one_button.sh`.
- CI: stdlib-only smoke + full-stack pipeline tests.
- Strict repository footprint cap.

## Honesty statement

GSC's core kinematic claim — the conformal equivalence between FRW expansion and freeze-frame shrinkage — is not original to this work. See **C. Wetterich, *A Universe without expansion*, arXiv:1303.6878 (2013)** and the asymptotic-safety lineage in [GSC_Framework.md §0](GSC_Framework.md). GSC is positioned as a specific RG-crossover realization within this lineage, with the original contributions being:

1. The layered-tier architecture and pre-registration discipline;
2. The σ-axion equivalence proposal for the strong CP problem;
3. The Kibble–Zurek derivation of vortex-DM density from σ_*-crossing;
4. Multiple specific near-term observational predictions (BAO ruler shift, 21cm Cosmic-Dawn, neutron-lifetime environmental dependence, GW-memory atomic-clock signatures);
5. The deterministic reproducibility stack as a publishable contribution in its own right.

Limitations and open problems are listed explicitly in [GSC_Framework.md §12](GSC_Framework.md).

## Contributing and feedback

- Open issues in the repository for technical questions or replication problems.
- Pre-registered predictions are append-only; once signed and dated, they cannot be modified.
- Cross-checks against alternative scale-covariant frameworks are welcome.

## License

MIT. See [LICENSE](LICENSE).

## Citation

See [CITATION.cff](CITATION.cff).
