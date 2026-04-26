# External Reviewer Feedback Integration

This note records external-feedback themes and maps them to concrete Phase-2
artifacts using claim-safe wording.

## External expert feedback (Feb 2026)

External feedback emphasized four pressure points: early-universe/CMB bridge
quality, sigma-field origin framing, structure-formation coverage, and
deterministic engineering/reproducibility.

## Feedback summary

- **Early Universe / CMB bridge:** keep compressed CMB priors and shift
  parameters operationally reproducible, and report risk clearly when closure
  pressure is high.
- **Sigma origin / FRG-AS:** keep wording explicit that FRG/AS is conceptual
  motivation only in the current framework, while documenting ansatz assumptions around
  `k(sigma)` and exploratory `k_*` diagnostics.
- **Structure formation / DM:** keep linear-theory growth and RSD overlays
  reproducible, but avoid non-linear and dark-matter-resolution claims.
- **Engineering / pipeline:** provide deterministic run/build/share paths, and
  avoid ad-hoc raw-worktree zip handoffs.

We do not compute full CMB anisotropy spectra in canonical the current framework scope; the
current bridge uses compressed CMB priors and compressed priors / shift
parameters as a diagnostic path, not a full spectra fit.

## Response / current status mapping

| Concern | What we have now | Where (docs/scripts) |
|---|---|---|
| Early-universe bridge quality | Deterministic Phase-2 E2 scan/merge/report/bundle workflow around compressed priors diagnostics | `docs/early_time_e2_status.md`, `docs/project_status_and_roadmap.md`, `scripts/phase2_e2_scan.py` |
| Sigma-field origin status | Sigma-origin status doc + FRG flow-table and Padé-fit diagnostics for externally provided tables; conceptual motivation only, ansatz-level, not derived | `docs/sigma_field_origin_status.md`, `docs/rg_asymptotic_safety_bridge.md`, `docs/rg_scale_identification.md`, `scripts/phase2_rg_flow_table_report.py`, `scripts/phase2_rg_pade_fit_report.py` |
| Structure formation / DM scope clarity | Linear-theory and approximate diagnostics (`T(k)`, growth, `fσ8`, RSD overlay/joint objective), plus explicit scope-boundary doc and paper snippet wiring | `docs/structure_formation_status.md`, `docs/perturbations_and_dm_scope.md`, `docs/reviewer_faq.md`, `scripts/phase2_sf_fsigma8_report.py`, `scripts/phase2_e2_scan.py`, `scripts/phase2_e2_make_paper_assets.py` |
| Planck spectra / perturbations readiness | Full Boltzmann TT/TE/EE pipeline is not implemented; deterministic export pack and deterministic results pack provide selected-candidate handoff plus packaging of external CLASS/CAMB outputs, and reviewer packs can optionally include both | `docs/perturbations_and_dm_scope.md`, `docs/project_status_and_roadmap.md`, `scripts/phase2_pt_boltzmann_export_pack.py`, `scripts/phase2_pt_boltzmann_results_pack.py`, `scripts/phase2_e2_make_reviewer_pack.py` |
| Deterministic reviewer handoff | Deterministic reviewer pack, share snapshot tooling, and bundle verify path | `docs/project_status_and_roadmap.md`, `scripts/phase2_e2_make_reviewer_pack.py`, `scripts/phase2_e2_verify_bundle.py`, `scripts/make_repo_snapshot.py` |

## Remaining gaps / next milestones

- **Implemented (current):** compressed-priors CMB bridge, sigma-origin status
  tooling, and linear-theory structure checks with RSD chi2 overlays.
- **Partial (current):** early-time closure diagnostics under tested families;
  linear-structure overlays are suitable for consistency pressure tests but
  remain approximation-first.
- **Future work (explicit):**
  - full CMB power spectra (`TT/TE/EE`) with a Boltzmann-class peak-level
    path;
  - perturbations beyond linear-growth approximations and non-linear structure
    formation;
  - dark-matter microphysics stance remains open;
- first-principles FRG derivation of `sigma(t)` and a justified `k(sigma)`
    map remain open research (conceptual motivation only in current scope).

Dark-matter stance in the current framework remains conservative: we do not claim dark matter
is solved or eliminated. Current structure checks are linear-theory,
approximate diagnostics.
