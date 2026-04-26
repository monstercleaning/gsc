# GSC — Project Index

A complete map of the standalone GSC framework package. Use this as the entry point when you need to find anything specific.

## At a glance

- **Theory:** [GSC_Framework.md](GSC_Framework.md) — canonical layered framework (T1 → T4)
- **Methodology:** [docs/tier_hierarchy.md](docs/tier_hierarchy.md) and [docs/pre_registration.md](docs/pre_registration.md)
- **Quick start:** [QUICKSTART.md](QUICKSTART.md) — five-minute end-to-end tour
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- **Citation:** [CITATION.cff](CITATION.cff)

## Predictions (8 of 8, all functional)

| ID | Title | Tier | Pipeline | Schema | Scoring | Outcome |
|---|---|---|---|---|---|---|
| [P1](predictions_register/P1_bao_ruler_shift/) | BAO standard-ruler shift in DESI Year-3 | T2 | ✅ real σ-metrology | ✅ | pending DESI Y3 (2027) | — |
| [P2](predictions_register/P2_21cm_cosmic_dawn/) | 21cm Cosmic-Dawn signal | T2/T3 | ✅ K_σ amplification | ✅ | pending HERA/SKA | — |
| [P3](predictions_register/P3_neutron_lifetime/) | Neutron-lifetime beam-trap | T4 | ✅ corrected σ-environmental (v0.2) | ✅ | ✅ scored vs PDG 2024 | **❌ FAIL** (universal scaling predicts no effect) |
| [P4](predictions_register/P4_cmb_birefringence/) | CMB cosmic birefringence | T3 | ✅ CS line-of-sight | ✅ | ✅ scored vs Planck 2020 | ❌ FAIL at 2σ |
| [P5](predictions_register/P5_strong_cp_bound/) | Strong-CP θ-bound | T3 | ✅ θ-trajectory | ✅ | ✅ scored vs n2EDM 2020 | ✅ PASS (within nEDM) |
| [P6](predictions_register/P6_kz_defect_spectrum/) | Kibble-Zurek defect spectrum | T4 | ✅ KZ scaling | ✅ | ✅ scored vs PTA bounds | ❌ FAIL (excludes default M_*) |
| [P7](predictions_register/P7_gw_memory_clocks/) | GW-memory atomic-clock signature | T4 | ✅ σ-GW coupling | ✅ | ✅ scored vs Al+ clock | ⏸ SUB-THRESHOLD |
| [P8](predictions_register/P8_redshift_drift/) | Redshift-drift sign | T2 (supporting) | ✅ Sandage-Loeb | ✅ | pending ELT (2040+) | — |

**6 scored predictions (post-v12.1 corrections): 1 PASS (P5), 4 FAIL (P3, P4, P6, plus joint-constraint exclusion of σ-axion at literature couplings), 1 SUB-THRESHOLD (P7).** Two predictions await future data (P1, P8).

> **v12.1 corrections sprint** — applied after critical hostile review:
> - **P3 corrected** from PASS → FAIL: the v0.1 PASS was an artefact of two cancelling errors (sign of mass scaling and missing G_F running). Correct sensitivity coefficient under universal coherent scaling is 0 (atomic-clock σ-dependence cancels β-decay σ-dependence). Framework predicts NO beam-trap discrepancy.
> - **Paper B Section 4** corrected: joint-constraint scan now notes that p ≈ 0.1 "PASS" was a scan artefact of omitting P1 from scoring. With P1 in the loop, joint-allowed window is empty at literature couplings.
> - **P1 schema range** loosened (r_s_gsc_predicted_mpc lower bound only) so empirical exclusion is enforced by scorer not by schema.
> - **de Brito-Eichhorn-Lino dos Santos 2022 obstruction** added to Paper B §3.2.1 — directly contradicting σ-axion-equivalence at the dimension-4 level via weak-gravity bound.
> - **Lunar-laser-ranging Ġ/G** check added to Paper A §4.4 — central powerlaw p ≈ 10⁻³ sits at edge of |Ġ/G| < 1.4×10⁻¹³/yr bound.

## Pipeline scripts

