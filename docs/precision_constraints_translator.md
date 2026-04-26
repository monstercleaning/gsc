# Precision Constraints Translator (/Option 2)

This document translates common precision constraints (WEP, clocks, Oklo, LLR/˙G) into the
**measurement-model language** of the current framework under **universal/coherent scaling**.

It is **project-canonical** (referee-grade), but it is **not part of the paper PDF** and is **not included**
in the submission bundle tooling.

---

## 1) Executive Summary (one page)

### Universal / coherent scaling (v11.0.0 axiom)

Option 2 introduces a universal matter scale `σ(t)` governing bound systems:

- bound lengths: `ℓ_bound(t) ∝ σ(t)`
- particle masses: `m_i(t) ∝ σ(t)^(-1)`
- dimensionless couplings/ratios (α, Yukawas, mass ratios, ...) are invariant to high precision.

This is not a “nice-to-have”. It is the **required symmetry** that produces a **local null prediction**:
purely local dimensionless comparisons should not show secular drift beyond SM/GR.

### “Only dimensionless observables” (what experiments actually measure)

Precision constraints are ultimately statements about dimensionless quantities:
an apparatus compares “the phenomenon” to “the standard” (clock, ruler, reference transition, ephemeris),
and reports a dimensionless residual.

If both the phenomenon and the local standard co-scale universally with `σ(t)`, the residual is **unchanged**
even if individual dimensionful quantities (masses, energies, `G_IR`, …) evolve in a bookkeeping frame.

### Local metrology blindness / geometric lock (the key idea)

In the ideal universal limit, any drift in a **dimensionful** quantity can be absorbed into the shared
rescaling of the local standards. What remains observable is only **non-universal** drift in dimensionless
ratios (composition dependence, differential clock drift, etc.).

In practice:
- “naive” constraints phrased as `\dot G/G` are often model-dependent because the mapping from data to a
time-varying `G` assumes a specific metrology/clock model.
- constraints on dimensionless ratios (clock comparisons, WEP/Eötvös parameters, etc.) are the
direct kill-tests of universality.

Canonical measurement-model pointer: `docs/measurement_model.md`.

---

## 2) Translator Table: Experiment → What Is Constrained → Why Null (Ideal Universal Limit) → Failure Mode

| Experiment / class | What they actually constrain | Why it is null in v10 (ideal universal limit) | Failure mode (what would kill v10 universality) |
|---|---|---|---|
| MICROSCOPE / Eötvös torsion-balance tests | **Composition dependence** of free-fall, often summarized by the Eötvös parameter `η` | Universal scaling implies all sectors co-scale; there is no composition-dependent differential acceleration sourced by `σ(t)` itself. | Sector-dependent scaling (different `σ_i(t)`), composition-dependent couplings, or any mechanism that induces non-universal clock/ruler behavior across materials. |
| Atomic clock comparisons (optical vs Cs/Rb, etc.) | Drift in **dimensionless frequency ratios** `ν_a/ν_b` | If all atomic transition frequencies share the same universal scaling (dimensionless inputs fixed), then `ν_a/ν_b` is constant. | Real drift in `α`, mass ratios, or any non-universal scaling that differentiates transitions (e.g. electromagnetic vs nuclear scaling mismatch). |
| Oklo (natural reactor) | Bounds on changes in **dimensionless combinations** controlling nuclear resonance positions/widths relative to nuclear scales | In the strict universal limit, ratios of nuclear scales and couplings remain fixed, so Oklo-type dimensionless resonance conditions are preserved. | Non-universal corrections: QCD vs EW vs EM mismatch, sector-dependent scaling, or drift in dimensionless couplings that shifts resonance conditions relative to nuclear scales. |
| LLR / pulsar timing (often quoted as `\dot G/G`) | Constraints on orbital dynamics residuals mapped (under assumptions) to a time variation of an effective gravitational coupling | In a universal scaling picture, the mapping “residual → `\dot G/G`” can be frame/metrology dependent; what is directly constrained are dimensionless orbital/clock residuals. Universal co-scaling can produce an apparent `\dot G/G` in bookkeeping variables while leaving operational residuals null. | Any verified secular drift in **dimensionless** ratios that cannot be removed by a consistent universal rescaling (e.g. differential scaling between atomic time standards and gravitational dynamics). |

---

## 3) “What v10 must satisfy” (checklist)

**Universality is a hard requirement.** If it fails, the v10 Option-2 program fails.

Checklist for future work (v10+):

- Universal scaling must remain a declared symmetry of the measurement model:
  - local dimensionless ratios are invariant to precision bounds.
- If any non-universal correction is introduced (even as a toy extension), it must:
  - specify which sector deviates (EM vs QCD vs leptonic, composition dependence, etc.),
  - be confronted against: WEP/MICROSCOPE, clock-comparison drifts, Oklo, LLR/pulsars.
- Code guardrails must lock the null prediction logic:
  - “geometric lock” invariance tests live in `tests/test_measurement_model_null_predictions.py`.

---

## 4) Worked examples (order-of-magnitude; illustrative)

