# JOSS Submission Instructions for Paper D

## Pre-submission checklist

- [x] **Fill in your ORCID** in `paper.md` — done: `0009-0009-7812-9203`
- [x] **Affiliation review** — done: "Independent researcher; Founder, Monster Cleaning Ltd."
- [x] **Repository public** on GitHub — verified 2026-09-22: `github.com/monstercleaning/gsc` clones anonymously, carries the MIT licence, and its root is this package
- [ ] **Tag a release** at the public repository (e.g., `v20.0.0`) — JOSS requires a versioned release archived to a citable platform
- [ ] **Zenodo DOI** — link the GitHub release to Zenodo for permanent archival; copy the DOI into the JOSS submission form (not into paper.md itself)
- [ ] **Cross-platform smoke test** — run the four checks on a fresh Python 3.9+ install:

```bash
git clone https://github.com/monstercleaning/gsc.git
cd gsc
python3 -m unittest discover -s tests
python3 verification/verify_claims.py --include-slow
python3 verification/retro_test.py
bash pipelines/predictions_compute_all.sh --verify
```

Confirm that all thirteen registered predictions reproduce their frozen outputs deterministically and that the nine scorers give the recorded verdicts (P1, P4, P5, P9, P11, P13 PASS; P3, P6 FAIL; P7 SUB-THRESHOLD).

## Word-count check

JOSS requires papers between 250 and 1000 words (excluding YAML front-matter, references, and headers). The current `paper.md` body is about **1,700 words** by the check below — **over the limit**. It grew past 1,000 when the honest-limitations section and the later corrections were added. Cut it below 1,000 before submitting; the audit-history section, which Paper E covers in full, is the natural candidate. The `joss-paper-d` workflow warns while the count exceeds 1,000.

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

### Option 3: Local preprint render (no DRAFT watermark)

The preprint deposited on Zenodo and figshare is built by a standard-library renderer that takes the citations and
the reference list from `paper.bib` (an unknown citation key is an error). It needs xelatex:

```bash
python3 papers/paper_D_methodology/joss/render_preprint.py --pdf
```

This writes `paper.tex` and `paper.pdf` next to `paper.md` (both ignored by git).

### Option 4: Local Python structural validation (no rendering)

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
   - **Repository URL**: `https://github.com/monstercleaning/gsc`
   - **Software version**: `v20.0.0` (or current release tag)
   - **Branch**: `main` (or whichever contains the release)
   - **Submission target paper**: path `papers/paper_D_methodology/joss/paper.md`
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

1. **"Why isn't this just the Open Science Framework?"** — emphasise the deterministic-pipeline + content-hashed register + fixed-in-advance scoring-protocol + tier-architecture combination (do **not** claim cryptographic signing: the GPG step is specified in the protocol but was never executed — see CHANGELOG.md). OSF provides time-stamping; we provide the operational pipeline binding it to specific computational artefacts.

2. **"Demonstrate independent reproduction."** — invite the editor to recommend a reproducer; provide minimal install + smoke-test instructions; offer to record the independent reproduction (platform, commit, result) in the repository.

3. **"Discuss limitations."** — be ready to point to the recorded corrections (CHANGELOG.md) as the discipline working: the retracted anomaly explanation, the withdrawn signing claim, and the withdrawn redshift-drift difference — errors caught, retracted, transparently documented. This is not a weakness — it is the central value claim.

4. **"Why thirteen predictions and not three / twenty?"** — explain the layered tier coverage: each tier has at least one prediction, four are exact nulls guarding the framework's core, scoring infrastructure is per-prediction, and the choice was opportunistic on currently-available data.

## Post-acceptance

JOSS provides a permanent DOI; cite this in subsequent papers (Paper A, Paper B, Paper C) as the methodological reference. Update `CITATION.cff` and `README.md` of the main repository to point to the JOSS DOI.

## Other targets to consider after JOSS

- **SoftwareX** — peer-reviewed software journal; same content, different audience.
- **Astronomy and Computing** — Elsevier journal for astronomy software; natural fit if the JOSS process raises content-vs-software-paper distinctions.
- **Journal of Open Research Software (JORS)** — Ubiquity Press; Elsevier alternative.

JOSS is the recommended primary target because of its short review cycle, broad community visibility, and explicit fit for software-with-methodology-paper submissions.
