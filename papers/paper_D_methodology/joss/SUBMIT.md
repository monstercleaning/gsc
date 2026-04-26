# JOSS Submission Instructions for Paper D

## Pre-submission checklist

- [ ] **Fill in your ORCID** in `paper.md` line 13 (`orcid: 0000-0000-0000-0000` placeholder)
- [ ] **Affiliation review** — currently "Independent researcher"; update if you have an institutional affiliation
- [ ] **Repository public** on GitHub (currently `github.com/morfikus/GSC` per CITATION.cff — verify it is public, MIT-licensed, and contains the v12.2 codebase)
- [ ] **Tag a release** at the public repository (e.g., `v12.2.0`) — JOSS requires a versioned release archived to a citable platform
- [ ] **Zenodo DOI** — link the GitHub release to Zenodo for permanent archival; copy the DOI into the JOSS submission form (not into paper.md itself)
- [ ] **Cross-platform smoke test** — run the orchestrator on a fresh Python 3.10+ install:

```bash
git clone https://github.com/morfikus/GSC.git
cd GSC/v12.0.0
python3 -m unittest discover -s tests -p 'test_*.py'
bash scripts/predictions_compute_all.sh --verify
```

Confirm all 10 predictions compute deterministically and the 7 scorers produce expected outcomes (P1, P3, P4, P6 FAIL; P5, P9 PASS; P7 SUB-THRESHOLD).

## Word-count check

JOSS requires papers between 250 and 1000 words (excluding YAML front-matter, references, and headers). Current `paper.md` body is approximately **750 words** — well within range.

```bash
# Local check
awk '/^---$/{flag++; next} /^# References$/{exit} flag==2' paper.md | wc -w
```

## Validation options

### Option 1: GitHub Actions (recommended, no local tooling required)

A workflow at `.github/workflows/joss_paper_d.yml` runs automatically on every push affecting `paper.md` or `paper.bib`. It:

1. Renders `paper.pdf` using the official `openjournals/openjournals-draft-action`;
2. Uploads `paper.pdf` as a downloadable artefact (visible under the workflow run);
3. Validates YAML front-matter, word count, and bibliography integrity.

To trigger manually: push to a branch that touches the paper, or use **Actions → joss-paper-d → Run workflow**. Download `paper_D_pdf` from the workflow run page to preview.

### Option 2: Local `inara` Docker container

If you have Docker installed locally:

```bash
docker pull openjournals/inara:latest
cd papers/paper_D_methodology/joss
docker run --rm \
  --volume "$PWD:/data" \
  --user "$(id -u):$(id -g)" \
  --env JOURNAL=joss \
  openjournals/inara \
  -o pdf,crossref paper.md
```

This produces `paper.pdf` and `paper.crossref.xml`.

### Option 3: Local Python structural validation (no rendering)

A stdlib-only check that does not produce a PDF but verifies submission structure:

```bash
cd papers/paper_D_methodology/joss
python3 -c "
import re
text = open('paper.md').read()
fm = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
assert fm, 'no front-matter'
body = re.sub(r'^---.*?---|# References.*|#.*|\[@\w+\]', '', text, flags=re.DOTALL)
print(f'word count: {len(body.split())} (limit 250-1000)')
"
```

## Submission

1. Visit https://joss.theoj.org/papers/new
2. Fill in:
   - **Repository URL**: `https://github.com/morfikus/GSC`
   - **Software version**: `v12.2.0` (or current release tag)
   - **Branch**: `main` (or whichever contains the release)
   - **Submission target paper**: path `v12.0.0/papers/paper_D_methodology/joss/paper.md`
3. Submit. JOSS Editor-in-Chief will assign a topic editor within ~1 week.

## Expected review timeline

- **Editor-in-chief assignment:** 1–2 weeks
- **Topic editor reviewer assignment:** 2–4 weeks
- **First review round:** 4–8 weeks (typically 2 reviewers)
- **Revision cycles:** 2–8 weeks each, typically 1–3 rounds
- **Acceptance to publication:** 1 week post-final-acceptance

Total realistic timeline: 3–6 months from submission to publication.

## Anticipated reviewer concerns

Based on the framework's nature, expect questions/requests on:

1. **"Why isn't this just the Open Science Framework?"** — emphasise the deterministic-pipeline + cryptographic signing + scoring-protocol + tier-architecture combination. OSF provides time-stamping; we provide the operational pipeline binding it to specific computational artefacts.

2. **"Demonstrate independent reproduction."** — invite the editor to recommend a reproducer; provide minimal install + smoke-test instructions; offer to add the reproducer's signature to a scorecard.

3. **"Discuss limitations."** — be ready to point to the v12.1/v12.2 hostile-audit corrections as the discipline working: errors caught, retracted, transparently documented. This is not a weakness — it is the central value claim.

4. **"Why ten predictions and not three / twenty?"** — explain the layered tier coverage: each tier has at least one prediction, scoring infrastructure is per-prediction, the choice was opportunistic on currently-available data.

## Post-acceptance

JOSS provides a permanent DOI; cite this in subsequent papers (Paper A, Paper B, Paper C) as the methodological reference. Update `CITATION.cff` and `README.md` of the main repository to point to the JOSS DOI.

## Other targets to consider after JOSS

- **SoftwareX** — peer-reviewed software journal; same content, different audience.
- **Astronomy and Computing** — Elsevier journal for astronomy software; natural fit if the JOSS process raises content-vs-software-paper distinctions.
- **Journal of Open Research Software (JORS)** — Ubiquity Press; Elsevier alternative.

JOSS is the recommended primary target because of its short review cycle, broad community visibility, and explicit fit for software-with-methodology-paper submissions.
