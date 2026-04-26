# GSC — Consolidated Roadmap v2.5.1 (Final, reviewed)

**Date:** 2026‑02‑27 (Europe/Sofia)  
**Repo baseline:** the framework (Phase‑3 infrastructure ≥ `m138`; roadmap is forward‑looking and does not assume any specific future tag)  
**Audience:** project lead, prospective collaborators/reviewers, and future “red team” readers  
**Primary objective:** convert GSC from a *single‑model claim* into a **reproducible evaluation framework** that produces publishable results even when the answer is “no”.

---

## Patch notes (v2.5.0 → v2.5.1)

This patch pass applies documentation and policy hygiene updates:

1. **Doc typo fixes** in the v11 cutover guidance (Mode A/Mode B directory references).
2. **Phase‑4 header normalization** for milestone‑stable reviewer docs.
3. **AI usage + validation policy doc** added as a reviewer-facing governance artifact.


---

## 0) Executive synthesis

### 0.1 What GSC should *stop trying* to be (for now)

- Not “a new alternative to ΛCDM that replaces QFT”.  
- Not “a full UV completion / quantum gravity solution”.  
- Not “a dark‑matter replacement” until perturbations + lensing/dynamics consistency is addressed.

Those remain legitimate **long‑term research directions**, but pursuing them *now* is strategically dominated by the community’s existing large collaborations and toolchains.

### 0.2 What GSC can realistically become — and why it matters

GSC’s real competitive advantage is not a specific action (which often maps to known scalar‑tensor/quintessence classes), but a **formal, reproducible framework** for:

1. **Measurement‑model dependence** in cosmological inference (explicit mapping from raw observations → inferred cosmological parameters under varying metrology assumptions).
2. **Falsification‑first / kill‑test methodology**, with claim management, deterministic artifact pipelines, and first‑class negative results.
3. **Precision null‑test cartography**: systematic constraints on (ε‑space) departures from universal scaling using laboratory + astrophysical bounds.

If GSC proves measurement‑model variation is negligible, that is a publishable confirmation that strengthens standard inference.  
If it is non‑negligible, it creates a new axis for understanding tensions (H₀, S₈, etc.) with explicit diagnostics.

### 0.3 The “structural wall” to elevate to first‑class output

Phase‑2 E2 synthesis indicates a strong trade‑off between **drift‑sign** objectives and **distance/CMB closure** under tested deformation families. This is not an “implementation bug”; it is plausibly a **structural constraint** on smooth histories H(z) when drift and distance integrals are tied to the same function.

**Reminder of the functional coupling:** the Sandage‑Loeb observable obeys  
\(\dot z(z) = H_0(1+z) - H(z)\), while standard distance observables constrain integrals of the form \(D(z) \propto \int_0^z \mathrm{d}z'/H(z')\). If a class of deformations cannot satisfy both simultaneously, that is a *structural* limitation of that class, not a tuning failure.

A core output of this roadmap is to turn “we scanned and failed” into a **reproducible, generalizable negative result** (empirical no‑go + formal conjecture + explicit conditions).

### 0.4 One‑sentence positioning (for reviewers)

> **GSC is a reproducible falsification framework for late‑time cosmology and metrology‑dependent inference, with first‑class claim management and publishable negative results.**

---

## 1) Claim ladder (avoid category errors)

To prevent “fit” being marketed as “unification”, the project must explicitly maintain a claim ladder with acceptance criteria at each rung:

1. **Empirical adequacy (Fit):** comparable fit to ΛCDM on defined datasets with comparable degrees of freedom.  
2. **New falsifier (Kill test):** a robust prediction that differs from ΛCDM in an observable that cannot be removed by frame/unit conventions.  
3. **Unified effective description (DE+DM):** a single mechanism explains both background + structure + lensing without hidden extra components (or clearly states components).  
4. **Microphysical bridge (QFT/QG):** controlled EFT/RG derivation with stated approximations and scale‑setting; not “hand‑wavy RG motivation”.

Roadmap deliverables explicitly map to these rungs.

---

## 2) Publication strategy (re‑ordered for credibility and feasibility)

