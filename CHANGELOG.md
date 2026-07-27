# CHANGELOG

Notable changes to GSC across framework cycles. Internal cycle markers are retained for traceability.

## [v12.6 frontier-sweep cycle] — July 2026

A constructive research sweep that cut both ways, exactly as the revival bargain requires. Three decorrelated research agents surveyed the 2025–26 observational and theory frontier under the verify-every-citation discipline; every load-bearing number was then independently re-verified before any of it touched the framework. Full synthesis: `docs/observational_frontier_2026.md`.

**The Ġ/G correction (the sweep's first casualty was our own text).** Paper A §4.4 (v12.5 and earlier) benchmarked the T3 module's Ġ/G ≈ −8.4×10⁻¹⁴/yr against "(2±7)×10⁻¹³/yr (Hofmann & Müller 2018)". That was doubly wrong: the number is the 2007-era LLR result, and H&M 2018 actually reported (7.1±7.6)×10⁻¹⁴/yr. Verified current bounds — LLR (Biskupek, Müller & Torre 2021, arXiv:2012.12032): (−5.0±9.6)×10⁻¹⁵/yr; MESSENGER (Genova et al. 2018): |Ġ/G| < 4×10⁻¹⁴/yr — **exclude the unscreened, locally observable G ∝ σ² module at canonical p at |z| ≈ 8.2**. This is a pre-registered T3 kill-channel (§3.4; `docs/claim_ledger.json`) firing on data published 2018–2021: the correction is ours, not the data's. Consequences, all executed this cycle: (a) the module exclusion is recorded (Paper A §4.4 rewritten with the bounds table and disclosure; framework §3.4 status; INDEX); (b) the geometric lock's exact local null Ġ/G ≡ 0 becomes a sharpened T1 claim under a new sudden-death clause **§12.2.1b** (local-invariance family: Ġ/G, α, μ, nuclear/electronic ratios); (c) LLR/ephemerides are removed from the constraint budget for p — the v12.5 "constrained by DESI DR1-era data and LLR" overstated LLR's role; BAO was and is the binding constraint, so **p = 6×10⁻⁴ and the +0.417% shift are unchanged**; (d) the previously unnoticed contradiction between Paper A §4.4 ("allowed, 8× under") and the Phase-4 bridge verdict KT-004 ("KILLED — unscreened local G variation tightly bounded") is resolved in the bridge's favor.

**P12 registered — the framework's first hadronic-sector null (genuine forward registration).** d ln(ν_Th-229m/ν_Sr-87)/dt = 0 exactly, parameter-free, under the T1 lock. Anchor: the first nuclear–electronic frequency ratio, 4.707072615078(18) (Zhang et al., Nature 633, 63 (2024), arXiv:2406.18719); measured α-sensitivity K = 5900(2300) (arXiv:2407.17300); closed-loop solid-state Th-229 clocks already running at 3×10⁻¹²√(τ/s) and constraining strong-sector drifts (arXiv:2606.04997). Registered with exactly one public epoch — the forward content is every future epoch. No scorer ships until a qualifying second epoch exists (active-scorer count stays 8, honestly). Register count 11 → 12 across all prose (enforced by `verify_claims`); framework §9.12; kill-condition scope grows to five forward tests with the majority threshold numerically unchanged at three.

**Frontier synthesis, threats recorded with equal prominence.** New standing threats ledger (frontier doc §3): the DESI DR2 extended-analysis preference for phantom-crossing w(z) (arXiv:2503.14743) — which no canonical scalar can produce, so GSC stands or falls with the quasi-ΛCDM family there; ACT DR6 birefringence at 2.9σ nonzero (arXiv:2509.13654) squeezing the already-FAIL σ-axion module; and the ~5-year metrology-closure window (megamasers + NGLR-class ranging + BepiColombo) that will remove the calibration freedom currently absorbing the +0.417% shift. Feeds: the Wetterich dilaton-gravity scaling-solution line is now peer-reviewed through PRD 113, 106023 (2026) (arXiv:2512.14009) and is the canonical anchor for the §12.1 σ_* route; the r_d ↔ w₀wₐ degeneracy is formalized (Adi, JCAP 03 (2026) 015) with GSC's shift on the more-apparent-dynamical-DE side — magnitude an open calculation, registered as an M-task, no claim made. P13 candidate (GW–EM duality Ξ₀ ≡ 1; GWTC-4.0/5.0) queued with numbers to verify at registration.

**Housekeeping found by the sweep.** `docs/pre_registration.md`'s summary table had silently stopped at P8 since v12.0 (P9–P11 were missing); completed through P12. The DESI "Year-3 (2027)" stale target in the same table corrected to the full-survey release, matching the v12.5 correction elsewhere.

**Legacy-suite reconciliation (same cycle): the standing red CI turned out to be three stale registries, not stale docs.** The "v11.0.0 CI (Late-Time)" workflow had been red on every push since the v12 layout landed. Diagnosis against the actual failure logs (not the assumed doc-layout story): (1) the M152 v10-filename hygiene guard was firing on 22 *legitimate* v12-package files (its allowlist predated the v12 package, and its `parents[2]` root assumption escapes the repository entirely in the public root layout) — rewritten layout-aware, with a normalized package-relative allowlist, git-tracked-files enumeration (a repo-hygiene guard polices what the repo tracks, not an operator's local scratch dirs), kept byte-identical in both test trees; (2) `docs_claims_lint.py`'s registry still pointed at the v11 doc layout, reporting 27 `missing_file` violations for docs that v12 had *relocated* into `archive/legacy_docs/` — repointed to the real locations so every content rule stays live on the archived files (an archived doc must not carry overclaims either), with the three genuinely-absent targets moved to an explicit `RETIRED_V11_REL_FILES` list rather than silently dropped; (3) `docs_claim_ledger_lint.py` applied the v1 three-status vocabulary to the deliberately-extended `gsc_claim_ledger_v2` schema — now v2-aware, enforcing the *stronger* v2 contract (tier + non-empty kill_test on every entry, negative-controls verified). The M139 required-docs test was likewise repointed and now also requires the v12 package's living entry-point docs; its cross-tree `../v11.0.0` lint call (impossible in the public layout) now lints its own package. Result, measured after the fixes (completed in a second pass the same day): **both suites fully green** — v12: 626 tests, 0 failures, 24 documented skips; v11: 629 tests, 0 failures. The second pass reconciled the remaining stale-expectation classes: the red-team checker's inventory registry (`phase2_repo_inventory.py`) repointed the same relocations and now audits **its own package** by default instead of a `v11.0.0` sibling (its serialized paths are package-relative — no more machine-local prefixes); tests targeting the consciously-retired v10.1 monolithic paper, paper-2 bundle, and outreach pack now skip through a **self-enforcing gate** (`tests/_v12_layout.py`): a skip is granted only when the absence is simultaneously declared in the retired-artifact registry — an undeclared disappearance still fails, so the gates cannot rot into blind spots; the branding test now also *enforces* the outreach retirement (a half-restored `outreach/` tree fails until consciously re-listed); relocated roadmap/feedback docs are followed to `archive/legacy_docs/`; the fit-grid test's dependency guard covers scipy as well as numpy. The July audit's "87 inherited failures" figure is superseded by these measured, fully-green states.

**M-task computed (same cycle): w₀wₐ response to the +0.417% shift.** The frontier doc's queued calculation was executed (`scripts/analysis_w0wa_rd_shift_diagnostic.py`, writeup `docs/analysis_w0wa_rd_shift.md`; controls pass exactly — the free-ruler control recovers the registered δ to 8 decimals). Three results, all recorded with equal weight: (1) the shift **cannot** explain the DESI dynamical-DE signal — under 1% of the χ² evidence; (2) it **does** bias standard-pipeline fits in the observed direction — the (w₀, wₐ) displacement is collinear with the DESI/Dovekie preference to ~8°, riding the CPL degeneracy valley (Adi's r_d degeneracy made concrete with GSC's specific number), plus a +0.42% H₀ bias; (3) the joint-fit H₀ degeneracy makes the shift nearly invisible to BAO+CMB fits, an honesty *refinement* of P1's testability: the registered externally-calibrated r_d comparison, not a joint fit, is the test with teeth, and metrology closure (megamasers, NGLR, BepiColombo) remains decisive.

## [v12.5 revival cycle] — July 2026

An honest resurrection, on the operator's instruction: not a reversal of any verdict by fiat, but a retreat to the parameter region that genuinely survives, a re-anchoring of the theory's one live derivation route, and the purchase of new kill-channels that make the framework *mortal* again rather than dead. Every input to the re-centering is already-public data; every change that improves a verdict is disclosed as such.

**Re-centering (the surviving corner, quantified).** A p-scan through the actual P1 pipeline against the registered DR1-era constraint gives a survival boundary of p = 7.63×10⁻⁴ (registered rule |z| < 3). The canonical exponent is re-centered from 10⁻³ to **p = 6×10⁻⁴**: retrodictive z = +2.36 (~21% margin), Ġ/G ≈ −8.4×10⁻¹⁴/yr (8.3× under the LLR bound). *[v12.6 annotation: that LLR bound was stale (2007-era) and misattributed; corrected current bounds exclude the locally observable G-running module at this p — see the v12.6 entry. The BAO leg of this re-centering, which is what actually constrains p, is unaffected.]* Deliberately near the boundary: p → 0 would make the framework observationally identical to ΛCDM, and a theory kept alive by shrinking its observables to zero is not alive. New single source of truth: `gsc/canonical_params.py` — closing the July audit's fragmentation finding (six copy-pasted `p = 0.001` literals).

**Scorer honesty fixes (both directions).** The P1/P3/P4 scorers had silently drifted to a 2.0σ pass threshold while every registered rule says |z| < 3 — implementation tightening the contract after the fact. Restored to the registered rule. Consequence disclosed plainly: P1's retrodictive check and P4 flip to PASS *because of the re-centering and the restored registered rule, not because of new data*. P4's PASS is explicitly unflattering — GSC predicts β ≈ 0.001° (a null) and is consistent with the Planck birefringence hint only because the hint itself is <3σ; **LiteBIRD confirming β at ≥3σ kills the σ-F̃F module**. Also fixed in the *generator* this time: the P1 scorecard template now emits the retrodictive banner and carries no unimplemented-correction rescue (the v12.3 pass had fixed the artifact; regeneration clobbered it — same lesson as the CI-count regression).

**New prediction P11 — distance-duality null (the framework's cleanest suicide switch).** Under universal coherent scaling, η(z) = D_L/[(1+z)²D_A] = 1 exactly, parameter-free, to all orders. Shared with ΛCDM (no discrimination there — stated plainly); its content is the pre-committed **sudden-death clause** (§12.2.1a): one robust DDR violation — ≥3σ, calibration-robust, model-independent, all three — falsifies T1 outright, no majority needed, no rescue permitted. Current bounds (verified): DESI DR2 BAO × Pantheon+ × chronometers give η₁ = 0.023 ± 0.027 (Zhang et al., arXiv:2506.17926) → GSC null at z = +0.85, PASS; parametrized 2–6σ violation claims in the literature are calibration-dependent and vanish in model-independent reconstructions (Keil et al., arXiv:2504.01750), hence the robustness qualifiers.

**Forward-target correction (found by fact-checking, against ourselves).** The registered P1 target "DESI Year-3 (2027)" was stale at registration: DESI DR2, which contains the Year-3 data, has been public since 2025-03 (aggregate isotropic BAO ~0.24%, arXiv:2503.14742; the canonical shift sits at ~1.7σ of that). The honest forward target is the **full five-year DESI release** (~0.2% forecast, arXiv:2402.14070). Honest mortality assessment, downgraded from earlier internal estimates: at the canonical p **no single near-term channel is decisive** — full-DESI BAO ~2σ, next-gen LLR ~1–2σ; decisive falsification comes from the combination plus P2's amplitude and P11's sudden-death clause. A wrong earlier citation from an internal exploration ("Pan & Mukherjee, arXiv:2412.04257") was caught by verification — that ID is Nguyen's varying-ħ/c dilaton paper, now cited correctly in P11 as a DDR-violating *alternative* GSC is distinguishable from.

**σ_\* re-anchored (§12.1).** The hadronic identification is retired as a derivation target: the Landau-pole form is anti-asymptotic-safety, the fixed point is sector-blind, and the σ-F̃F bridge is obstructed. G(σ) survives only as T2 phenomenology. The one live route is the FRG scaling-solution programme, whose intrinsic scale is the dark-energy (meV) density (Wetterich, arXiv:2407.03465) — a named specialist calculation, with the repo's flow-table ingestion tooling ready to receive it.

**Scoreboard post-v12.5:** 5 PASS (P1-retro, P4, P5, P9, P11 — with the honesty notes above), 2 FAIL (P3, P6) + the standing joint σ-axion exclusion, 1 SUB-THRESHOLD (P7), 3 PENDING (P2, P8, P10). The claim-verification layer enumerated every count/prose site this growth had to touch, and the CI prediction-count assertion now derives from the register — both guards built in earlier cycles did their job on a *growth* event.

## [v12.4 claim verification] — July 2026

Turns the project's one hard-won lesson into an instrument. The v12.3 false claim was caught by `grep SCAFFOLD` — one mechanical check, one line long, that nobody had bound to the prose. This release generalizes that binding.

**New: `scripts/verify_claims.py` + `CLAIMS.json`.** Each load-bearing claim is paired with a predicate over the repository's real state (front-matter field values, file/directory counts, SHA-256 recomputation, schema-name resolution, subprocess exit codes). It fails on **ASSERTED + UNBACKED**: the docs say it, the artifact does not do it. Ten claims covered. Runs in ~0.15 s over 134 markdown files, stdlib-only, zero inference.

This closes a real gap: the existing `docs_claims_lint.py` (28 KB) can only express "this phrase must not appear" and "this phrase must appear". It has no subprocess and no artifact introspection, so it cannot ask whether a sentence is *true* — a `REQUIRED_RULES` entry would happily have mandated the false signing claim.

**Validated by retro-detection.** Run against the pre-honesty-pass v12.2 tree (`a42d294`), the current manifest independently rediscovers four findings that each cost a human-led audit cycle: the signing overclaim (**18 assertion sites** vs 0/10 signed entries), the eight-vs-ten prediction drift, the private-repo citation pointer, and §9 documenting only P1–P8. Current tree: clean. Honest caveat: this is a *regression test, not a blind trial* — the manifest was written knowing those findings. One genuinely prospective catch (n=1): a reviewer talking-point in `joss/SUBMIT.md` still coaching the author to advertise "cryptographic signing", which the July hand-audit missed hours earlier; now corrected. Of four first-run failures, three were bugs in the tool, not the repository.

**New: `scripts/verify_claims_retro_test.sh` — a regression guard on the detector itself.** It requires a *failure* on the historical tree to pass, which blocks the obvious attack on any claim verifier: over-hedging until the inconvenient finding goes quiet. A negative control (adding the over-broad hedge `"signed"`) exposed a weakness in the guard's first version — detection collapsed 18 → 1 site while the binary "did it fire?" check still passed — so the guard now enforces a **sensitivity floor**, not mere liveness. Both controls verified.

**Also fixed (found by the new tool):** `README.md` still advertised a "four-paper publication strategy" with Paper E missing from its table entirely.

**New CI workflow** `v12_claim_verification.yml`: two jobs — claims-backed, and detector-sensitivity (needs `fetch-depth: 0`).

Design, predicates, and limitations: `docs/claim_verification.md`.

## [v12.3 execution audit] — July 2026

A fourth audit pass, execution-grounded where the previous three were reasoning-grounded: every executable claim in the package was run and checked against behavior.

**Verified (previously asserted, never executed as a check):**

- All 10 prediction pipelines regenerate `pipeline_output.json` **byte-identical to the committed register files** — a check CI itself does not perform (CI verifies run-to-run determinism but never diffs against the committed register). Also cross-version deterministic (Python 3.9 vs CI's 3.10).
- Scorecard-recorded SHA-256 hashes match the committed outputs for all 7 scored predictions; re-run scorers reproduce the recorded verdicts exactly; all 10 outputs validate against their JSON schemas.

**Found and fixed (claim drift):**

- The register grew 8 → 10 predictions in v12.1–v12.2 but prose in 14 places still said "eight" (framework doc ×2 + prediction list, README, INDEX, QUICKSTART, Paper D long-form ×3 incl. a "P1–P8" range, compute orchestrator docstring). **`GSC_Framework.md` §9 had no P9/P10 sections at all** — §9.9 and §9.10 added, faithful to the register entries.
- "Four-paper strategy" → five (Paper E added).
- Residual signing overclaims corrected: framework closing line, M201–M203 roadmap milestones (annotated with actual outcomes), INDEX "signing … operational" wording, and an editorial note on the v12.0 changelog entry ("signed-and-dated" was never true).
- Scoreboard presentation harmonized everywhere to: **2 PASS (P5, P9); 4 FAIL (P1, P3, P4, P6) + joint σ-axion window exclusion; 1 SUB-THRESHOLD (P7); 3 PENDING (P2, P8, P10)** (QUICKSTART was still quoting the v12.1 landscape).
- §12.2.1 framework-level kill condition gained an explicit **evaluability clause**: majority = ≥3 of 4 forward tests, firing incrementally (P8's ≥2040 data cannot delay a kill already triggered); passes never veto. Tightening only.

**Disclosed (known debt, not hidden):**

- The full inherited unittest suite is **not green**: 626 tests, 539 pass, 87 fail — every failure an inherited v11 doc-layout regression test asserting files that v12 relocated to `archive/legacy_docs/`. v12 CI never runs this suite, so the debt was invisible. The prediction/falsification stack is fully green. QUICKSTART now states this and points verification at `predictions_compute_all.sh --verify`.
- Package hygiene scan: no secrets, no private emails, no machine-local paths outside `archive/` (the only pattern hits are the project's own hygiene tests).

## [Current cycle, v12.3 honesty pass] — May 2026

### Triggered by a third hostile re-audit (post-publication)

After the v12.2 deposit (Zenodo, figshare, OSF), a third independent hostile re-audit turned scrutiny on the *methodology paper's own central claim* — not on the individual physics predictions, which the earlier cycles had already corrected. It found that the headline claim was overstated, and in one place internally self-contradictory. The scientific scoreboard below is **unchanged**; this sprint corrects how the methodology was *described*, which for a methodology paper is the substance.

**Findings:**

- **Pre-registration overclaim (CRITICAL).** The JOSS paper, `paper_D/main.md`, Paper A, and `docs/pre_registration.md` stated that predictions were "cryptographically signed and time-stamped before the corresponding observational data are released" and that this made moving the goalposts "structurally impossible." In fact **all ten register entries are `status: SCAFFOLD`** with empty signature fields; `predictions_sign.py` is an unexecuted reference scaffold. `docs/pre_registration.md` simultaneously claimed the register "is cryptographically signed" (line 3) and that the signing scripts were "scheduled for implementation in M201" (a milestone that never ran).
- **Retrodictive vs. forward conflation (CRITICAL).** Seven of the ten worked examples (P1, P3, P4, P5, P6, P7, P9) are scored against data that was already public when their pipelines were written; they are *retrodictive consistency checks*, not forward pre-registrations. Only P2, P8, P10, and the future DESI Year-3 BAO target are genuine forward pre-registrations.
- **P1 scored against the wrong data increment.** The registered P1 target is DESI **Year-3** (≈2027), but the worked `scorecard.md` scored against DESI **Year-1** (public 2024-04-04), using a relative-shift statistic and a confidence label ("2.0σ") inconsistent with the registered `|z| < 3` rule.
- **No framework-level falsifier (degenerating-programme risk).** Every failed prediction had been absorbed by tier-demotion or a "non-universal extension"; no observation was conceded to falsify the framework *core*. The only existing statement ("reduces to a re-parametrization of ΛCDM") was reduction, not falsification.
- **Physics demarcation (Paper A).** The redshift-drift sign and BAO-shift "deviations from ΛCDM" originate in the phenomenological H(z) = H₀(1+z)^p ansatz, **not** in the freeze-frame relabeling (which is conformally equivalent to ΛCDM and shares all dimensionless observables). Paper A had marketed them without this caveat.

**Corrections applied in v12.3:**

- Reworded the JOSS `paper.md` (the deposited artifact), `paper_D/main.md`, Paper A abstract, `docs/pre_registration.md`, and `paper_D/README.md` to drop "cryptographically-signed" / "signed-before-data" and state honestly: the register is **content-hashed and git-time-stamped**, GPG signing is **specified but not executed**, and the worked examples are **mostly retrodictive**.
- Added a **"Scope and honest limitations"** section to the JOSS paper, plus a paragraph recording that this v12.3 self-audit caught the overclaim (reported rather than quietly edited).
- Relabeled all ten `prediction.md` `status:` fields as RETRODICTIVE-check vs FORWARD-pre-registration (kept the `SCAFFOLD` prefix so the signing/scoreboard tooling still parses).
- Relabeled P1's `scorecard.md` as a retrodictive DESI Year-1 check, reconciled the `|z| < 3` threshold, and removed the "σ-modified recombination (M201) reverses the verdict" escape hatch.
- Fixed `P3 prediction.md` so the registered text matches its own corrected compute (Δτ_n = 0 / null under the canonical universal framework; non-zero only under the opt-in non-universal extension).
- Added a **pre-committed framework-level kill condition** (`GSC_Framework.md` §12.2.1): a conjunctive test over the *forward* predictions, with no post-hoc tier-demotion or extension permitted to rescue a registered prediction.
- Tempered the "a methodology paper can survive any physics outcome" language so it is not an unfalsifiability escape hatch.

This sprint is the methodology operating at its own expense: the discipline's most consequential value here was catching the overstatement of the discipline itself, before it could be cited.

---

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
- **Pre-registration register** introduced as primary methodological commitment. Eight (then ten) predictions (P1–P10) with associated scoring pipelines. *(Editorial note, v12.3: the original entry read "signed-and-dated"; signing was in fact never executed — entries are content-hashed and git-time-stamped only. See the v12.3 honesty pass.)*

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
