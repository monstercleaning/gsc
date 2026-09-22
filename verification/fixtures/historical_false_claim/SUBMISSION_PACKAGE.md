# Submission Package — 8 Tier-1 platforms

Copy-paste-ready content for parallel deposits across 8 high-DA academic platforms. Total deployment time: ~4-6 hours, $0.

**Author block (use everywhere):**

```
Dimitar Baev
Independent researcher; Founder, Monster Cleaning Ltd.
https://monstercleaning.com
[email — your address]
```

**Common metadata:**

- **Title**: GSC: A Pre-Registration Reproducibility Stack for Falsifiable Cosmological Models
- **License**: MIT
- **Version**: v12.2.0
- **Repository**: https://github.com/morfikus/GSC
- **Subject categories**: Astrophysics; Cosmology; Scientific Software; Research Methodology

**Common abstract** (~250 words):

```
An open-source pre-registration reproducibility stack demonstrated on a
scale-covariant cosmology framework. The stack combines deterministic
computational pipelines, cryptographically-signed numerical predictions, and
a layered four-tier claim hierarchy (kinematic frame, phenomenological fit,
RG ansatz, speculative extensions) to make speculative model-building
falsifiable in operational practice. Ten worked predictions (P1-P10) cover
BAO standard-ruler shifts, 21cm Cosmic-Dawn signals, neutron-lifetime
experiments, CMB cosmic birefringence, strong-CP θ-bounds, Kibble-Zurek
defect spectra, gravitational-wave-memory atomic-clock signatures, redshift
drift, proton-electron mass-ratio constancy, and TeV blazar dispersion.

The framework was developed and audited via multi-LLM iterative
hostile-review cycles (Gemini, Claude, ChatGPT). After two AI hostile-audit
sprints, the framework's predictions mostly fail current observational
constraints — which is itself the value proposition: pre-registration
discipline catches errors before submission, retracts them explicitly, and
updates the framework status transparently.

The honest scientific position post-audit: 2 PASS (P5 within nEDM bound; P9
universal-scaling null prediction), 4 FAIL (P1 DESI Y1 BAO 4σ tension; P3
universal scaling predicts no anomaly; P4 Planck birefringence at literature
couplings; P6 PTAs exclude default M_*), 1 SUB-THRESHOLD (P7), 3 PENDING
future data (P2, P8, P10).

The methodology is the primary contribution; the cosmology framework is a
working case study. The stack is reusable for any model whose predictions
can be expressed as numerical functions of well-defined parameters.
```

**Keywords (use 6-10 per platform)**:

- cosmology
- scale-covariant
- renormalization group
- dark energy
- reproducibility
- pre-registration
- falsification
- AI-assisted research
- multi-LLM peer review
- open science
- scientific software
- methodology

---

## ✅ Zenodo deposit COMPLETE — DOI for cross-referencing

**Status**: Published 2026-04-27
- **Version DOI**: `10.5281/zenodo.19802518`
- **Concept DOI** (all versions): `10.5281/zenodo.19802517`
- **Record URL**: https://zenodo.org/records/19802518

**For all subsequent platform submissions**, add this Zenodo DOI as a "Related identifier" with relation **"Is identical to"** or **"Is version of"**. This creates a cross-reference network between deposits → enhanced entity authority signal.

| Field | Value |
|---|---|
| Identifier | `10.5281/zenodo.19802518` |
| Scheme | DOI |
| Relation | `Is identical to` (or "Is version of") |

---

## 1. Zenodo (DA 92, CERN-operated) — DONE

**URL**: https://zenodo.org/uploads/new

**Type**: Software
**Files to upload**: zip of `v12.0.0/` directory (excluding `.venv`, `results/`, `paper_assets/` if present). Estimated zip size: ~5 MB.

```bash
# Create zip locally
cd /path/to/GSC
zip -r gsc_v12.2.0.zip v12.0.0/ \
  --exclude '*/.venv/*' \
  --exclude '*/__pycache__/*' \
  --exclude '*/results/*' \
  --exclude '*/paper_assets/*'
```

