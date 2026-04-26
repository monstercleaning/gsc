# CHANGELOG

Notable changes to GSC across framework cycles. Internal cycle markers are retained for traceability.

## [Current cycle, v12.2 corrections sprint] — April 2026

### Triggered by Agent 3 hostile-audit findings

A second hostile-review audit (post-v12.1) identified five additional HIGH-severity issues. All five have been corrected in v12.2:

- **Universality contradiction resolved.** GSC_Framework.md §3.3 substantially rewritten as new §3.3.1 ("The non-universality question and its consistency"). The previous framework was inconsistent: it FAILed P3 because the σ-environmental coupling required non-universal extension (forbidden under strict T1), while at the same time PASSing P4/P5 which require non-universal σ-F̃F coupling. The v12.2 resolution: non-universal extensions ARE admissible as T3/T4-level extensions, each with its own observational bounds. P3, P4, P5 are now on equal footing.

- **P1 schema enforcement gap closed.** The v12.1 had loosened the P1 schema upper bound on `r_s_gsc_predicted_mpc`, with a note promising scorer enforcement; the scorer did not exist. **v12.2 adds `predictions_score_P1.py`** which scores predicted Δr_s/r_s against DESI Y1 relative precision. P1 is now SCORED. Result: even at the canonical p ≈ 10⁻³, the leading-order σ-metrology shift exceeds DESI Y1 precision at ~4σ. The σ-modified recombination correction (gating M201) is required to reduce the prediction to consistency.

- **P10 dimensional consistency repaired.** The v12.1 P10 declared k_grad as "dimensionless" but the formula σ²_t = k_grad² × d_L × ε required k_grad to have units of √s. **v12.2 corrects to k_grad in s × m^(-1/2) (SI units).** Default value changed from 1e-15 to 3e-23 to maintain order-of-magnitude correctness. Schema updated correspondingly.

- **INDEX.md stale claims removed.** The "scientific findings to date" table previously claimed P3 explained the unsolved 4σ neutron-lifetime anomaly with ⭐⭐⭐ rating. **v12.2 retracts this** to "P3 σ-environmental explanation fails" with explicit note that the v12.0 PASS was retracted in v12.1. The "first scientific finding" line in the status snapshot is removed.

- **Paper A §4.4 LLR framing strengthened.** The v12.1 described the LLR Ġ/G constraint as "right at the edge of the bound." **v12.2 strengthens this to "current observational tension"**, noting that the GSC central powerlaw value Ġ/G ≈ -1.4 × 10⁻¹³/yr is essentially equal to the central LLR best-fit residual (2 ± 7 × 10⁻¹³/yr). Combined with P1 v12.2 scorer (DESI Y1 4σ tension), the powerlaw σ(z) ansatz with p ≈ 10⁻³ is in tension with two independent existing measurements simultaneously.

- **P9 reframing as honest consistency test.** v12.1 P9 was tautological under universal scaling. **v12.2 P9** explicitly frames itself as a consistency test of the geometric-lock axiom, with the non-universal opt-in mode parametrising η_diff = η_QCD - η_Higgs as a joint-test against the literature-grounded couplings of P4/P5.

### Honest scientific snapshot post-v12.2

```
P1:  FAIL — DESI Y1 4σ tension at canonical p (NEW SCORER in v12.2)
P2:  PENDING (HERA/SKA, 2027-2030)
P3:  FAIL — universal scaling predicts no anomaly (CORRECTED in v12.1)
P4:  FAIL at literature couplings + de Brito 2022 obstruction
P5:  PASS — within nEDM bound
P6:  FAIL — KZ defects with default M_* excluded by PTAs
P7:  SUB-THRESHOLD — needs FRG-derived k_GW or improved clocks
P8:  PENDING (ELT, 2040+)
P9:  PASS — universal-scaling null prediction (T1 consistency check)
P10: PENDING — sub-detector at corrected k_grad parametric value
```

The framework now records: **2 PASS (P5, P9), 5 FAIL (P1, P3, P4, P6, plus joint σ-axion exclusion), 1 SUB-THRESHOLD (P7), 3 PENDING (P2, P8, P10)**. Four FAIL results constraining/excluding parameter regions on independent observational channels (BAO, neutron lifetime, CMB birefringence, PTA stochastic GW).

