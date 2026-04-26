> **HISTORICAL / DO NOT SUBMIT AS-IS**
>
> This legacy draft is retained for provenance. Current canonical framing is
> Roadmap v2.8 with `v11.0.0/GSC_Framework_v10_1_FINAL.md`; drift-sign wording
> here is historical and not the primary Phase-4 discriminator.

# Gravitational Structural Collapse (GSC) v10.1  
## A Renormalized, Scale‑Covariant Framework for Static‑Space Cosmology and Global Energy Conservation

**Status:** Working research draft (January 2026)  
**Audience:** Theoretical cosmology / gravity, with emphasis on falsifiable tests and precision‑measurement consistency.

---

## Abstract

We present **GSC v10.1**, a scale‑covariant cosmological framework in which the background spacetime can be represented as static (Minkowski in a “freeze frame”), while all **dimensionful** particle‑physics scales (masses, bound‑state radii, clock frequencies) vary coherently with a single cosmic scale field \( \sigma(t) \). In this class of scalar–tensor‑like descriptions, an expanding FLRW picture with constant particle masses can be related by a conformal transformation to a shrinking‑atom picture in which cosmological redshift arises from evolving emitters and detectors rather than metric expansion.

The central theoretical pivot from GSC v9.x is a shift from ad hoc enhancement models to an explicitly **renormalization‑group (RG) running** hypothesis for gravity: the effective coupling \(G(\sigma)\) increases toward a critical scale \(\sigma_*\), potentially leading to accelerated “collapse” dynamics \( \dot\sigma/\sigma \) without arbitrary exponents. We treat \(\sigma_*\) as a phenomenological parameter unless independently derived from microphysics.

A major conceptual feature of the static‑background picture is its **global energy bookkeeping**: cosmological redshift need not be interpreted as photons losing energy “to expanding space”. Instead, photon energy can remain constant along propagation in the static background while detector energy scales evolve.

**Falsifiability:** The framework is designed around a decisive look‑back observable: the **redshift drift** (\(\dot z\), Sandage–Loeb test). In the simplest accelerated‑collapse realization, the redshift‑drift sign pattern differs from \(\Lambda\)CDM at high redshift, making the model testable with ELT/ANDES‑class ultra‑stable spectroscopy. We also give a concrete “metrology shield”: a scale‑covariant **geometric lock** showing why local systems such as GPS need not exhibit secular drift if all local scales transform universally.

---

## 1. Motivation and triage from v9.x

GSC v9.x contained strong ideas (static‑space cosmology; redshift drift as a decisive discriminator) mixed with components that were easy to falsify or that relied on numerically fragile estimates (e.g., cosmic‑torsion explanations of nuclear anomalies; Casimir deviations at 10–100 nm).

**v10.1 implements a disciplined triage:**
- **Core (must survive):** scale covariance, frame map, RG‑running gravity ansatz, global energy bookkeeping, redshift‑drift falsification program.
- **Optional modules (explicitly separated):** intrinsic hadronic torsion; dark sector as superfluid vortices/defects.
- **Removed from the core:** Casimir deviation claims; over‑specific “anomaly‑solving” numerology.

This modular approach is meant to avoid the “Frankenstein failure mode”: one wrong sub‑claim should not kill the core.

---

## 2. Expansion–collapse duality and scale covariance

### 2.1 Kinematic frame map

Scalar–tensor cosmology admits physically equivalent descriptions related by conformal rescalings. A useful language distinguishes:

- **Einstein‑like frame:** particle masses constant, metric expands (FLRW).  
- **Freeze frame:** background geometry approximately Minkowski; masses vary; atoms shrink; cosmological redshift emerges from changing emitter/detector scales.

Because only **dimensionless** ratios are observable, coherent re‑scalings can be invisible to local experiments.

### 2.2 Scale‑covariant “geometric lock” for GPS / metrology