```
scripts/
├── predictions_compute_P1.py    # BAO ruler shift compute
├── predictions_compute_P2.py    # 21cm Cosmic Dawn
├── predictions_compute_P3.py    # neutron lifetime
├── predictions_compute_P4.py    # CMB birefringence
├── predictions_compute_P5.py    # strong-CP θ-trajectory
├── predictions_compute_P6.py    # KZ defect spectrum
├── predictions_compute_P7.py    # GW-memory atomic clock
├── predictions_compute_P8.py    # Sandage-Loeb redshift drift
├── predictions_compute_all.sh   # orchestrator (all 8 + verify)
├── predictions_sign.py          # sign protocol (front-matter mutation)
├── predictions_score.py         # generic score (hash verification)
├── predictions_score_P3.py      # P3 → PDG world averages
├── predictions_score_P4.py      # P4 → Planck birefringence hint
└── predictions_scoreboard.py    # text/markdown/json scoreboard
```

## JSON schemas

```
schemas/
├── predictions_p1_pipeline_output_v1.schema.json
├── predictions_p2_pipeline_output_v1.schema.json
├── predictions_p3_pipeline_output_v1.schema.json
├── predictions_p4_pipeline_output_v1.schema.json
├── predictions_p5_pipeline_output_v1.schema.json
├── predictions_p6_pipeline_output_v1.schema.json
├── predictions_p7_pipeline_output_v1.schema.json
└── predictions_p8_pipeline_output_v1.schema.json
```

## Documentation

```
docs/
├── tier_hierarchy.md             ← read second
├── pre_registration.md           ← read third
├── measurement_model.md
├── reproducibility.md
├── claim_ledger.json             # 18 entries with tier annotations
├── ARTIFACT_POLICY.md
├── DATA_LICENSES_AND_SOURCES.md
├── DATA_SOURCES.md
├── DATASET_ONBOARDING_POLICY.md
├── FRAMES_UNITS_INVARIANTS.md
├── perturbations_and_dm_scope.md
├── redshift_drift_beyond_flrw.md
├── redshift_drift_forecast.md
├── rg_asymptotic_safety_bridge.md
├── rg_scale_identification.md
├── risk_register.md
├── sigma_field_origin_status.md
├── structure_formation_status.md
└── ... (30 timeless docs total)
```

## Papers

```
papers/
├── README.md                              # 4-paper layered strategy
├── paper_A_late_time/
│   ├── README.md
│   └── main.md                            # ~2700 word draft (T1+T2 empirical)
├── paper_B_rg_mechanism/
│   └── README.md                          # outline (T3, FRG-dependent)
├── paper_C_extensions/
│   └── README.md                          # outline (T4, vortex DM, QRF)
└── paper_D_methodology/
    ├── README.md
    └── main.md                            # ~2960 word draft (JOSS-ready)
```

## Software stack

```
gsc/                              # core Python package (~52 modules)
├── measurement_model.py          # freeze-frame + Sandage-Loeb
├── histories/                    # σ(t) history classes
├── early_time/                   # rd, CMB priors, microphysics
├── epsilon/                      # σ-translator MVP
├── datasets/                     # SN, BAO, CMB, structure loaders
├── structure/                    # transfer, growth, fσ8
├── pt/                           # Boltzmann export/results
├── rg/                           # RG flow, Padé fit
├── diagnostics/                  # report builders
├── bbn/                          # primordial element constraints
└── ...
```

## CI workflows

```
.github/workflows/
├── v11_0_0_ci.yml                # legacy CI (kept for compatibility)
└── predictions_ci.yml            # NEW: predictions-determinism + schema validation
```

## Archive (provenance only — not part of active codebase)

```
archive/
├── README.md
├── GSC_Framework.md.legacy        # v11.0.0 framework
├── GSC_Framework.tex.legacy       # v11.0.0 LaTeX
├── v10_framework.md               # v10 compact triage
├── v10_1_framework.md             # v10.1 disciplined draft
├── v9_1_changelog.md              # v9.0 → v9.1 transformation log
├── v9_1_deferred_ideas.md         # v9.x → v10 triage notes + critical errors
└── legacy_docs/                   # 44 archived release/phase-specific docs
    ├── README.md
    ├── ARXIV_*.md / JOSS_*.md / PAPER2_*.md   # submission infrastructure
    ├── GSC_Consolidated_Roadmap_v2.5.md / v2.8.md / v2.8.1_patch.md
    ├── external_reviewer_feedback.md
    └── phase_specific_status/                  # 13 Phase-2 / Phase-3 working notes
```

## Common operations

### Compute a single prediction

```bash
python3 scripts/predictions_compute_P3.py
```