The framework is in serious tension with current data. No "explained anomaly" claim survives. The σ-axion-equivalence claim is challenged by both Paper B §4 joint-constraint exclusion AND the de Brito-Eichhorn-Lino dos Santos 2022 obstruction. Submission readiness is contingent on either (a) σ-modified recombination correction reducing P1 BAO tension OR (b) acceptance of a substantially smaller p (p ≪ 10⁻³) which would in turn reduce the σ-evolution amplitude.

This is the *honest scientific position* of GSC after two hostile-audit cycles.

---

## [Current cycle, v12.1 corrections sprint] — April 2026

### CRITICAL corrections (post hostile-review audit)

A critical hostile-review audit identified five fundamental problems in the v12.0 release. All have been corrected in v12.1:

- **P3 sensitivity coefficient corrected.** The v12.0 prediction used d ln(τ_n)/d ln(σ) = -5; the correct value under universal coherent scaling is **0** (σ-dependence in τ_n^physical cancels with σ-dependence in atomic-clock-measured time). The v12.0 PASS verdict for "GSC explains the beam-trap anomaly" was an artefact of two cancelling errors (sign of mass scaling, missing G_F running). **The corrected outcome is FAIL**: GSC predicts no beam-trap discrepancy under universal scaling. The framework's "first explained anomaly" claim is retracted. A non-universal-coupling opt-in mode is preserved as `--non-universal` in `predictions_compute_P3.py` for parameter-space exploration but is flagged as geometric-lock-violating.

- **Paper B Section 4 joint-constraint scan corrected.** The v12.0 scan ignored P1 (no scorer at scan time), giving an artefactual "PASS-only at p ≈ 0.1" verdict. At p = 0.1 the registered P1 pipeline gives r_s^GSC ≈ 302 Mpc (vs DESI Y1 ≈ 147 Mpc) — excluded at >50σ. With P1 in the loop, **the joint-allowed window is empty at literature-grounded couplings**. Section 4 of `papers/paper_B_rg_mechanism/main.md` rewritten to acknowledge this; three honest paths forward documented.

- **P1 schema range loosened.** The v12.0 schema required r_s_gsc_predicted_mpc ∈ [100, 200] Mpc. Large GSC parameter values produce values outside this range that should be empirically excluded by scorer, not by schema. Lower bound only (`exclusiveMinimum: 0`) now; schema_note documents the design.

- **de Brito-Eichhorn-Lino dos Santos 2022 obstruction added to Paper B §3.2.1.** The cited Eichhorn & Versteegen 2018 paper does not actually support the σ-F̃F coupling claim (it studied Higgs-portal sectors, not topological operators). The same author group's [JHEP 06 (2022) 013](https://link.springer.com/article/10.1007/JHEP06(2022)013) tentatively concludes that ALP-like couplings cannot be accommodated in asymptotic-safety + matter due to weak-gravity bound — a direct counter-result. Paper B now addresses this obstruction explicitly, identifying three escape routes the FRG calculation must address.

- **Lunar-laser-ranging Ġ/G check added to Paper A §4.4.** Under G ∝ σ², powerlaw p = 10⁻³ implies Ġ/G ≈ -1.4×10⁻¹³/yr — at the edge of the LLR bound |Ġ/G| < (1-4)×10⁻¹³/yr. Paper A now documents this constraint, which complements the BAO upper limit on p.

### New predictions added

- **P9 — Constancy of μ = m_p/m_e under universal coherent scaling.** Tier T1 consistency check. Under strict universal scaling, GSC predicts μ̇/μ = 0 to all orders; current PASS at lab (HD+, 5×10⁻¹⁷/yr) and cosmological (H₂ absorbers, |Δμ/μ| < 10⁻⁶ at z~2-3) bounds. A non-universal-coupling opt-in mode is included for differential-coupling exploration.

- **P10 — TeV blazar arrival-time dispersion (energy-flat, structure-correlated).** Tier T4 σ(x) spatial-extension test. Under σ(x,t) field-theoretic extension, GSC predicts energy-FLAT stochastic dispersion proportional to ∫(∇σ)² dℓ — distinct from QG-LIV which is energy-DEPENDENT. CTAO archival data (commissioning 2026, science 2027) is the target. Currently sub-threshold for any current detector at the parametric k_grad amplitude, but provides a discriminator vs QG-LIV.

### Honest scientific snapshot post-corrections

