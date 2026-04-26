---
title: "GSC Phase 3 — CMB/BAO/Growth Compressed Diagnostics"
subtitle: "From Action Parameters to Early/Late Observables (v0.2)"
author: "GSC working draft"
date: "January 2026"
version: "v0.2"
---

## 0. Scope and intent

This document is **Phase 3** of the GSC roadmap: *turn the Phase‑2 “Action → background” prototype into testable, dataset-facing diagnostics*.

**Important scope note:** these are **compressed checks** (distance priors / BAO consensus / growth ODE). This is **not** a full Boltzmann treatment (no full $C_\ell$, no lensing likelihood, no MCMC). The goal is to (1) find obvious contradictions quickly, and (2) identify what Phase 4 must implement.

---

## 1. Link to Phase 2: removing “magic numbers”

Phase‑2 introduced an exponential scalar potential prototype where the late-time scaling exponent is **derived** (not guessed). For the attractor solution of a scalar field with $V(\phi)\propto e^{-\lambda \phi}$ one obtains (in the simplest scalar-dominated scaling regime) an effective power-law for the background that can be parameterized as

\[
p \equiv \frac{\lambda^2}{2}.
\]

In this Phase‑3 package we therefore scan $\lambda$ and always convert to $p=\lambda^2/2$ (so the phenomenology is explicitly tied to the Action).

---

## 2. Background model used here (phenomenological matching)

We use a **piecewise** background history:

- For **late redshift** $z \le z_{\rm tr}$ we use the Phase‑2 law
  \[
  H(z)=H_0(1+z)^p,
  \quad p=\lambda^2/2.
  \]
- For **early redshift** $z > z_{\rm tr}$ we use the standard matter+radiation scaling
  \[
  H(z)=H_0\sqrt{\Omega_r(1+z)^4+\Omega_m(1+z)^3}.
  \]

In v0.2 we set **$z_{\rm tr}=5$** as a working choice, because:
- v10.1 is explicitly *late-time focused* ($0\lesssim z \lesssim 5$),
- the redshift-drift discriminant lives in this regime,
- and it avoids injecting an uncontrolled model into the pre-recombination era.

**Phase 4 requirement:** derive $z_{\rm tr}$ (and the full interpolation) from the RG/action dynamics instead of imposing it.

---

## 3. CMB acoustic scale diagnostic (θ\*)

We compute the angular sound horizon:

\[
\theta_*=\frac{r_s(z_*)}{D_M(z_*)},
\qquad
\ell_A \equiv \frac{\pi}{\theta_*}.
\]

Implementation notes:
- $z_*$ uses the standard Hu–Sugiyama fitting form.
- $r_s(z)$ is computed numerically from the sound speed $c_s(z)$ and the early-time $H(z)$.
- $D_M(z)$ is computed by numerical integration of $c/H(z)$ along the line of sight using the **piecewise** $H(z)$.

Outputs:
- `outputs/figures/theta_star_vs_lambda.png`
- `outputs/figures/zstar_required_shift.png`
- `outputs/results/theta_star_action_summary.txt`

### Interpretation

This diagnostic answers a narrow question:

> **If** we naïvely treat the late-time GSC collapse law as an effective FLRW $H(z)$ for $z<z_{\rm tr}$, **how much does $\theta_*$ move?**

If the shift is large, it means **we cannot claim CMB compatibility without a full freeze‑frame mapping** of early-time microphysics and observables. This is not surprising: v10.1 explicitly defers CMB to future work.

---

## 4. BAO + Full-Shape (RSD) compressed test (BOSS DR12)

We implement the **BOSS DR12 consensus** constraints (BAO+FS), including the published covariance.

BOSS provides constraints in scaled form:

- $D_M(z)\,(r_{d,\rm fid}/r_d)$
- $H(z)\,(r_d/r_{d,\rm fid})$
- $f\sigma_8(z)$

We compute:
- $r_d$ using the Eisenstein–Hu fitting $z_d$ and a numerical sound-horizon integral.
- $D_M(z)$ and $H(z)$ from the piecewise $H(z)$.
- $f\sigma_8(z)$ using the standard GR growth ODE (diagnostic only).

We **analytically marginalize $\sigma_{8,0}$**, since the model predicts $f\sigma_8(z)=\sigma_{8,0}\,f(z)\,D(z)$.

Outputs:
- `outputs/figures/chi2_vs_lambda.png`
- `outputs/results/bao_fs_summary.txt`

### Interpretation

This is a meaningful *late-time* stress test because:
- BAO/RSD live in the same $z$ range as the v10.1 redshift-drift discriminant.
- It is much cheaper than a full CMB likelihood.

It is still **not a full cosmology fit** (no SNe, no lensing, no $P(k)$ transfer function).

---

## 5. Growth curves (diagnostic only)

We provide growth curves for a few representative $\lambda$:

- `outputs/figures/growth_Dz_vs_z.png`
- `outputs/figures/growth_f_vs_z.png`

These plots are for intuition only. In Phase 4, GSC should derive the correct perturbation source term (effective $\mu(a,k)$ / slip / scalar perturbations), not assume GR growth on a modified background.

---

## 6. How to reproduce

From the package root:

```bash
python scripts/run_all.py
```

---

## 7. What Phase 4 must do (to become ΛCDM-comparable)

1. **Freeze-frame recombination / CMB mapping**
   - derive how $z_*$ and $r_s$ map under universal mass scaling,
   - compute full $C_\ell$ spectra with a Boltzmann solver (CLASS/CAMB fork).

2. **Perturbations in the GSC scalar/RG sector**
   - derive linear perturbation equations from the Action (not GR-by-hand),
   - compute transfer functions and $P(k)$.

3. **Likelihood-level comparisons**
   - Planck (or CMB-lite priors), BAO+FS, SNe, lensing,
   - run MCMC / nested sampling to map degeneracies.

Phase 3 v0.2 is a stepping stone: it does not claim to solve these items, but it concretely shows what breaks (or not) under a naïve mapping.
