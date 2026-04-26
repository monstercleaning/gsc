# DESI BAO compact baseline (v11.0.0 / Phase-4 M156)

This folder contains a small, deterministic BAO block table for the Phase-4
Triangle-1 baseline leg diagnostic.

Files:
- `desi_dr1_bao_baseline.csv`: compact BAO ratio block table (`D_V/r_d`, `D_M/r_d`, `D_H/r_d`)
  used by `phase4_desi_bao_epsilon_or_rd_diagnostic.py`.

Scope:
- This is a compact inference bundle for deterministic diagnostics.
- It is not a full DESI likelihood package.

Roadmap wording policy:
- DR1 is used as baseline.
- DR2 BAO/cosmology products are treated as optional robustness checks when
  public and available in chosen likelihood tooling.
