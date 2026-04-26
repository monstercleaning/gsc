# RG Scale Identification in the current framework (Clarifying Note)

## What `k` means in FRG / Asymptotic Safety

In functional RG / asymptotic-safety language, running couplings are defined with
respect to a momentum-like renormalization scale `k`. Statements about `G(k)` are,
at that level, statements about scale dependence in the RG flow, not automatically
about cosmic time evolution.

## What GSC assumes in the current framework

In the current framework we use

`G(k) = G_IR / (1 - (k/k_*)^2)`

as a phenomenological parametrization of a rapid crossover/enhancement. This is not
a first-principles FRG derivation in the current release.

The mapping from RG scale to the bound-matter evolution variable is treated as a
working identification (ansatz): a characteristic bound-system scale tracks `sigma`,
and we use a relation of the form `k = k(sigma)` (often motivated as `k ∝ 1/sigma`
up to model-dependent factors). This identification is not derived from FRG in
v11.0.0 and remains an open problem.

## What is NOT claimed

- We do not claim a controlled FRG derivation of `k(sigma)` in this release.
- We do not claim a first-principles derivation of `k_*` from asymptotic safety.
- We do not claim UV completeness of the present phenomenological harness.
- We do not claim that asymptotic safety by itself validates GSC.

## What is falsifiable at this stage

Phase-2 falsification remains framed through explicit background histories `H(z)` and
their observational consequences (for example redshift-drift sign behavior and CMB
compressed-priors closure diagnostics). The frame map itself is not the empirical
discriminator.

## Roadmap / Open Problem

Needed beyond v11.0.0:

- A controlled argument (or derivation) for the `k(sigma)` identification.
- Clear links between FRG truncation choices and effective late-time history classes.
- Additional consistency checks connecting early-time closure diagnostics to the
  same scale-identification ansatz.