### Paper‑4 (Priority‑0): **CosmoFalsify** — reproducible evaluation framework (software + methodology)

**Target venues:** JOSS; *Astronomy & Computing*; optionally arXiv (if endorsement available).  
**Why first:** publishable without new physics; strongest differentiator; reduces the “outsider” credibility gap.

**Core contributions:**
- deterministic artifact pipeline (plans → scans → merges → bundles → verify → reviewer packs)  
- schema‑validated results with provenance DAGs  
- portable‑content linting and leak prevention  
- “verification matrix” linking claims → scripts → artifacts → hashes  
- reusable templates for adding new models/datasets/kill‑tests safely

**Success criteria:** a reviewer can run a minimal example and reproduce artifacts in <1 hour with deterministic hashes.

---

### Paper‑0 (Early narrative anchor): Late‑time framework & measurement model (minimal‑claim, high clarity)

**Role:** provide a conservative scientific narrative anchor and orient non‑specialists.  
**Distribution options:** Zenodo/OSF preprint; optionally arXiv if endorsement is available.

**Core message:** explicit measurement model layer + falsifiers + scope boundaries + reproducibility.

---

### Paper‑3 (Solo‑feasible): **Null‑Test Cartography in ε‑space** (precision constraints translator → full map)

**Target audience:** varying‑constants, metrology, cosmological inference methodology.  
**Key novelty:** unified constraint landscape across multiple precision tests; identifies which experiments dominate which region of parameter space.

**Scope guard:** does not require claiming a full action; treats ε‑space as a parameterization of metrology departures.

---

### Paper‑1 (Collab‑preferred): **No‑Go / Structural bound** for drift‑sign vs distance compatibility

**Two‑tier plan:**
- **Tier 1 (solo):** empirical no‑go with reproducible scans + formal statement of conditions + tight numerical bound.  
- **Tier 2 (with mathematician/physicist):** promote to theorem/lemma‑chain (PRD‑style venues).

**AI policy:** AI can help draft exposition, but analytic proof steps must be human‑verified and/or independently symbolically checked.

---

### Paper‑2 (Hardest; high novelty): **Measurement Model Dependence in Cosmological Inference**

**Deliverable:** systematic sensitivity analysis: how inferred (H₀, Ωm, σ₈, w₀, wₐ, …) shift under controlled measurement‑model variations, including “consistency triangles” across EM/QCD/gravity observables.

**Realism:** 6–18 months. Requires careful statistics, priors, and systematics; collaborator strongly recommended.

---

## 3) Workstreams and milestones (Phase‑4)

### Phase‑4A — Credibility & reviewer UX (0–3 months)

**4A.1 — Create `docs/REVIEW_START_HERE.md` (single‑page “review map”)**
- what to read first (paper, measurement model, reproducibility)  
- minimal commands to reproduce key figures/claims  
- “expected outputs” checklist (filenames + SHA256)

**4A.2 — Add `docs/VERIFICATION_MATRIX.md`**
- table: claim/rung → test script → dataset → acceptance threshold → artifact path → hash  
- explicitly mark which rungs are *not* claimed.

**4A.3 — Red‑Team automation (v1)**
Codify adversarial checks as scripts/tests:
- “frame transformation” equivalence sanity checks (where applicable)  
- “distance vs drift” trade‑off regression  
- “portable content” leak regression  
- “look‑elsewhere / prior sensitivity smoke checks” (non‑Bayesian first pass)

**4A.4 — Prior‑art / novelty map**
Create `docs/PRIOR_ART_MAP.md`:
- component‑by‑component mapping to known literature (freeze picture, scalar‑tensor equivalences, EFT‑of‑DE tooling, etc.)  
- explicitly isolate what remains novel *after* mapping (usually: measurement‑model dependence + verification methodology)  
- align with claim ledger (“what we do **not** claim” is as important as what we claim).

**4A.5 — Data and licensing manifest**
Create `docs/DATA_LICENSES_AND_SOURCES.md`:
- what is vendored in the repo vs downloaded  
- citations + licenses/usage permissions for each dataset  
- hash‑pinned download scripts for any non‑redistributable data  
- explicit statement of “redistributable‑by‑default” policy for the main repo

