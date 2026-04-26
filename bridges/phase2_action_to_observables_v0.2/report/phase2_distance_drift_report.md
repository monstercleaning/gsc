# GSC Phase 2 Prototype: Distance–Drift Consistency Check

**Goal:** Explore (in a strictly phenomenological way) whether a family of *always-positive* redshift–drift histories can still mimic the standard \(\Lambda\)CDM luminosity-distance curve over the redshift range most strongly constrained by SN Ia (roughly \(z\lesssim 2\)).

> ⚠️ **Important disclaimer**
>
> This is **not** a derivation from the GSC RG action.  
> It is a *numerical existence proof / feasibility scan* intended to guide Phase 2:
> - if even a toy always-positive-drift \(H(z)\) cannot match basic distance–redshift relations, the program is likely dead;
> - if it *can*, then the job becomes: **derive the same \(H(z)\) from the RG framework**.

---

## Models compared

### Baseline: flat \(\Lambda\)CDM
\[
H(z)=H_0\sqrt{\Omega_m(1+z)^3+\Omega_\Lambda}.
\]

We used \(H_0=67.4\,\mathrm{km/s/Mpc}\), \(\Omega_m=0.315\), \(\Omega_\Lambda=0.685\) as a representative reference curve.

### Always-positive redshift-drift family
We considered a running exponent toy model:
\[
H(z)=H_0(1+z)^{p(z)},\qquad p(z)=1-Ae^{-z/z_0}.
\]
If \(p(z)<1\) for all \(z>0\), then \(H(z) < (1+z)H_0\) and the standard FLRW drift expression implies:
\[
\dot z = (1+z)H_0 - H(z) > 0.
\]

---

## Fit target
We fitted \(A\) and \(z_0\) to minimize the mean squared **relative** error between the toy model luminosity distance \(d_L(z)\) and the \(\Lambda\)CDM \(d_L(z)\) over:
\[
z\in[0.05,2.5].
\]

Best-fit parameters:
- \(A\approx 0.621\)
- \(z_0\approx 0.680\)

So \(p(0)=1-A\approx 0.379\), and \(p(z)\to 1\) at high \(z\).

---

## Key results

### 1) Distances
- Max \(|\Delta d_L/d_L|\) over \(z\le 2.5\): **0.87%**
- Max \(|\Delta d_L/d_L|\) over \(z\le 5\): **6.17%**

See: `phase2_dL_relative.png`.

### 2) Redshift drift (velocity shift over 10 years)
For the best-fit always-positive-drift model:
- \(\Delta v_{10yr}(z=0.5)\approx 2.35\) cm/s  
- \(\Delta v_{10yr}(z=2)\approx 0.73\) cm/s  
- \(\Delta v_{10yr}(z=4)\approx 0.06\) cm/s  

See: `phase2_redshift_drift_compare.png`.

---

## Interpretation (what this means for GSC)

1. **Existence proof:**  
   There exist smooth \(H(z)\) families with **\(\dot z>0\)** that can track \(\Lambda\)CDM-like distance curves at \(\lesssim 1\%\) over the SN-dominated range.

2. **Trade-off:**  
   For this particular family, making distances nearly \(\Lambda\)CDM-like forces \(p(z)\to 1\) at high \(z\), which makes \(\Delta v\) at \(z\sim 4\) **very small** (still positive, but potentially challenging observationally).

3. **Phase 2 mandate:**  
   The RG framework must be used to **predict** a specific \(p(z)\) (or equivalent) and then we must test simultaneously:
   - distances (SN + BAO),
   - growth/lensing,
   - and the redshift-drift amplitude.

---

## Files generated
- `phase2_dL_relative.png`
- `phase2_redshift_drift_compare.png`
- `phase2_distance_drift_report.md`

