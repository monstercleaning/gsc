# Data

| File | Content | Source |
|---|---|---|
| `desi_dr2_bao.csv` | DESI DR2 BAO: D_V/r_d for BGS and correlated (D_M/r_d, D_H/r_d) pairs for six tracers | DESI DR2 Results II, arXiv:2503.14738 v3, Table IV (the combined LRG3+ELG1 bin, as in DESI's baseline). Used by `analyses/joint_fit.py`. |
| `planck2018_distance_priors.json` | Planck 2018 CMB distance priors (R, l_A, ω_b, n_s) with their correlation matrix | Chen, Huang & Wang, JCAP 02 (2019) 028, arXiv:1808.05724, Table 1 (flat ΛCDM, TT,TE,EE+lowE). Used by `analyses/joint_fit.py`. |
| `desi_dr1_bao_baseline.csv` | A compact DR1-era table of BAO distance ratios, used only by `analyses/w0wa_rd_shift_diagnostic.py` | Described at creation as public DESI DR1 BAO summary values (arXiv:2404.03000). See the discrepancies below. |

**Known discrepancies in `desi_dr1_bao_baseline.csv`** (checked against DESI 2024 III, arXiv:2404.03000, at the 20.1
review; the file is left unchanged because an existing diagnostic's recorded output depends on it):

- BGS: σ(D_V/r_d) is 0.123 here and 0.15 in the paper.
- The D_M–D_H correlation is −0.39 here and −0.445 in the paper for LRG1, and +0.15 here and −0.389 in the paper
  for the z = 0.93 bin.
- The paper gives the QSO bin only as D_V/r_d = 26.07 ± 0.67; the D_M/r_d, D_H/r_d pair listed here does not
  appear in it.
- The LRG2 (z = 0.71) and ELG2 (z = 1.32) bins are missing.
- The Lyα row comes from the companion paper (arXiv:2404.03001) and was not re-checked.

New analyses use `desi_dr2_bao.csv`. The prediction pipelines themselves read only the `observed_data.json` file inside
each register entry, where every number is quoted with its publication.
