# GSC the current framework — Measurement Model (Freeze-Frame, Universal Scaling)

## Purpose

GSC adopts **Option 2**: we do **not** automatically reuse the standard
ΛCDM/FLRW translation “observation → H(z), D_L, D_A, CMB…”.

Instead we first define a **measurement model**:
what physical standards (clocks/rods/atomic lines) do over time, and how an
observer turns raw measurements into the reported cosmological observables.

This document is the “source of truth” for that translation at the current framework scope.

## Core Objects

### Freeze frame
- Background metric is approximately static (Minkowski-like).
- The dominant cosmological evolution is carried by a single **universal scale**
  field `σ(t)` that controls bound matter scales.

### Universal scale field σ(t)
`σ(t)` is the characteristic size/length scale of bound matter (“ruler scale”).

We define the **collapse rate**

`H_σ(t) ≡ - (dσ/dt)/σ`.

## Universal Scaling Axioms

These are the simplifying “axioms” that make the measurement model predictive.

1. Bound lengths scale with σ:
   - `ℓ_bound(t) ∝ σ(t)`

2. Particle masses scale inversely with σ:
   - `m_i(t) ∝ σ(t)^(-1)`

3. Planck mass co-scales with matter:
   - `M_Pl(t) ∝ σ(t)^(-1)`
   - therefore the *infrared* Newton coupling scales as `G_IR(t) ∝ σ(t)^(+2)`

4. Dimensionless quantities are (approximately) invariant:
   - fine structure constant `α`, Yukawas, mass ratios, etc. are constant to
     high precision in local experiments.

5. Local metrology is a **null drift** prediction:
   - any purely local dimensionless ratio should show no secular drift beyond
     Standard Model/GR effects.

## Redshift Definition in the Measurement Model

Atomic transition energies scale as (hydrogenic intuition):
- `E_atom ∝ m_e` (since α is constant and `ħ,c` are treated as constants at this level).

With `m_e(t) ∝ 1/σ(t)`:
- `E_atom(t) ∝ 1/σ(t)`
- `ν_atom(t) ∝ 1/σ(t)`

A photon emitted at time `t_e` with energy set by the emitter’s atomic physics
is observed at `t_0` and compared to **today’s** atomic standards.

Therefore we define the observed redshift as:

`1 + z ≡ ν_emit / ν_obs (in today's units) = σ(t_e) / σ(t_0)`.

Equivalently:
- `z = σ_e/σ_0 - 1`

This is the operational meaning of cosmological redshift in Option 2.

## Classical Look-Back Effects (Time Dilation, Tolman)

Because the definition of redshift is tied to the evolution of our standards,
several classical “expansion tests” are naturally reinterpreted as metrology
effects in the freeze frame.

### Time dilation (SN Ia stretch)

Atomic clock rates scale as:
- `ν_atom ∝ 1/σ`

So the observer’s atomic “second” at `t_0` is shorter than the emitter’s at
`t_e` by:
- `s_0/s_e = ν_e/ν_0 = σ_0/σ_e = 1/(1+z)`

Therefore any emitter timescale (light curve width, variability timescale)
is observed to be stretched by:
- `Δt_0 = (1+z) Δt_e`

This reproduces the standard SN Ia `(1+z)` stretch without invoking geometric
expansion of the background.

### Tolman surface brightness scaling

In standard FLRW, surface brightness scales as:
- `B_obs/B_emit = (1+z)^(-4)`

In Option 2 the same scaling is recovered under the universal scaling axioms
plus the conservative reciprocity hypothesis used below:
- one factor `(1+z)^(-1)` from photon energy in today’s units
- one factor `(1+z)^(-1)` from arrival-rate dilation in today’s seconds
- two factors `(1+z)^(-2)` from the metrology of areas/solid angles

Operationally, this is consistent with Etherington distance duality
`D_L = (1+z)^2 D_A` (and thus `D_L = (1+z) D_M` in the flat case).

## Effective FLRW Map (Convenience Layer)

It is often convenient to define an **effective** scale factor:

`a(t) ≡ σ(t_0)/σ(t)`.

Then:
- `1 + z = a(t_0)/a(t_e)`
- `H(t) ≡ (da/dt)/a = - (dσ/dt)/σ = H_σ(t)`

This is a *bookkeeping map* that allows use of standard cosmology algebra
when it is purely kinematic and when we are explicit about what “time” means.

## Redshift Drift (Sandage–Loeb Observable)

The observable is:
- `ż ≡ dz/dt_0`

At the current framework scope we use the standard kinematic relation written in terms of the
effective history `H(z)`:

`ż = H_0 (1+z) - H(z)`

Interpretation in Option 2:
- `t_0` is the observer’s proper time measured by local atomic clocks (the time
  used in real experiments).
- `H(z)` is the effective collapse-rate history `H_σ(z)` under the mapping above.