**4A.6 — Frames/units/invariants explainer (reviewer disarm)**
Create `docs/FRAMES_UNITS_INVARIANTS.md`:
- list which observables are treated as **frame‑invariant** in GSC’s measurement model  
- show explicitly which quantities are conventions (e.g., parameterizations) vs physical observables  
- provide the “consistency triangle” definitions as *invariant tests* (not as model‑dependent rhetoric)  
- include a short “FAQ‑style” section: “Is this just units?”, “What changes when ε≠0?”, “What is actually measured?”

**4A.7 — DM Decision Memo (scope lock)**
Create `docs/DM_DECISION_MEMO.md`:
- DM interpretation choice (A/B/C) plus a new option **D: “apparent DM signatures partially due to measurement‑model mismatch”**  
- list must‑pass tests for any DM claim (rotation curves, lensing vs dynamics, clusters/Bullet‑class constraints, linear growth, etc.)  
- state explicitly what would *falsify* each option  
- tie to claim ladder rung‑3 (DE+DM) so it cannot drift into rung‑1/2 claims.

**4A.8 — Dataset onboarding policy for Paper‑2**
Create `docs/DATASET_ONBOARDING_POLICY.md`:
- start: redistributable + small datasets already in‑repo (or tiny hash‑pinned downloads)  
- next: public likelihoods with hash‑pinned acquisition and license clarity  
- every dataset must have: schema, provenance, citation, and a “minimal toy mode” for reviewers.

**4A.9 — CosmoFalsify packaging for JOSS/A&C**
- stable CLI entrypoint(s), minimal examples, deterministic outputs  
- DOI via Zenodo  
- LICENSE / CITATION.cff / CONTRIBUTING / CODE_OF_CONDUCT  
- `paper.md` (JOSS) or software‑paper skeleton (A&C)  
- cross‑platform smoke: minimal demo in CI on Linux; optionally macOS if feasible.

**4A.10 — Publish Paper‑4 (submission)**

---

### Phase‑4B — Measurement‑model space & ε‑space (3–12 months; staged)

**4B.1 — Formalize “measurement model space” as code**
Define a small set of parameterized measurement models `M(θ_M)` with explicit mapping:
- raw observable → inferred quantity under model M  
Ensure every mapping is unit‑consistent and exposes dimensionless invariants.

**4B.2 — Sensitivity kernels (first‑order)**
Compute ∂(inferred parameters)/∂θ_M under simplified assumptions.  
Require independent verification: numeric finite‑difference checks + limiting‑case recovery tests.

**4B.3 — Consistency triangles (v1)**
EM‑anchored vs QCD‑anchored vs gravity‑anchored observables:
- EM: SN luminosity distances, time dilation (where applicable)  
- QCD: BAO/r_s‑anchored distances (with explicit “what is assumed about r_s?” note)  
- Gravity: lensing and (where available) GW sirens  
Produce diagnostic “tension fingerprints” that map to ε‑space directions.

**4B.4 — Null‑test cartography expansion (Paper‑3)**
Build the full ε‑space constraint map with provenance of each bound and conservative combination rules.  
Outputs must be: publishable plots + machine‑readable tables + schema‑validated artifacts.

**4B.5 — Paper‑2 execution plan (stats‑first)**
- preregister key tests/predictions to avoid a‑posteriori tuning  
- start with toy likelihoods → then public likelihoods if feasible  
- explicitly report prior sensitivity and posterior predictive checks.

---

### Phase‑4C — Perturbations as viability gate + path to DE/DM claims (start earlier than v2.3)

**Rationale:** perturbations are not “optional later”; for any theory beyond canonical quintessence they are the first place models die (ghosts, gradient instabilities, lensing/dynamics mismatch).

**4C.1 — Perturbations MVP gate (baseline)**
- for a canonical quintessence baseline, document stability and linear growth behaviour and lock it as reference.  
- define the minimal stability checklist:
  - no ghosts (positive kinetic term), no gradient instability (c_s^2 ≥ 0), well‑posed initial conditions  
  - linear growth sanity (fσ₈ behaviour vs baseline; does not need to “solve” S₈)