### Compute all 8 predictions deterministically

```bash
bash scripts/predictions_compute_all.sh --verify
```

### Sign a prediction (mutates prediction.md front-matter)

```bash
GSC_SIGNER="your.email@example.com" python3 scripts/predictions_sign.py P3
```

Use `--dry-run` to preview without modifying.

### Score a prediction against observed data

```bash
python3 scripts/predictions_score_P3.py            # PDG 2024 world averages → PASS
python3 scripts/predictions_score_P4.py            # Planck 2020 hint → FAIL
```

### View scoreboard

```bash
python3 scripts/predictions_scoreboard.py
python3 scripts/predictions_scoreboard.py --format markdown
python3 scripts/predictions_scoreboard.py --format json
```

### Run the test suite

```bash
# stdlib-only smoke
python3 -m unittest discover -s tests -p test_*.py

# full stack with numpy etc.
bash scripts/bootstrap_venv.sh
.venv/bin/python -m unittest discover -s tests -p test_*.py
```

### Audit repository footprint

```bash
python3 scripts/audit_repo_footprint.py --max-mb 10
```

## Scientific findings to date (post-v12.2 corrections)

| Finding | Evidence | Strength |
|---|---|---|
| **Universal scaling consistent with current μ̇/μ bounds** (HD+ 5×10⁻¹⁷/yr, H₂ at z~2-3) | P9 PASS | ⭐⭐ T1 axiom not falsified |
| **σ-axion equivalence consistent with current n2EDM bound** | P5 PASS within 50% of bound | ⭐⭐ no contradiction with strong-CP probe |
| **σ-axion equivalence in tension with Planck birefringence at literature couplings** | P4 z=-2.5 vs Planck 2020 + de Brito 2022 obstruction | ⭐⭐ useful joint constraint |
| **σ_*-crossing with M_* ≈ GUT excluded by PTA bounds** | P6 with default parameters | ⭐⭐ M_* ≲ TeV required |
| **σ-environmental explanation of τ_n anomaly fails** | P3 v0.2 corrected: universal scaling predicts no anomaly | ⭐ retracted earlier PASS |
| **Powerlaw σ(z) with p ≈ 10⁻³ in tension with DESI Y1 BAO at 4σ** | P1 v12.2 scorer | ⭐ requires σ-modified recombination correction (M201) |
| **Redshift-drift sign-flip at z ≥ 2 vs ΛCDM (ELT/ANDES test)** | P8 calibrated | ⭐ pending observation |
| **Lunar laser ranging Ġ/G at edge of bound for p ≈ 10⁻³** | Paper A §4.4 | ⭐ near-term constraint |

## Status snapshot (post-v12.2 corrections)

```
Standalone size: ~8.4 MB
Predictions: 10/10 deterministic + schema-validated (P1-P10)
Scored predictions: 7/10 with PASS/FAIL/SUB-THRESHOLD verdicts
Paper drafts: 3 of 4 (Paper A empirical, Paper B theoretical with v12.1 corrections, Paper D methodology)
CI: predictions-determinism + schema validation
Tests: 22+ representative core tests passing
Pre-registration: signing + scoring protocols operational end-to-end with 7 active scorers (P1, P3, P4, P5, P6, P7, P9)

Outcome breakdown post-v12.2:
- 2 PASS:           P5 (n2EDM bound), P9 (universal-scaling μ̇/μ = 0)
- 5 FAIL:           P1 (DESI Y1 4σ tension at central p), P3 (universal scaling predicts no anomaly), P4 (Planck β tension), P6 (M_* near GUT excluded)
- 1 SUB-THRESHOLD:  P7 (sub-detector for current k_GW)
- 3 PENDING:        P2 (HERA/SKA), P8 (ELT 2040+), P10 (CTAO 2026-2028)

Honest scientific position: framework has been substantially constrained by current data
on multiple independent channels. No "explained anomaly" claim survives v12.2 corrections.
σ-axion-equivalence claim under serious obstruction (de Brito-Eichhorn 2022 + P4 FAIL).
```

## See also

- [README.md](README.md) — top-level README with quick orientation
- [QUICKSTART.md](QUICKSTART.md) — five-minute tour
- [CHANGELOG.md](CHANGELOG.md) — what changed across cycles
- [GSC_Framework.md](GSC_Framework.md) — full theoretical specification
- [archive/README.md](archive/README.md) — what's in historical provenance