These are simple “back-of-the-envelope” translations from a universal-scaling *risk parameterization*
to a measurable drift/bound. They are **not** additional claims.

Define (as in the paper risk model; Sec. 5.6):

- `ε_EM, ε_QCD` via `m_e ∝ σ^(-1-ε_EM)` and `m_p` (or a hadronic scale) `∝ σ^(-1-ε_QCD)`.
  - Then for `μ ≡ m_p/m_e`: `d ln μ / dt = (ε_EM - ε_QCD) H_σ`.
- Derived: `ε_μ ≡ d ln μ / d ln σ = ε_EM - ε_QCD`, so `d ln μ / dt = ε_μ H_σ`.
- Optionally, to parameterize a direct drift of `α`: `ε_α ≡ d ln α / d ln σ`, so `d ln α / dt = ε_α H_σ`.

In the current framework we take strict universality: `ε_EM = ε_QCD = 0` (and operationally `ε_α=0`). The point of
the examples below is to show how small non-universal corrections would be constrained if they were
ever introduced in v10+.

### Example 1: Optical clock ratio → order bound on `ε_α`

Generic clock comparisons constrain drift of **dimensionless** frequency ratios:

`d/dt ln(ν_A/ν_B) = (K_α^{AB} ε_α + K_μ^{AB} ε_μ + …) H_σ`.

Take a representative sensitivity `K_α^{AB} ~ O(1–3)` and assume (for illustration) `ε_μ=0`.
At the present epoch `H_σ(t0)=H0 ≈ 7×10^-11 yr^-1`, so if `ε_α = 10^-7` then

- `|d/dt ln(ν_A/ν_B)| ~ K_α ε_α H0 ~ O(10^-17 yr^-1)` (before any additional factors).

Clock networks that bound `|d/dt ln(ν_A/ν_B)|` at the `~10^-17 yr^-1` level therefore imply an
order-of-magnitude constraint `|ε_α| ≲ 10^-7`, modulo the actual `K_α` values and the particular
clock pair used.

Reference point: optical-clock comparisons constrain `\dot α/α` at the `~10^-17 yr^-1` level
(e.g. Rosenband et al., *Science* 319, 1808 (2008)).

### Example 2: WEP / MICROSCOPE → order bound on `(ε_EM - ε_QCD)`

WEP tests constrain **composition-dependent** differential acceleration, summarized by the Eötvös
parameter `η_AB`. MICROSCOPE reports null results at the `|η| ~ 10^-15` level for composition pairs
such as Ti vs Pt (Touboul et al., *Class. Quantum Grav.* 39, 204009 (2022)).

In a non-universal extension, different materials would generally acquire different effective
dimensionless “charges” under the scaling field, leading to `η_AB ≠ 0`. A schematic translation
template is:

- write `η_AB ~ g_nu × ΔC_AB`, where `ΔC_AB` captures how differently A and B depend on the non-universal
  sector (typically `ΔC_AB ~ 10^-2–10^-1` in order-of-magnitude terms), and `g_nu` is the effective
  non-universal coupling strength.
- if we identify `g_nu` with `(ε_EM - ε_QCD)` (risk-module knob), then MICROSCOPE implies
  `|ε_EM - ε_QCD| ≲ 10^-13–10^-14` (order-of-magnitude).

This translation is intentionally conservative and schematic: the precise mapping from a particular
non-universal scaling model to `η_AB` depends on composition coefficients and on whether the scalar
mediator is screened. The point is that **any** departure from universality must be confronted against
WEP bounds, and the required couplings are generically tiny.

### Example 3: Oklo long-baseline → order bound on `ε_α` (optional template)

Oklo-type bounds are often phrased as limits on a long-baseline change `Δα/α` over `~Gyr` times.
In the same `ε_α` risk parameterization:

- `Δ ln α ≈ ε_α Δ ln σ`.

If we take a conservative late-time lookback `Δ ln σ ~ O(0.1)` for `z ~ 0.1–0.2` and an
illustrative Oklo-scale bound `|Δα/α| ≲ 10^-7`, then

- `|ε_α| ~ |Δ ln α| / |Δ ln σ| ≲ 10^-6` (order-of-magnitude).

This is meant only as a translation template: the precise bound depends on the detailed Oklo analysis
and on the correct mapping of the lookback interval into `Δ ln σ` for the late-time history used
(see e.g. Damour & Dyson (1996), Davis & Hamdan (2015)).

---

## References (minimal pointer list)

- P. Touboul et al., “MICROSCOPE Mission: Final Results of the Test of the Equivalence Principle,” *Class. Quantum Grav.* 39, 204009 (2022).
- T. Rosenband et al., “Frequency Ratio of Al\(^+\) and Hg\(^+\) Single-Ion Optical Clocks; Metrology at the 17th Decimal Place,” *Science* 319, 1808 (2008).
- T. Damour and F. Dyson, “The Oklo bound on the time variation of the fine-structure constant revisited,” (1996).
- A. C. Davis and A. G. Hamdan, “Oklo constraints on variations of the fine-structure constant,” *Phys. Rev. C* 92, 045501 (2015).