**4C.2 — “Any new theory must pass 4C.1” policy**
Add CI guard: any new modified‑gravity / non‑minimal coupling must include stability checks (analytic where possible, numeric otherwise).

**4C.3 — Minimal lensing/dynamics consistency test (DM track gate)**
Even without full non‑linear modelling, require a linear‑regime check that lensing potential and dynamical potential behave consistently with constraints.  
If the model cannot address both, DM‑replacement claims remain off the table.

**4C.4 — Only after 4C.1–4C.3: pursue DE+DM unification track**
This keeps the project from sinking time into background‑only models that are perturbatively sick.

---

## 4) Collaboration strategy (realistic under “outsider problem”)

### 4.1 Who to target first (low reputational risk, high alignment)

Prioritize collaborators who already value software/methodology contributions:

- cosmology/astro‑statistics + software engineers (survey pipelines, likelihood tooling)  
- contributors to Astropy, CLASS/CAMB tooling, Cobaya/MontePython/NumCosmo‑style ecosystems  
- “beyond‑ΛCDM” inference people who publish methodology papers, not only new models

**Pitch:** “co‑author a software/methodology paper with deterministic reproducibility and artifact‑verified results”.

### 4.2 What not to rely on

- Don’t assume a random postdoc will join a speculative alternative model led by an independent researcher.  
- Don’t assume theory‑heavy proof work can be done by AI. It cannot be trusted for theorem‑grade rigor.

### 4.3 Collaboration artifacts to prepare

- a 1‑page “collaboration menu”: modular tasks that are publishable and low risk  
- issues labeled “good first issue” for contributors  
- a code review protocol + maintainer checklist (fast onboarding)

---

## 5) AI disclosure and analytic‑claim policy

### 5.1 Disclosure (default)

- disclose AI assistance for code drafting, documentation drafting, and literature triage  
- emphasize that all **scientific claims are backed by deterministic pipelines and tests**, and analytic claims are independently validated

### 5.2 Analytic‑claim policy (hard rule)

Any analytic derivation that affects conclusions must satisfy at least one:

- independent derivation by a human collaborator, or  
- symbolic verification (where feasible), or  
- numerical cross‑checks (finite differences, limiting cases, synthetic data recovery), plus a clear error budget.

AI output is treated as **a draft**, not a proof.

### 5.3 Authorship and provenance (practical rule)

- AI systems are not authors.  
- Keep a lightweight provenance note (what was AI‑assisted vs human‑written) so reviewers can trust the boundary between “drafting” and “validated result”.

---

## 6) Risk register (updated)

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| **Collaboration fails due to “outsider” reputational risk** | Medium‑High | High | Lead with JOSS/A&C software paper; target astro‑software people; keep physics claims conservative |
| **ArXiv endorsement barrier blocks visibility** | Medium | Medium | Use JOSS/A&C + Zenodo DOI; seek endorser after first software publication |
| **Paper‑1 no‑go cannot be made theorem‑rigorous solo** | High | Medium | Publish Tier‑1 (empirical no‑go + conjecture); recruit mathematician for Tier‑2 |
| **Measurement‑model study becomes too large / under‑specified** | Medium | High | Start with tiny `M(θ_M)`; preregister tests; build from toy likelihoods |
| **Perturbation instability kills promising theory extension** | Medium | High | Move perturbations MVP earlier; gate any extension on stability checks |
| **Novelty diluted into known scalar‑tensor literature** | Medium | Medium | Embrace mapping as prior‑art context; shift novelty claim to measurement‑model dependence + verification methodology |
| **“Just units / just a frame” misinterpretation dominates review** | Medium | High | Add FRAMES_UNITS_INVARIANTS doc; emphasize invariant observables + consistency tests; keep claims rung‑appropriate |
| **Data licensing/provenance questions derail review** | Medium | High | Maintain explicit data manifest + licenses + hash‑pinned acquisition; redistributable‑by‑default main repo |
| **Scope creep / over‑engineering stalls output** | Medium‑High | High | Decision gates; prioritize Paper‑4; freeze new features unless tied to a paper deliverable |
| **AI errors leak into analytic sections** | Medium | High | Enforce analytic‑claim policy; require independent verification; keep proofs modular |