```
P1:  PENDING (DESI Y3, 2027) — calibrated, signed-ready
P2:  PENDING (HERA/SKA, 2027-2030) — calibrated
P3:  FAIL — universal scaling predicts no anomaly; v12.0 PASS retracted
P4:  FAIL at literature couplings — joint with P5 implies σ-axion may not survive
P5:  PASS — within nEDM bound (only surviving PASS among σ-coupling tests)
P6:  FAIL — KZ defects with default M_* excluded by PTA bounds
P7:  SUB-THRESHOLD — needs FRG-derived k_GW or improved clocks
P8:  PENDING (ELT, 2040+) — calibrated
P9:  PASS — universal-scaling null prediction consistent with current data
P10: SCAFFOLD — sub-threshold at current k_grad parametric value
```

The framework now records: 2 PASS (P5, P9), 4 FAIL (P3, P4, P6, joint σ-axion), 1 SUB-THRESHOLD (P7), 3 PENDING (P1, P2, P8), 1 NEW PARAMETRIC (P10). Joint-allowed window for σ-axion at literature couplings is empty.

This is a markedly less flattering picture than the v12.0 release, which claimed P3 as a major positive result. It is also markedly more *honest*. Pre-registration discipline is now demonstrating its central value: pre-registered predictions can be falsified, and the framework's actual scientific status reflects what the data and theory currently support.

---

## [Current cycle, v12.0 release] — April 2026

### Architecture

- **Layered tier hierarchy** introduced (T1 kinematic frame, T2 phenomenological fit, T3 RG ansatz, T4 speculative extensions). Each tier carries an independent kill-test.
- **Four-paper publication strategy** replacing the prior single-paper scope. Papers A (empirical), B (theoretical), C (extensions), D (methodology) align with tier boundaries.
- **Pre-registration register** introduced as primary methodological commitment. Eight (then ten) signed-and-dated predictions (P1–P10) with associated scoring pipelines.

### New theoretical content

- **σ-axion equivalence claim** (Section 4 of GSC_Framework.md): the gravitational fixed-point's renormalization of the QCD topological operator generates an automatic σ-F̃F coupling, providing cosmological θ-relaxation without a separate axion field. Status: structural argument; later challenged in v12.1 by de Brito et al. 2022 obstruction.
- **σ_* candidate derivations** (Section 3.5): two parallel routes — non-commutative IR/UV mixing and AdS/QCD warp factor — replacing the prior purely phenomenological treatment.
- **Vortex DM from Kibble–Zurek defect formation** (Section 5).
- **Spatial σ(x,t) extension** (Section 6): σ promoted from σ(t) to a field with spatial gradients, unifying MOND phenomenology with cosmological evolution.
- **σ as cosmological quantum reference frame** (Section 8).
- **σ ≡ RG-flow time** (Section 7.3): conceptual identification with Connes thermal-time hypothesis.

### Reframed from prior cycles

- **Redshift-drift sign discriminator** (P8) demoted from primary to *supporting* falsifier.
- **Lineage statement upfront** acknowledging Wetterich (2013) "Universe without expansion" as the primary precursor.
- **Vortex DM**, **information-thermodynamic gravity**, **holographic proton**, and **σ-θ relaxation** restored from v9.1 archive with dimensional-error corrections.

### Reproducibility

- Pre-registration scripts: `predictions_sign.py`, `predictions_score.py`, `predictions_scoreboard.py`.
- Tier-tagged claim ledger (`docs/claim_ledger.json`) with positive claims labelled by tier and kill-test.
- Layered paper scaffold; Paper A (empirical) and Paper D (methodology) draft-ready; Paper B drafted; Paper C remains outline.

### Cleaned

- Repository organised as standalone package (no version-suffix in user-facing names).
- 44 release-cycle and phase-specific status documents archived to `archive/legacy_docs/`.
- `docs/` reduced to 30 timeless physics and methodology documents.

---

## Predecessor cycles (provenance only)

Detailed prior changelogs and release notes are retained in `archive/`:

- `archive/v9_1_changelog.md` — section-by-section v9.0 → v9.1 transformation;
- `archive/v9_1_deferred_ideas.md` — ideas triaged out of v10 and the dimensional-error log;
- `archive/v10_framework.md` — the compact v10.0 triage draft;
- `archive/v10_1_framework.md` — the v10.1 disciplined draft;
- `archive/GSC_Framework.md.legacy` — the v11.0.0 canonical theoretical framework.

These document the full lineage from the v8/v9.1 maximalism through the v10/v10.1 triage to the v11.0.0 reproducibility-stack consolidation — all of which inform the layered architecture of the current cycle.
