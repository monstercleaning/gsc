# Weyl-Integrable Geometry Mapping (ToE-Track Note)

**DISCLAIMER (read first):** This note is **not peer-reviewed**, **not part of the the current framework submission package**, and **not included in the referee pack by default**. It is a ToE-track / conceptual mapping note intended to clarify how "universality" can arise from symmetry/geometry rather than being a slogan.

## 1) Why This Note Exists

In the current framework we treat **universal scaling** as a required structural property of the measurement model and as a hard consistency contract (dimensionless local metrology is a null test in the universal limit). Reviewers often ask:

- "Why should universality be exact?"
- "What structure in an action/geometry would enforce it?"

This note sketches one standard language for that: **Weyl (local scale) geometry**, in the **integrable** subclass where the Weyl 1-form is a gradient and the theory maps cleanly to scalar-tensor (frame-equivalent) descriptions.

## 2) Integrable Weyl Geometry in One Page (Geometry Only)

In Weyl geometry one relaxes metric compatibility and allows a non-metricity of the form

\[
\nabla_\lambda g_{\mu\nu} = -2 W_\lambda g_{\mu\nu},
\]

where \(W_\mu\) is a Weyl 1-form (a "scale connection"). Under a Weyl (local scale) transformation,

\[
g_{\mu\nu} \to \Omega^2(x)\, g_{\mu\nu},
\qquad
W_\mu \to W_\mu - \partial_\mu \ln \Omega.
\]

In the **integrable** case, \(W_\mu\) is pure gauge:

\[
W_\mu = \partial_\mu \varphi,
\]

so the geometry is "Weyl-integrable" (no scale curvature). This is precisely the setting where one can interpret a scalar field (or compensator) as the carrier of local scale structure while remaining close to familiar scalar-tensor forms.

## 3) Mapping to Scalar-Tensor / Brans--Dicke (Frame-Equivalent View)

Weyl-integrable scalar-tensor formulations are commonly shown to be equivalent (modulo field redefinitions / frame transformations) to Brans--Dicke-like theories with a geometrical interpretation.

One explicit reference point:

- Almeida et al., *Phys. Rev. D* **89**, 064047 (2014), "From Brans-Dicke gravity to a geometrical scalar-tensor theory" (APS link):  
  https://link.aps.org/doi/10.1103/PhysRevD.89.064047

At the level of this note, the key takeaway is not the details of any one action, but the general structural idea:

- Local scale symmetry can be implemented as a gauge-like redundancy (Weyl rescaling).
- A scalar (compensator/dilaton-like) degree of freedom can restore Weyl invariance.
- Frame changes then look like gauge choices / field redefinitions, consistent with the "conformal-frame map / heritage" disclaimers already made in the main paper.

## 4) Universality as Symmetry; Epsilon Parameters as Symmetry-Breaking Knobs

In the the current framework risk model we parameterize possible departures from strict universality via small sector-dependent parameters (e.g. \(\epsilon_{\rm EM}\), \(\epsilon_{\rm QCD}\)), which would induce drifts in dimensionless ratios and/or WEP violation and are therefore strongly constrained.

In Weyl-compensator language, such epsilon-type departures can be viewed (conceptually) as:

- sector-dependent anomalous dimensions / RG running that breaks exact universality,
- explicit symmetry-breaking couplings (non-universal coupling of matter sectors to the compensator),
- or effective anomaly terms that spoil exact scale locking.

This note makes **no claim** that any specific UV completion produces these parameters; it only provides a clean language in which:

1. Exact universality corresponds to a symmetry/structure, not a slogan.
2. Small non-universal corrections can be organized as explicit breaking knobs (the same \(\epsilon\) parameters used in the the current framework referee-facing risk parameterization).

## 5) What This Does and Does Not Claim

This mapping note:

- **does** provide a standard geometric/scalar-tensor vocabulary for "universality = symmetry",
- **does** motivate why frame changes are not, by themselves, "new physics",
- **does not** add new predictions, fits, or canonical results,
- **does not** claim a specific UV-complete ToE derivation for v11.0.0.

## References / Pointers

- Almeida et al. (2014), APS link:  
  https://link.aps.org/doi/10.1103/PhysRevD.89.064047
- Barreto (2017) / Weyl-integrable scalar-tensor preprint pointer (arXiv PDF):  
  https://arxiv.org/pdf/1707.08226

