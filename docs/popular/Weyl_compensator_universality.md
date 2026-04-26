# DISCLAIMER (ToE-track note; not part of submission / referee pack)

This document is **not peer-reviewed** and is **not part of the submission package** or the
canonical referee pack. It is a **ToE-track / conceptual note** intended to give structural
context for the “universality” principle used in the late-time measurement model.

Nothing here should be read as a new empirical claim or as a replacement for the paper’s scope.

---

# Universality as a Weyl-Compensator (Dilaton) Structure (Conceptual Note)

## 1) Motivation: make “universality” a symmetry statement, not a slogan

In the current framework (late-time scope), “universal/coherent scaling” is treated as a required symmetry of the
measurement model. Operationally: local metrology is *blind* to a purely universal rescaling, so
dimensionless local comparisons are null tests.

A natural structural way to frame this is via **local scale (Weyl) invariance** implemented with a
**compensator field** (often called a dilaton), which we denote here by `chi` (conceptually related to
the paper’s `sigma` bookkeeping scale).

This note is only about *structure*: it does not attempt a UV-complete model.

## 2) Weyl / local scale invariance in one paragraph

Under a local Weyl transformation:

- `g_{mu nu}(x) -> Omega(x)^2 g_{mu nu}(x)`
- a compensator `chi(x) -> Omega(x)^{-1} chi(x)`

If the action is built from Weyl-invariant combinations, then **dimensionful quantities can be made
to scale with `chi`**, while **dimensionless observables are unchanged**.

In a “universal” limit, one can think schematically of:

- particle masses: `m_i(x) ∝ chi(x)`
- an effective Planck mass: `M_Pl(x) ∝ chi(x)`

so that local rulers/clocks co-scale and operational comparisons remain invariant (the “geometric lock”).

## 3) How non-universality maps to the epsilon risk parameters

In the project’s reviewer-facing risk model, we parameterize departures from strict universality by
small “epsilon” knobs (examples used in the paper/docs):

- electromagnetic sector mismatch: `epsilon_EM`
- hadronic/QCD sector mismatch: `epsilon_QCD`

Conceptually, in a Weyl/dilaton framing, such epsilons can be interpreted as:

- sector-dependent anomalous dimensions,
- anomaly-induced running,
- or explicit symmetry-breaking operators that couple differently to `chi`.

That is: **non-universal epsilons are not innocuous**. They immediately imply measurable drifts in
dimensionless ratios and/or composition dependence (WEP violation), which is why they are treated as
kill-mode risks and are set to zero in the the current framework baseline.

## 4) How this ties to existing project artifacts

This note is intentionally *non-canonical*. The canonical, submission-relevant statements live in:

- `docs/measurement_model.md` (measurement model axioms and null predictions)
- `docs/precision_constraints_translator.md` (how WEP/clocks/Oklo map onto epsilon risks)
- lock tests in `tests/` that enforce the universal-scaling invariants

## 5) Starter pointers (not exhaustive)

- Weyl / conformal geometry overview as a gauge framework:
  - [Quantum gravity from Weyl conformal geometry (EPJC, 2025)](https://link.springer.com/article/10.1140/epjc/s10052-025-14489-z)
- Weyl-integrable / scalar-tensor traditions (general entry points):
  - “Weyl integrable geometry” reviews in gravitational theory (various authors; use as terminology anchors).
  - Classical Weyl geometry origins (H. Weyl, 1918) and later scalar-tensor/dilaton formulations.

