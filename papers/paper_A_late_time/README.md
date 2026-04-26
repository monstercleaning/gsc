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

- Framework: [GSC_Framework.md §1, §2](../../GSC_Framework.md)
- Measurement model: [docs/measurement_model.md](../../docs/measurement_model.md)
- Pipeline: [scripts/reproduce_late_time.sh](../../scripts/) (renamed from v11 reproduce_v10_1_late_time.sh)
- Data: [data/sn/pantheon_plus_shoes/](../../data/sn/pantheon_plus_shoes/), [data/bao/](../../data/bao/)
- Pre-registered prediction: [predictions_register/P1_bao_ruler_shift/](../../predictions_register/P1_bao_ruler_shift/)

## Build instructions

When ready to compile:

```bash
bash ../../scripts/build_paper.sh paper_A
```

(target script to be implemented; currently a placeholder).

## Outstanding work

- [ ] Re-run all late-time fits with current parameter ranges and freeze a v12 reference manifest.
- [ ] Compute and pre-register P1 (BAO ruler shift) — M201.
- [ ] Draft frame-equivalence critique response (tightly).
- [ ] Cross-check against Wetterich's published late-time predictions.
- [ ] Prepare LaTeX template (port from existing v11 paper assets).