---

## 7) Success criteria (so the roadmap can “finish”)

The project is a success if *any* of the following is achieved:

1. **CosmoFalsify is published** (JOSS/A&C) and used/cited by others as a reproducible evaluation framework.  
2. **A reproducible no‑go result** is published: either as a theorem with collaborator or as a robust empirical bound + conjecture with clear conditions.  
3. **Measurement‑model dependence is quantified** and either:
   - shown negligible (strengthening standard inference), or  
   - shown capable of generating a diagnostic “tension fingerprint” (new inference axis).  
4. **ε‑space cartography** becomes a widely usable reference for precision constraints on universal scaling departures.

DE/DM unification and QFT/QG bridging remain *optional stretch goals* gated by perturbations and by measurement‑model results.

---


### 7.1 Contingency plan (make null results first‑class)

Because the project’s goal is *epistemic value*, not “being right”, we explicitly define what happens when the answer is “no”:

- **If Paper‑1 confirms a no‑go (strongly):**  
  - publish it as the main physics result (negative results are results),  
  - tighten and generalize the stated conditions,  
  - pivot drift‑sign work from “find a viable corner” to “map the boundary and its assumptions”.

- **If Paper‑2 finds measurement‑model effects are negligible under realistic ε bounds:**  
  - write Paper‑2 as a *null sensitivity* result that strengthens standard inference,  
  - keep measurement‑model code as reusable infrastructure,  
  - treat “tension explanations via metrology” as falsified for the tested model class.

- **If no external collaborators join after Paper‑4:**  
  - treat that as an input to scope, not a failure: proceed with solo‑feasible papers (Paper‑3, Tier‑1 Paper‑1),  
  - keep the collaboration pitch narrowly software/methodology.

- **If perturbations (Phase‑4C) kill a theory extension:**  
  - document and archive it as a negative result with reproducible stability artifacts,  
  - do not downgrade the evidence standard to “keep the story alive”.

This contingency plan is designed to prevent sunk‑cost escalation and to keep the project publishable under conservative standards.


## 8) Immediate next actions (1–2 week checklist)

1. Draft `docs/REVIEW_START_HERE.md` and `docs/VERIFICATION_MATRIX.md`.  
2. Draft `docs/FRAMES_UNITS_INVARIANTS.md` (keep it short and explicit).  
3. Draft `docs/PRIOR_ART_MAP.md` (rough v0 beats none).  
4. Draft `docs/DATA_LICENSES_AND_SOURCES.md` and `docs/DATASET_ONBOARDING_POLICY.md`.  
5. Draft `docs/DM_DECISION_MEMO.md` (even if DM is “not claimed yet”, lock the interpretation and tests).  
6. Extract a **minimal reproducible CosmoFalsify demo** (toy model + toy dataset + deterministic artifacts).  
7. Decide Paper‑4 venue (JOSS vs A&C) and implement submission‑required packaging items.  
8. Start Tier‑1 Paper‑1 outline with explicit conditions and scope.  
9. Define the first measurement model parameterization `M(θ_M)` (tiny) and implement finite‑difference sensitivity checks.
10. Decide **v11 cutover mode** (soft tag‑only vs full directory rename). Default: **full rename**.
11. Execute v11 cutover (atomic): move ` → `, update paths, run full gates, produce reviewer snapshot.
12. Add a **stability sanity MVP** report (ghost/gradient) for surrogate action models used in Phase‑3/Phase‑4 claims; fail‑closed for any physics‑claim use.


---

## 9) Indicative timeline and resource envelope (solo‑realistic)

This is intentionally coarse. The goal is not precision scheduling; it is to prevent “infinite roadmap drift”.

### 9.1 Timeline (order matters more than dates)

1. **Now → +2 weeks:** 4A.1–4A.8 (review UX + verification matrix + invariants + prior‑art map + data/licensing + onboarding policy).  
2. **Next:** 4A.9–4A.10 (CosmoFalsify packaging + Paper‑4 submission).  
3. **Cutover:** apply the v11 transition (see §11) so the public-facing Phase‑4 track is coherent.
4. **Then:** Paper‑3 (ε‑space cartography) as the first physics‑adjacent, still solo‑feasible paper.
5. **Parallel (opportunistic):** Tier‑1 Paper‑1 outline and stabilization of the “structural no‑go” statement.
6. **After first external publication:** recruit collaborators for Tier‑2 Paper‑1 and Paper‑2.

