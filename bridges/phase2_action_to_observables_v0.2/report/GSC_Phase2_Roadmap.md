# GSC Phase 2 Roadmap — From “Late-Time Framework” to a Full ΛCDM Alternative

This roadmap assumes **v10.1** is *frozen* as “Paper I”: a coherent framework + a decisive falsifiable test (redshift drift) + a consistent local-scale invariance argument.

Phase 2 is the minimum set of steps required to become a **complete cosmological model** (i.e., to confront the same pillars that make ΛCDM empirically successful).

---

## 0) Guiding principle (avoid a “Frankenstein”)
**Rule:** A module is promoted to “Core GSC” only after it passes its own acceptance tests.

Until then:
- keep it as a *separate* section/paper (“GSC-II”, “GSC-III”…),
- keep the parameter count explicit,
- keep the falsification criteria explicit.

---

## 1) The Action → Observable bridge (non‑negotiable)
### Goal
Derive a **unique** predicted collapse law σ(t) (or equivalent), and therefore a unique **H(z)** and **dz/dt(z)**, from the RG-running gravity hypothesis.

### Required outputs
- A clearly stated effective action (Jordan or Einstein frame):
  - field content (metric + scale field σ / φ + matter)
  - coupling functions F(φ), A(φ), V(φ), K(φ) (or their equivalents)
- A physically motivated **RG scale identification** k = k(σ, H, ρ, …)
- A dynamical equation (ODE) for σ(t) (or φ(t))
- A numerical solver with reproducible plots:
  - σ(t), z(t), H(z), w_eff(z), dz/dt(z)

### Acceptance criteria
- No “hand-picked” p=0.5 (or similar) in the *main* predictions.
- Parameter count ≤ 2 “new” parameters beyond standard cosmology (initially).
- Clear statement of what sets σ_* (free parameter vs derived).

### Suggested scripts
- `phase2_rg_sigma_solver.py` — integrates σ(t) from the RG-improved equations
- `phase2_rg_to_drift.py` — produces dz/dt and Δv(10yr) curves from the solver

---

## 2) Distance ladder & BAO confrontation (late-time geometry)
### Goal
Show that the Phase-2 predicted H(z) reproduces:
- SN Ia distance modulus curve
- BAO distance measures (D_M/r_d, D_H/r_d) *or* an internally consistent alternative mapping, if the frame changes the interpretation

### Acceptance criteria
- A full likelihood run (even a simple χ²) against:
  - SN Ia (Pantheon+ or equivalent)
  - BAO compilation
- Parameter posteriors + residual plots

### Suggested scripts
- `phase2_fit_sn_bao.py`
- `data/` folder containing the exact datasets used + citations in README

---

## 3) Linear perturbations: growth, lensing, and the matter power spectrum
### Goal
Provide a consistent perturbation sector:
- growth factor D(a)
- fσ8(z)
- weak lensing potential

### Practical implementation path
- Map to a scalar–tensor / varying-Planck-mass form and implement in an existing Boltzmann code:
  - CLASS / hi_class / EFTCAMB (choose one)
- Start with minimal modifications: background + scalar perturbations + effective G_eff(k,a)

### Acceptance criteria
- Fit does not catastrophically fail on:
  - fσ8 compilation
  - lensing amplitude constraints (qualitatively at first)

---

## 4) Early Universe pillar: CMB acoustic peaks
### Goal
Demonstrate that the model reproduces:
- peak positions (θ_*), relative peak heights (baryon loading), and damping tail (at least qualitatively)

### Notes
This is the hardest step. If the model is truly static in the physical frame, you must show how the *effective* photon–baryon sound horizon and recombination mapping emerges.

### Acceptance criteria
- At minimum: reproduce the observed angular acoustic scale θ_* within a few percent using a consistent sound-horizon computation.
- Ideally: full CMB TT spectrum fit via Boltzmann code.

---

## 5) Precision “consistency” constraints (turn attacks into checks)
Create a single module: `phase2_constraints/` that collects:
- Oklo (dimensionless resonance conditions)
- pulsar timing constraints on Ġ/G (properly interpreted in the chosen frame)
- BBN consistency (already mostly addressed, but formalize)
- lab/clock bounds on α, μ variations (again: in the chosen frame)

Each constraint must include:
- what observable is actually measured (dimensionless)
- how it transforms under GSC scaling
- the derived bound on the model parameters

---

## 6) Deliverables of Phase 2
Minimum “Phase 2 complete” package:
- `GSC-II_Action_to_Observables.md` (short paper / appendix)
- `phase2/` code directory with reproducible scripts
- one `phase2_report.md` that:
  - summarizes fits
  - lists failures transparently
  - states next falsification tests

---

## 7) Hard stop conditions (to keep the project honest)
If any of the following is true, the “full alternative” track should stop or pivot back to “late-time framework only”:

1) No RG-motivated σ(t) can be found that keeps dz/dt positive **and** fits SN+BAO distances within reasonable tolerance.
2) The perturbation sector requires >~5 additional free functions/parameters to avoid obvious conflicts.
3) CMB acoustic scale cannot be reproduced without introducing a separate “early-time expansion” patch that breaks the conceptual unity.