Assume a universal scaling field \( \sigma(t) \) such that (illustratively)
- masses \(m \propto \sigma^{-1}\)
- Newton coupling \(G \propto \sigma^{2}\)
- lengths \(r \propto \sigma\)

Then \(GM \propto \sigma\), and the Kepler period scales as
\[
T_{\rm orbit}\propto \sqrt{\frac{r^3}{GM}}
\;\;\Rightarrow\;\;
T_{\rm orbit}\propto \sqrt{\frac{\sigma^3}{\sigma}}
\propto \sigma.
\]
Atomic periods scale as \(T_{\rm atom}\propto 1/m \propto \sigma\). Hence
\[
\frac{T_{\rm orbit}}{T_{\rm atom}} = \text{constant}.
\]
This is the **geometric lock**: if the scaling is universal, an orbiting atomic‑clock system can remain self‑consistent and exhibit no secular drift in its own internal units.

A minimal toy plot demonstrating the cancellation is provided in the companion simulation folder:
- `GSC_v10_sims/scale_covariance_gps.png`

**Important:** this lock is not a “free pass”. It imposes a **hard consistency condition**: any non‑universal scaling between different sectors (QCD vs electroweak) will generate composition‑dependent effects constrained by WEP tests and atomic‑clock comparisons.

---

## 3. Renormalized scale‑dependent gravity

### 3.1 Minimal RG‑running hypothesis

We do **not** claim a complete derivation from asymptotic safety. Instead we adopt a minimal RG‑motivated hypothesis:

1. There exists an effective gravitational coupling \(G(\sigma)\) that runs with a physical scale \(\sigma\) (or \(k\sim 1/\sigma\)).  
2. The running contains a rapid‑growth regime near a critical scale \(\sigma_*\).  
3. As \(\sigma(t)\) decreases, \(G(\sigma)\) increases and can drive an accelerated collapse rate.

An illustrative parameterization (Landau‑pole form) is
\[
G(\sigma)=\frac{G_N}{1-(\sigma_*/\sigma)^2}.
\]
A plot of this running and its near‑pole sensitivity is in:
- `GSC_v10_sims/rg_running_landau_pole.png`

### 3.2 The \(\sigma_*\) issue

A frequent and valid criticism of earlier drafts was to treat \(\sigma_*\approx r_p\) as a “prediction”. In v10.1:

- \(\sigma_*\) is an **effective critical scale parameter**.
- Any numerical identification (e.g., “near a hadronic scale”) is **phenomenological** unless derived from microphysics.

This is the correct scientific posture: the framework is falsifiable even if \(\sigma_*\) is not (yet) derived from first principles.

---

## 4. Global energy bookkeeping

In expanding‑space cosmology, “global energy conservation” is subtle: a time‑dependent background generally lacks a global timelike Killing vector, so “total energy of the Universe” is not a conserved Noether charge in the usual sense. In practice, cosmological redshift is often described as photons “losing energy” as the Universe expands.

In the GSC freeze‑frame picture, redshift can be reinterpreted:
- Photon energy in a static background can remain constant along propagation.
- The detector’s reference scale (atomic transition energy) evolves with \(\sigma(t)\).
- The observed redshift reflects a mismatch between emitter and detector scales.

This reframing is conceptually attractive for global bookkeeping. It does **not** automatically solve the cosmological constant problem; it changes the accounting language and motivates seeking a static‑background description in which Noether’s theorem applies more transparently.

---

## 5. Precision tests and consistency conditions

### 5.1 Weak Equivalence Principle (WEP)

If the scaling is universal (a single conformal factor for all matter), composition‑dependent free‑fall violations are suppressed. However, any sector‑dependent scaling (e.g., QCD vs electroweak) produces an Eötvös parameter \(\eta\) that is strongly constrained by modern experiments.

### 5.2 Oklo / atomic clocks / “varying constants”

Even in a scale‑covariant picture, **dimensionless** parameters remain observable and constrained. A viable GSC realization must keep (or predict) extremely small drifts in:
- \(\alpha\) (fine structure constant)
- \(m_e/m_p\)
- nuclear resonance ratios (Oklo‑type bounds)