If/when we refine the measurement model (v10+), this is the first place where
subtle “clock-definition” corrections might appear, so we treat it as a
supporting consistency diagnostic in the current Roadmap v2.8 framing.

### Frame equivalence vs history discriminant

- The conformal map itself is a variable choice. If two descriptions use the
  same physical `H(z)` history, dimensionless observables coincide.
- Sandage-Loeb `ż = H0(1+z) - H(z)` is therefore a kinematic relation, not a
  frame discriminator.
- The empirical discriminator is the chosen history class (`H(z)`), e.g.
  whether it satisfies `H(z) < H0(1+z)` in `z ~ 2–5`.
- Operationally, the historical drift diagnostic is a history-vs-history
  comparison (`H(z)_GSC` versus `H(z)_ΛCDM`) under the same kinematic relation.
- If `H(z)` matches ΛCDM, then these observables do not provide an empirical
  preference for one frame label over the other at this level; the difference
  is interpretation/bookkeeping rather than a new measurement equation.

## Distances (Working Hypothesis at v11.0.0)

For late-time (post-recombination) analyses we adopt a conservative working
hypothesis:
- photon propagation obeys geometric optics and Etherington reciprocity holds,
  so `D_L = (1+z)^2 D_A`.

We then compute distances using the effective history `H(z)` (flat case):

- Comoving distance:
  - `χ(z) = c ∫_0^z dz'/H(z')`
- Transverse comoving distance:
  - `D_M(z) = χ(z)`
- Angular diameter distance:
  - `D_A(z) = D_M(z)/(1+z)`
- Luminosity distance:
  - `D_L(z) = (1+z) D_M(z)`

## Standard Candles / Flux Mapping (Canonical at v11.0.0)

The “distance” that SN Ia constrain is defined operationally through flux
calibration. At the current framework we adopt the standard bolometric mapping as the
canonical *measurement-layer* definition:

- observed flux:
  - `F_obs` = energy received per unit detector area per unit observer time
    (all in *today's* standards at `t_0`)
- source luminosity:
  - `L_emit` = energy emitted per unit emitter proper time
    (in the emitter's local standards at `t_e`)

We define the luminosity distance `D_L` by:

`F_obs ≡ L_emit / (4π D_L^2)`.

### (1+z) factors (bookkeeping)

Under universal scaling, the two standard factors appear as metrology:
- photon energy in today's units: `E_obs = E_emit/(1+z)`
- arrival-rate dilation in today's seconds: `dt_obs = (1+z) dt_emit`

Therefore the bolometric flux is suppressed by `(1+z)^(-2)` relative to the
pure geometric `1/(4π r^2)` falloff, which is equivalent to:

`D_L = (1+z) D_M`  (flat case),

consistent with Etherington duality `D_L = (1+z)^2 D_A`.

### Distance modulus (what SN analyses fit)

Define the distance modulus:

`μ(z) ≡ 5 log10(D_L(z)/10 pc)`.

Then (schematically):

`m = M + μ(z) + (K-corrections + dust + stretch/color terms + ...)`.

v11.0.0 policy:
- treat `M` (and any bandpass/correction terms) as **nuisance** in a late-time
  fit harness;
- do **not** claim a first-principles prediction for SN luminosity evolution
  with `σ(t)` at the current framework scope.

## BAO (Late-Time Safe Treatment at v11.0.0)

BAO measurements constrain geometric combinations of distances via the observed
angular scale and redshift separation of the BAO feature. In standard notation,
these map to:
- transverse comoving distance `D_M(z)`
- Hubble distance `D_H(z) = c/H(z)`
- (sometimes) volume distance `D_V(z)`

At the current framework scope we **do not** claim a freeze-frame derivation of the drag-epoch
sound horizon `r_d` from early-universe microphysics (this is deferred to v10+).

Therefore, the late-time harness treats `r_d` as a **free nuisance parameter**
and compares BAO data only through ratios like:
- `D_M(z)/r_d`, `D_H(z)/r_d`, `D_V(z)/r_d`

This keeps the BAO block honest and compatible with the Option 2 philosophy:
late-time kinematics + explicit measurement mapping, without early-universe
overreach.

## the current framework Definition of “Done” (Scope)

v11.0.0 is explicitly late-time focused. “Done” at the current framework means:
- This measurement model is written and consistent.
- We can compute `z`, `ż`, and baseline distances reproducibly.
- Primary discriminator follows Roadmap v2.8:
  `epsilon` / measurement-model inference + cross-probe consistency triangles.
- Redshift-drift sign checks at `z ~ 2–5` remain supporting diagnostics
  (historical no-go/pre-check evidence), not the primary project discriminator.

Full early-universe / full CMB-likelihood claims require v10+ work:
freeze-frame mapping of recombination physics, sound horizon, transfer
functions, and likelihood interfaces.
