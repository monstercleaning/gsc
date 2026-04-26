# QCD-Gravity Bridge v0.1 (Sanity Checks + Kill-Tests)

## 1) Executive Summary (idea-bank only)

This annex is a deterministic sanity-check bundle for Phase-4 triage. It does
not introduce a new central claim.

Non-claims:
- We do **not** claim "gravity = strong force".
- We do **not** claim "QCD explains $M_{\mathrm{Pl}}$".
- We do **not** claim "RG beta-functions imply cosmic time variation".
- This is a motivation + falsification matrix artifact for reviewer inspection.

Repro command (deterministic):

```bash
python3 v11.0.0/bridges/phase4_qcd_gravity_bridge_v0.1/tools/make_qcd_gravity_bridge_artifacts.py \
  --outdir v11.0.0/bridges/phase4_qcd_gravity_bridge_v0.1/golden \
  --preset paper_grade \
  --seed 0 \
  --emit-plot 1 \
  --format text
```

## 2) Induced Gravity Sanity Check (Sakharov/Adler-Zee style)

Reference motivation: Donoghue & Menezes, arXiv:1712.04468.

Assumed ansatz (order-of-magnitude only):
- $M_{\mathrm{Pl,ind}}^2 \sim (N_{\mathrm{species}}/12\pi)\,\Lambda_{\mathrm{UV}}^2$

With explicit assumptions $(\Lambda_{\mathrm{UV}}, N_{\mathrm{species}})$, the generated
artifact reports induced-$M_{\mathrm{Pl}}$ and $G_{\mathrm{ind}}/G_N$ ratios.

Interpretation rule used here:
- If $M_{\mathrm{Pl,ind}} \ll M_{\mathrm{Pl,obs}}$ under conservative QCD/SM cutoffs,
  then this check is classified as **insufficient by itself**.

## 3) Trace/Weyl Anomaly Decomposition by Sector

Reference: Duff, hep-th/9308075.

Artifact includes a compact one-loop coefficient table with explicit convention:
- $\mathrm{d}g/\mathrm{d}\ln\mu = (b_i/16\pi^2) g^3$

Included sectors:
- QED/U(1) sign behavior
- EW/SU(2)
- QCD/SU(3)

What follows:
- Relative sign structure is a robust sanity signal.

What does **not** follow:
- No theorem mapping these coefficients directly to cosmological time drift.

## 4) QCD Vacuum-Energy Scaling Check

Reference motivation: Urban & Zhitnitsky, arXiv:0906.2162.

Artifact computes naive scaling:
- $\rho_{\mathrm{QCD,naive}} \sim H_0\,\Lambda_{\mathrm{QCD}}^3$
- compares against observed $\rho_{\mathrm{DE}}$ from $(H_0,\Omega_\Lambda)$
- reports ratio and required suppression factor when mismatch exists.

Interpretation rule:
- A large mismatch is a **kill/tension indicator** for direct-identification claims,
  not evidence for a solved mechanism.

## 5) Kill-Test Matrix (PASS / TENSION / KILLED / N-A)

The generated CSV matrix records row-wise applicability assumptions:
- `applies_if` states the coupling/screening assumptions under which a bound is relevant.
- Constraints include MICROSCOPE, clocks, Oklo, LLR, and combined-bound conditionality.

Critical caveat:
- Combined precision constraints are model-conditional. Without a shared coupling model,
  cross-probe aggregation is apples-vs-oranges.

## 6) Memo: "\mu-running != t-variation"

- RG equations run with renormalization scale $\mu$, not directly with cosmic time $t$.
- A usable $\mu\to t$ map requires extra assumptions:
  - scale-setting rule,
  - background/scalar dynamics,
  - screening/environment dependence.
- Therefore any claim of observable time variation from beta-functions alone is out of scope.

## Files produced by the deterministic tool

- `qcd_gravity_bridge_numbers.json`
- `qcd_gravity_bridge_kill_matrix.csv`
- `qcd_gravity_bridge_scale_plot.png` (fallback PNG, deterministic)
