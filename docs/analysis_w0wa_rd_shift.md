# Diagnostic: what does GSC's +0.417% ruler shift do to a w₀wₐ fit?

**Status: DIAGNOSTIC — not a registered prediction.** Direction and order of
magnitude only. Script: `scripts/analysis_w0wa_rd_shift_diagnostic.py`;
deterministic artifact: `data/analysis/w0wa_rd_shift_diagnostic.json`.
Executed 2026-07-27 (v12.6 cycle), closing the M-task queued in
`docs/observational_frontier_2026.md` §5.

## Question

Adi (JCAP 03 (2026) 015, arXiv:2509.12331) showed that the DESI w₀wₐ
"evolving dark energy" evidence is partially degenerate with the assumed
drag-epoch sound horizon: *"lowering r_d systematically drives the w0-wa
posterior toward less dynamical, quintessence-like behavior, bringing it
closer to ΛCDM"* (verbatim, abstract). GSC's canonical T2 ansatz predicts the
*apparent* BAO ruler in today's units is **+0.417% larger** than the ΛCDM
expectation (P1, `delta_rs_relative = 0.004166198`, read from the register
artifact at runtime). This diagnostic asks: if the universe were GSC and an
analyst fit w₀wₐCDM with the standard (unshifted) r_d calibration, where
would (w₀, wₐ) land — toward the DESI preference (w₀ > −1, wₐ < 0) or away
from it, and how strongly?

## Setup (minimal by design)

- Mock "GSC truth": noiseless flat-ΛCDM background at the P1 fiducial
  (h = 0.6736, ω_m = 0.1430), with the measured BAO ratios D/r_d lowered by
  the factor 1/(1+δ) — the apparent-ruler effect and nothing else. The CMB
  acoustic angle is dimensionless and invariant under the coherent
  relabeling, so the CMB-side anchors equal the fiducial exactly (the
  registered P1 convention).
- Data model: the five DESI DR1 tracers with their real per-tracer
  uncertainties and D_M–D_H correlations (`data/bao/desi/`), central values
  replaced by the mock; Planck-like Gaussian anchors ω_m = 0.1430 ± 0.0011
  and D_M(z★)/r_d at 0.031%.
- Fits: flat ΛCDM and flat w₀wₐCDM (CPL), radiation included, r_d fixed to
  the standard calibration. Deterministic Nelder–Mead plus a 441-point
  (w₀, wₐ) grid profiled over (ω_m, h).

## Controls (both pass)

| Control | Expectation | Result |
|---|---|---|
| C0: unshifted mock, ΛCDM fit | recover fiducial, χ² ≈ 0 | exact: χ² = 0.0 at (0.1430, 0.6736) |
| D: shifted mock, ΛCDM + free BAO-ruler scale | absorb exactly: scale → 1+δ | scale = 1.00416615 (δ_registered = 1.004166198), χ² = 1.2×10⁻¹⁰ |

Control D confirms the mock is a *pure calibration effect*: one BAO-side
recalibration parameter removes it to numerical precision.

## Results on the shifted mock (standard r_d throughout)

**1. The shift hides almost entirely in H₀.** The ΛCDM fit absorbs the
+0.417% ruler shift as a **+0.419% bias in h** (0.6736 → 0.6764, ≈ +0.28
km/s/Mpc), leaving residual χ² = 0.21 at DR1 precision (0.55 with BAO errors
halved to DR2-like scale). Mechanism: the compressed-CMB anchor pins ω_m,
not h, so the low-z distance rescaling c/(H₀ r_d) soaks up the calibration
offset. Two consequences stated plainly:

- *For the H₀ tension:* the bias is toward SH0ES but is ~4% of the ~7 km/s/Mpc
  discrepancy — negligible; GSC does not address the H₀ tension.
- *For P1's testability:* in a **joint** BAO+CMB fit the shift is nearly
  invisible (it masquerades as H₀); the registered P1 comparison — r_d against
  an externally calibrated value — is the configuration with actual teeth.
  This sharpens, with numbers, why the decisive test requires external
  metrology closure (megamasers, NGLR-class ranging; frontier doc §3.3), and
  it is *less* favorable to near-term BAO-only falsification than the naive
  shift/σ estimate suggests. Recorded as an honesty refinement, not a rescue.

**2. The w₀wₐ residual pull is in the DESI direction.** Letting (w₀, wₐ)
float picks up the small residual: best fit **(w₀, wₐ) = (−0.948, −0.161)**
(Nelder–Mead), landscape minimum (−0.94, −0.20) — the two agree, so the
minimum is real, not optimizer noise. The displacement from ΛCDM,
(Δw₀, Δwₐ) = (+0.05, −0.16), is **collinear with the DESI/Dovekie preference
direction to within ~8°** (Dovekie best fit (w₀, wₐ) = (−0.803 ± 0.054,
−0.72 ± 0.21), arXiv:2511.07517; displacement (+0.197, −0.72); angle from
cos θ = u·v/|u||v| = 0.9987). Of landscape gridpoints improving on the
near-ΛCDM reference, 5 of 6 lie in the (w₀ > −1, wₐ < 0) quadrant. The
valley follows the standard CPL degeneracy (wₐ* ≈ −2.5(w₀+1)), and the pull
sits on its quintessence-like side.

**3. But the magnitude is tiny.** The w₀wₐ improvement is Δχ² = 0.044 at DR1
precision (0.036 at DR2-like BAO errors) — against Δχ² ≈ 12 for DESI DR2's
reported 3.1σ (two-parameter) preference. In χ² terms the GSC shift supplies
**under 1% of the observed evidence**. (The displacement *amplitude* is a
larger fraction of Dovekie's — |u|/|v| ≈ 0.23 — precisely because the
displacement rides the weakly constrained valley direction; that geometry is
Adi's degeneracy made concrete, and it is why the two numbers differ by a
factor of ~50. The χ² number is the honest measure of evidence.)

## Conclusions (all three stated with equal weight)

1. **GSC's metrology shift cannot explain the DESI dynamical-dark-energy
   signal.** Sub-1% of the χ² evidence at either DR1 or DR2-scaled precision.
   Anyone hoping the +0.417% shift "is" the DESI anomaly should stop hoping;
   this computation closes that speculation with a number.
2. **It does, however, bias standard-pipeline fits in the observed
   direction** — a small, systematic, same-direction (within ~8°) push into
   the quintessence-like quadrant, plus a +0.4% H₀ bias. If the universe is
   GSC, w₀wₐ analyses of BAO+CMB read slightly "DESI-like" for calibration
   reasons alone.
3. **The joint-fit degeneracy weakens near-term BAO-only tests of P1** (the
   shift hides in H₀). The registered forward test remains the full-survey
   externally-calibrated r_d comparison, and the metrology-closure
   instruments of frontier doc §3.3 remain the decisive ones.

## Limitations

No SNe; compressed CMB anchors only; DR1 per-tracer errors without
cross-tracer covariance; exact-ΛCDM mock background (the T2 background
deviation at p = 6×10⁻⁴ is second-order for this purpose); θ★ treated as
exactly invariant (P1 convention); quadrature and r_d constants shared
between mock and fit, so only differential statements are valid. None of
these plausibly flip the direction result; all of them caution against
quoting the magnitude beyond order-of-magnitude.