### 9.2 Compute assumptions

- keep “review‑grade” runs runnable on a single workstation (hours, not weeks)  
- reserve HPC/cluster work only for optional later MCMC or high‑resolution scans  
- always provide a toy/deterministic mode for reviewers.

### 9.3 Time budget sanity

If the project has <10 hours/week sustained attention, reduce scope to:
- Paper‑4 + Paper‑3 only, plus minimal maintenance.

---

## 10) Decision gates (prevent sunk‑cost escalation)

These are “stop/go/redirect” gates that keep the project honest.

### Gate‑A: Paper‑4 publishability
If Paper‑4 cannot be made reviewer‑smooth (install → run example → deterministic artifacts), then:
- stop adding new physics features  
- invest in packaging + docs until this is true.

### Gate‑B: Perturbations stability for any new theory extension
If an extension fails the 4C stability checklist:
- it is **not** used for Paper‑2/DE/DM claims  
- it is documented as a negative result and parked.

### Gate‑C: Measurement‑model effect size
If early 4B sensitivity kernels indicate negligible impact at realistic ε bounds:
- Paper‑2 becomes a “null result paper” (still valuable)  
- the project pivots away from “tensions explained by metrology” and focuses on methodology outputs.

### Gate‑D: Collaboration availability
If no collaborator appears within ~6 months after Paper‑4:
- publish Tier‑1 Paper‑1 as “empirical no‑go + conjecture” without over‑claiming theorem status  
- do not wait indefinitely for the perfect coauthor.

---


## 11) Versioning and v11 transition policy

### 11.1 Why v11
Phase‑4 is a **strategic pivot**: from “find a new late‑time cosmology history” toward **methodology + measurement‑model sensitivity + reproducible falsification tooling (CosmoFalsify)**.
A major version bump communicates:
- a clean separation between **Phase‑3 (action‑scaffold + low‑z scan + dossier tooling)** and **Phase‑4 (papers + measurement‑model space + falsification engine)**;
- a new “public face” for Paper‑4 and collaboration outreach;
- reduced cognitive load for reviewers (“v11 = the new track”).

### 11.2 Two compatible cutover modes
**Mode A — Soft v11 (tag only):** keep the working directory `v10.1.1/`, but begin tagging releases as `v11.0.0‑phase4‑m###`.
- Pros: minimal churn.
- Cons: confusing to outsiders (repo says v11, paths say v11.0.0).

**Mode B — Full v11 (preferred):** rename the working directory to `` and update all repo references.
- Pros: coherent external story; reduces “why is everything under v11.0.0?” reviewer friction.
- Cons: one‑time mechanical refactor touching many files.

### 11.3 Preferred plan
Proceed with **Mode B** as a single atomic milestone (M140 or equivalent):
1. Move `v10.1.1/ → ` (no duplication).
2. Update **all** hardcoded paths in:
   - docs, runbooks, onboarding, scripts, tests, and CI workflow;
   - snapshot tooling profiles + inventory defaults;
   - any schema references that include the old root.
3. Run full quality gates.
4. Generate a deterministic reviewer snapshot (`make_repo_snapshot.py --profile review_with_data`) and attach the preflight + unittest summary.

### 11.4 Versioning discipline
- Keep existing tags/releases intact (Phase‑2/Phase‑3 history remains in Git).
- Start v11 tags at the first Phase‑4 cutover commit.
- Keep Phase‑4 milestone numbering monotonic (M139 → …) even across the major version bump.

### 11.5 Acceptance criteria for v11 cutover
- `docs_claims_lint.py`, `audit_repo_footprint.py`, and full unit tests pass from a clean checkout.
- “Start here” instructions work verbatim with the new paths.
- Snapshot tooling produces identical file manifests across two runs.
- No absolute paths appear in generated job scripts / packs.


End of Roadmap v2.5.1.
