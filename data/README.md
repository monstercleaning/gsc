# Data

| File | Content | Source |
|---|---|---|
| `desi_dr1_bao_baseline.csv` | DESI DR1 BAO distance ratios (D_V/r_d, D_M/r_d, D_H/r_d) per tracer, with uncertainties and D_M–D_H correlations | Public DESI DR1 BAO summary values (DESI Collaboration 2024, arXiv:2404.03000; https://data.desi.lbl.gov/doc/releases/dr1/). A compact table for deterministic diagnostics, not a DESI likelihood. |

The prediction pipelines themselves read only the `observed_data.json` file inside each register entry, where
every number is quoted with its publication.