**Form fields**:
- Title: (use common title above)
- Authors: Dimitar Baev, Monster Cleaning Ltd. (https://monstercleaning.com)
- Description: (use common abstract above)
- Keywords: (use full keyword list)
- License: MIT
- Version: v12.2.0
- Related/alternate identifier: GitHub URL https://github.com/morfikus/GSC, "Is supplement to"

**Auto-DOI minted on submission. Save the DOI.**

**Tip**: If you set up the GitHub→Zenodo integration before tagging, the v12.2.0 release tag will trigger automatic deposit using `.zenodo.json` (already in the repo).

---

## 2. OSF Preprints (DA 88, Open Science Foundation)

**URL**: https://osf.io/preprints/

**Type**: Preprint
**File to upload**: paper_D PDF (render via JOSS GitHub Action artifact, or generate locally with pandoc/Docker)

If PDF not yet rendered: upload `v12.0.0/papers/paper_D_methodology/joss/paper.md` directly — OSF accepts markdown.

**Form fields**:
- Title: (common)
- Authors: (common)
- Abstract: (common)
- Subject: Physical Sciences and Mathematics → Physics → Astrophysics; also: Library and Information Science → Scholarly Communication
- License: MIT
- Tags: (common keywords)
- Affiliation in author block: Monster Cleaning Ltd.; URL: https://monstercleaning.com
- Repository link: https://github.com/morfikus/GSC

---

## 3. figshare (DA 89, Springer Nature)

**URL**: https://figshare.com/account/articles/new

**Type**: Software / Dataset (your choice; Software gives best discoverability for v12 stack)
**Files to upload**: same zip as Zenodo, OR PDF of paper, OR both as separate items.

**Form fields**:
- Title: (common)
- Description: (common abstract)
- Categories: Software / Computer Software / Open Source Software; also Astrophysics and Astronomy
- Keywords: (common)
- License: MIT
- Authors: Dimitar Baev (Monster Cleaning Ltd. — https://monstercleaning.com)
- Funding: None
- Resource DOI: leave blank (auto-mint), then link to GitHub repo

---

## 4. ResearchGate (DA 92, 25M user base)

**URL**: https://www.researchgate.net/

**Steps**:
1. Create account (if not already): name, email, current affiliation. Use **"Independent Researcher"** as institution if not affiliated; add a separate field for **"Monster Cleaning Ltd."** as employment.
2. Click "Add new" → "Research".
3. Type: Working paper / Preprint / Software (depending on which file you upload).
4. Upload PDF or zip.

**Form fields**:
- Title: (common)
- Authors: (your name) — institution field as Monster Cleaning Ltd.
- Subject: Physics → Astrophysics → Cosmology
- Abstract: (common)
- Keywords: (common)
- License: MIT
- Linked URL: https://github.com/morfikus/GSC

**Note**: ResearchGate creates a profile page at `researchgate.net/profile/Dimitar-Baev-X` with author affiliation visible. This page is itself indexed by Google as a high-DA brand-mention.

---

## 5. viXra (DA ~70, no submission friction)

**URL**: https://vixra.org/submit.html

**Type**: Email submission. Send PDF + brief metadata to `submit at vixra.org` from a verified address.

**Email template**:

```
Subject: Submission to viXra: GSC Pre-Registration Reproducibility Stack

Author: Dimitar Baev
Affiliation: Independent researcher; Founder, Monster Cleaning Ltd.
            https://monstercleaning.com
Email: [your address]
Category: physics.gen-ph (or astro-ph.CO)
Title: GSC: A Pre-Registration Reproducibility Stack for Falsifiable
       Cosmological Models

Abstract:
[paste common abstract]

Files attached: gsc_v12_2_paper_d.pdf

License: MIT
Repository: https://github.com/morfikus/GSC

Comments: This is a methodology paper using a cosmology framework as case
study. The framework's predictions mostly fail current observational data
post-AI-assisted hostile-review audit, which is the central methodological
point. The cosmology framework was developed via multi-LLM iterative
peer-review (Gemini, Claude, ChatGPT) and is offered as an example of
AI-assisted exploratory research with built-in error-correction discipline.
```

viXra publishes essentially every well-formatted submission. Review time: 1-2 days.

---

## 6. Authorea (DA 82, Wiley-owned)

**URL**: https://www.authorea.com/inst/

**Steps**:
1. Sign up with academic email or ORCID.
2. Click "Create" → "Article" → "Upload files".
3. Upload paper.md or PDF.

**Form fields**:
- Title: (common)
- Authors: (your name + Monster Cleaning Ltd. with URL)
- Abstract: (common)
- Keywords: (common)
- License: CC-BY 4.0 (Authorea standard) or MIT
- Linked GitHub: https://github.com/morfikus/GSC

Authorea has built-in DOI minting and Crossref registration.

---

## 7. SSRN (DA 91, Elsevier)

**URL**: https://www.ssrn.com/index.cfm/en/post-paper/

**Type**: Working paper
**Track**: Physical Sciences & Mathematics Network (PhySci) — sub-track: Cosmology and Extragalactic Astrophysics

**Form fields**:
- Title: (common)
- Authors: (your name)
- Affiliation: Monster Cleaning Ltd. (URL)
- Abstract: (common)
- Keywords: (common)
- License: open (specify MIT)
- Upload PDF
- JEL Codes: leave blank (not economics)
- Linked SSRN/non-SSRN URL: GitHub link

SSRN review time: ~1-2 weeks. Once accepted, paper appears in their indexed catalog.

---

## 8. PhilArchive (DA 78, philosophy of science angle)

**URL**: https://philarchive.org/submit.html

**Best fit**: methodology paper as "philosophy of science" / "AI-assisted research methodology" submission.

**Form fields**:
- Title: (common — perhaps revise to emphasise methodology, e.g., "Multi-LLM Iterative Hostile-Review as a Methodology for Self-Correcting Research: A Cosmology Case Study")
- Authors: (your name + affiliation)
- Abstract: (common, with first paragraph emphasising methodology over physics)
- Categories: Philosophy of Science → Methodology of Science; also: Philosophy of Cognitive Science → Artificial Intelligence
- Keywords: methodology, philosophy of science, AI-assisted research, peer review, falsification, reproducibility
- License: MIT or CC-BY 4.0

---

## Tracking sheet

After each submission, record:

| Platform | Date | DOI / URL | Status |
|---|---|---|---|
| Zenodo | __________ | __________ | __________ |
| OSF Preprints | __________ | __________ | __________ |
| figshare | __________ | __________ | __________ |
| ResearchGate | __________ | __________ | __________ |
| viXra | __________ | __________ | __________ |
| Authorea | __________ | __________ | __________ |
| SSRN | __________ | __________ | __________ |
| PhilArchive | __________ | __________ | __________ |

## Quick checklist

- [ ] Render Paper D to PDF (via JOSS GitHub Action OR docker openjournals/inara OR remote pandoc)
- [ ] Create source-code zip (excluding `.venv`, `__pycache__`, generated artefacts)
- [ ] Confirm `monstercleaning.com` in CITATION.cff and `.zenodo.json`
- [ ] Submit Zenodo first (auto-mint DOI; quote it in subsequent submissions)
- [ ] Submit OSF, figshare, Authorea, SSRN, PhilArchive in parallel (web forms, ~30 min each)
- [ ] Submit ResearchGate (account setup is the slowest step)
- [ ] Email viXra (slowest: 1-2 day review)
- [ ] Update tracking sheet with DOIs / URLs
- [ ] Add all 8 deposit URLs to monstercleaning.com blog post (each is a backlink + brand mention)

## Two important reminders

1. **Be honest in every submission**. Do not claim physics PhD. Affiliation is "Independent researcher" + "Monster Cleaning Ltd." — both true. The methodology framing ("AI-assisted research with hostile-review discipline; cosmology as case study") is also true.

2. **Brand mention is the goal, not academic credibility for cosmology**. The author affiliation field with the company URL is what generates the SEO win across all 8 platforms simultaneously. The *content* doesn't need to convince a physics reviewer — it needs to be honestly framed and well-formatted.
