# GSC Phase 2 — Action → Observables (v0.2)

**Status:** Prototype / bridge document.

**Why this exists:** GSC v10.1 intentionally used a minimal phenomenological ansatz for the redshift-drift plots,

\[ H(z) = H_0 (1+z)^p, \]

because the v10.1 paper was scoped to late-time kinematics and “null tests”.
Peer review will still ask a direct question: **“Where does the exponent \(p\) come from?”**

This Phase 2 note closes that *Action-to-Observable gap* in the smallest possible way:

1. Provide an explicit action (a standard scalar-field action) that has known attractor solutions.
2. Show how the power-law \(H(z)\) emerges from that action.
3. Quantify the **distance–drift tradeoff** of the \(p<1\) regime (the regime that gives **positive redshift drift at all redshifts** in the standard drift formula).

> **Important scope note:** This is **not** yet “GSC-CAM/CLASS”. It is a controlled bridge step.

---

## 1. Minimal action that reproduces the Phase 1 drift ansatz

We start with the canonical scalar action (Einstein frame):

\[
S = \int d^4x \sqrt{-g} \left[ \frac{M_P^2}{2}R - \frac{1}{2}(\partial\phi)^2 - V(\phi)\right].
\]

Choose an exponential potential

\[
V(\phi)=V_0\,e^{-\lambda \phi/M_P}.
\]

This system admits a scalar-field dominated power-law solution (an attractor in the relevant parameter range),

\[
a(t)\propto t^{\;2/\lambda^2},\qquad
w_\phi = \frac{\lambda^2}{3}-1.
\]

Then

\[
H(z)\propto (1+z)^{p},\qquad p=\frac{\lambda^2}{2}=\frac{3}{2}(1+w_\phi).
\]

So the previously “floating” phenomenological exponent \(p\) is re-interpreted as a **single slope parameter** of an explicit action.

**Key point:** In this prototype we do **not** claim that the exponential potential *is* the true GSC RG potential.
We claim something narrower but very useful: *there exists an explicit action whose attractor reproduces the same H(z) family used in v10.1.*

---

## 2. Redshift drift and the “always-positive” regime

We use the standard drift relation

\[
\dot z = H_0(1+z)-H(z),
\]

which follows directly from the FRW relation between emission and observation times.

For \(H(z)=H_0(1+z)^p\):

* If \(p<1\), then \(H(z)<H_0(1+z)\) for all \(z>0\) and therefore **\(\dot z>0\) at all redshifts**.
* If \(p>1\), the drift becomes negative at sufficiently high \(z\) (the familiar \(\Lambda\)CDM behavior).

---

## 3. Pre-data “distance–drift tradeoff” scan

Even before importing real SN/BAO likelihoods, it is valuable to understand the structural tension:

* Smaller \(p\) ⇒ larger positive drift signal.
* Smaller \(p\) ⇒ smaller \(H(z)\) at moderate/high \(z\) ⇒ larger luminosity distances compared to a \(\Lambda\)CDM baseline.

To quantify this, we run a *screening scan* over \(p\in(0,1)\) and compute:

* **Distance penalty:** \(\max_{z\le 2}|\Delta\mu(z)|\), where \(\Delta\mu\) is the distance modulus difference relative to a baseline flat \(\Lambda\)CDM (\(\Omega_m=0.3\)).
* **Drift signal:** \(\dot v\) at \(z=3\), converted to cm/s/year.

This does **not** claim \(\Lambda\)CDM is “true”; it uses \(\Lambda\)CDM only as a **proxy reference curve** known to match late-time distance data reasonably well.

### Outputs

**(a) Distance deviation vs p**

![](../outputs/phase2_tradeoff_max_abs_dmu_vs_p.png)

**(b) Drift amplitude at z=3 vs p**

![](../outputs/phase2_tradeoff_vdot_z3_vs_p.png)

**(c) Scatter: drift vs distance deviation**

![](../outputs/phase2_tradeoff_scatter.png)

### Main quantitative takeaway

If one demands a conservative screening cut

\[
\max_{z\le 2}|\Delta\mu|\lesssim 0.1\,\mathrm{mag},
\]

then (for the chosen baseline) the scan favors approximately

\[
 p\approx 0.75\text{–}0.80.
\]

In that window, \(\dot v(z=3)\) remains **positive** and typically of order **0.5–0.6 cm/s/year**
(i.e. several cm/s over a decade), which is still a strong discriminant against \(\Lambda\)CDM’s negative drift at the same redshifts.

---

## 4. What this changes for GSC development

This v0.2 update answers the two most damaging “Phase 1 style” criticisms:

1. **“p=0.5 is arbitrary.”**
   *Phase 2 reframes p as an action parameter (\(\lambda\)).*

2. **“Even if you can make drift positive, you probably break distances.”**
   *The tradeoff scan makes that tension explicit and quantifies a plausible p-window to explore next.*

It also suggests a clear engineering target for the true RG-driven model:

> **The RG potential should generate an effective p(z) that stays below 1 (for positive drift),
> while staying near the “distance-safe” band suggested by the scan over the redshift range where SN/BAO are measured.**

---

## 5. Next step (Phase 2.1)

**Do not modify v10.1.** Keep v10.1 frozen as the “late-time null tests + drift sign” paper.

Instead, develop Phase 2 as a separate follow-on manuscript with two concrete upgrades:

1. **Replace constant-p with a derived p(z):**
   * Move from exponential potentials (constant \(\lambda\)) to a slowly running slope \(\lambda(\phi)\) motivated by the RG running ansatz.

2. **Attach real low-z likelihoods:**
   * Pantheon+/SN likelihood
   * BAO (with \(r_d\) treated as a nuisance parameter at first, consistent with the “late-time only” scope)

---

## Reproducibility

From the repository root:

```bash
python scripts/run_all.py
```

Or run the scan alone:

```bash
python scripts/phase2_action_tradeoff_scan.py
```
