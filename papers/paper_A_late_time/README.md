# Paper A — Late-Time Empirical Framework

**Working title:** *GSC: A Scale-Covariant Measurement-Theoretic Framework for Late-Time Cosmology.*

**Tier scope:** T1 + T2 (kinematic frame + phenomenological σ(t) fit).

**Length target:** ≈ 30 pages.

**Venue target:** Phys. Rev. D / JCAP.

**Status:** Drafting from existing late-time release artifacts.

## Scope

Paper A presents the freeze-frame measurement model and the canonical late-time fit results, without depending on any specific physical mechanism for σ(t) (which is the scope of Paper B) or any extension module (Paper C). It is the empirical core of the framework.

### Sections

1. Introduction and lineage statement (Wetterich 2013, asymptotic safety tradition);
2. The freeze-frame measurement model;
3. Geometric-lock consistency conditions;
4. σ(t) phenomenological ansätze (power-law, transition, RG-flow profile);
5. Late-time data: Pantheon+SH0ES, DESI BAO, fσ8;
6. Joint-fit results and uncertainty propagation;
7. Pre-registered prediction P1 (BAO standard-ruler shift in DESI Year-3);
8. Comparison with ΛCDM and alternative scale-covariant frameworks;
9. Discussion of frame-equivalence critique;
10. Conclusions and outlook.

## Key sources

- Framework: [THEORY.md, §2](../../THEORY.md)
- Measurement model: [docs/measurement_model.md](../../docs/measurement_model.md)
- Pipelines: [pipelines/](../../pipelines/) — the registered computations for P1 and P8, verified by `bash pipelines/predictions_compute_all.sh`
- Data: [data/](../../data/) and the `observed_data.json` file of each register entry
- Pre-registered prediction: [predictions/P01_bao_ruler_shift/](../../predictions/P01_bao_ruler_shift/)

## Build instructions

The paper is Markdown ([main.md](main.md)); there is no build step yet.

## Outstanding work

- [ ] Re-run all late-time fits with current parameter ranges and freeze a v12 reference manifest.
- [ ] Compute and pre-register P1 (BAO ruler shift) — M201.
- [ ] Draft frame-equivalence critique response (tightly).
- [ ] Cross-check against Wetterich's published late-time predictions.
- [ ] Prepare LaTeX template (port from existing v11 paper assets).