### 5.3 Why \(\dot G/G\) bounds must be translated carefully

Solar‑system and pulsar bounds on \(\dot G/G\) are commonly quoted under assumptions about fixed rods/clocks and fixed particle masses. In a scale‑covariant framework the correct statement is:

> such experiments constrain **dimensionless combinations** built from orbital dynamics and electromagnetic timing, not an “absolute” \(G(t)\).

This does not evade the constraints; it demands a careful mapping of what is actually measured. A proper “constraint translator” is part of the Phase‑2 program (Sec. 9).

---

## 6. The decisive prediction: redshift drift (Sandage–Loeb test)

### 6.1 Observable

Redshift drift is defined by
\[
\dot z(z)=H_0(1+z)-H(z),
\qquad
\Delta v \approx c\,\frac{\dot z}{1+z}\,\Delta t.
\]
It is a **look‑back** measurement: it compares the redshift of the *same* source observed at two different times. Once a physical clock is specified for the observer (atomic time), this drift is not removable by local rescalings.

### 6.2 What GSC must specify

To make a sharp prediction, GSC must specify an effective \(H(z)\) (equivalently \(\sigma(t)\)). Different collapse laws lead to different drift curves, but the simplest accelerated‑collapse realizations generically yield:
- \(H(z) < H_0(1+z)\) over a broad redshift range
- therefore \(\dot z > 0\) (contrast with ΛCDM’s high‑\(z\) negative drift)

A minimal toy comparison (ΛCDM vs one accelerated‑collapse toy law) is provided in:
- `GSC_v10_sims/redshift_drift_10yr.png`  
- `GSC_v10_sims/GSC_v10_Simulations_Report.md`

**Interpretation:** v10.1 treats this as the *primary falsifier*. If future ELT/ANDES observations confirm the ΛCDM high‑\(z\) negative drift with sufficient precision, the simplest accelerated‑collapse GSC is ruled out.

---

## 7. Optional modules (kept separate)

### Module M1: Intrinsic hadronic torsion (deferred)

A local spin–torsion coupling inside hadrons could in principle generate keV‑scale shifts without invoking cosmic torsion. This requires serious EFT/QCD development and is not part of the v10.1 core.

### Module M2: Dark sector as superfluid vortices / topological defects (deferred)

To avoid Derrick‑theorem objections, any “lump” model should be formulated as:
- topological defects (strings/vortices), or  
- time‑dependent non‑topological objects (Q‑balls/oscillons), or  
- effective fluid descriptions

This is not required for the redshift‑drift falsification program and is intentionally left modular.

---

## 8. Risk register (what can kill v10.1)

**Core falsifier**
- A robust ELT/ANDES detection of the ΛCDM high‑\(z\) negative drift pattern at the predicted amplitude would strongly disfavor the simplest accelerated‑collapse GSC.

**Core theoretical risk**
- Without a microphysical derivation of \(\sigma_*\), the RG running remains phenomenological. This is acceptable for a falsifiable hypothesis, but must be presented honestly.

**Core consistency risk**
- Any non‑universal scaling between sectors is severely constrained by WEP and atomic clock limits.

---

## 9. Phase‑2 program (recommended next actions)

1. **Replace toys with a minimal dynamical model:** choose a specific \(\sigma(t)\) equation (RG‑motivated effective action) and fit only distance‑redshift data; avoid anomaly hunting.
2. **Constraint translator notebook:** map each experimental constraint (LLR, pulsars, Oklo, atomic clocks) to the dimensionless combination it constrains under scale covariance.
3. **Redshift‑drift forecast:** use published ANDES performance assumptions to generate a realistic detectability forecast vs GSC parameter space.

---

## Files generated with this draft

- `GSC_Framework_v10_1.md` (this file)  
- `GSC_v10_sims/` (scripts + figures + mini‑report)
