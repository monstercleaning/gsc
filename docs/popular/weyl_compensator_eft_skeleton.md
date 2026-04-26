# Weyl-Compensator EFT Skeleton (ToE-Track, Non-Submission)

**Disclaimer:** This note is exploratory ToE-track material. It is **not** part of the submission bundle, **not** part of canonical referee claims, and does not modify any the current framework late-time fit outputs.

## 1) Minimal Skeleton

One useful starting point is a Weyl-compensator scalar `chi` with an action-level structure that can be gauge-fixed into a frame where effective masses track one common scale:

- `M_Pl^2 ~ chi^2`
- matter-sector masses `m_i ~ chi`
- optional non-universal departures represented as small sector-dependent deviations.

Operationally, this is the ToE-track language for the v10 freeze-frame scaling variable `sigma(t)`.

## 2) Universality As Symmetry

In the baseline diagnostic contract, universality means:

- all sectors follow one coherent scaling law (effective `epsilon = 0` in risk notation),
- local dimensionless metrology remains locked (null-prediction logic),
- look-back observables carry the cosmological signal.

This reframes "universality" as a symmetry statement, not a slogan.

## 3) Small Symmetry-Breaking Knobs (Risk Model)

Two compact placeholders:

- `epsilon_EM`: effective EM-sector departure
- `epsilon_QCD`: effective hadronic/QCD-sector departure

Then clock/WEP/Oklo sensitivities depend on combinations such as `(epsilon_EM - epsilon_QCD)`. This remains a risk-parameterization framework, not a claim that these terms are nonzero.

## 4) Observable Hooks

If non-universal terms are activated in future modules, first-order pressure points are:

- WEP / Eotvos (`eta`) consistency,
- atomic clock ratio drifts (dimensionless),
- Oklo-style long-baseline dimensionless constraints,
- early-time closure consistency (CMB proxy and later full-Boltzmann pathway).

## 5) Module Contract (Template-Filled)

- Claim/motivation:
  - Provide a symmetry-grounded origin for universal scaling in v10 language.
- Assumptions:
  - Minimal compensator EFT is valid as a low-energy effective description.
- New parameters:
  - `epsilon_EM`, `epsilon_QCD` (default `0` in baseline).
- What it changes:
  - Interpretive layer and possible future couplings; no canonical pipeline effect today.
- Affected observables:
  - WEP, clocks, Oklo, CMB closure diagnostics, GW-to-EM consistency checks.
- Kill tests:
  - Any robust detection of incompatible dimensionless drifts at baseline would kill exact universality.
- Minimum code changes:
  - Keep isolated in diagnostic modules; no default-path changes.
- Status:
  - `candidate` / deferred; reopen only with explicit null-test budgets and bounded risk priors.

## 6) Scope Boundary

This note is intentionally separate from submission/referee canonical claims. Promotion path is:

1. convert into reproducible diagnostics with explicit tests,
2. satisfy null-test guardrails,
3. only then consider inclusion in referee-facing technical supplements.
