# Data

| File | Content | Source |
|---|---|---|
| `desi_dr2_bao.csv` | DESI DR2 BAO: D_V/r_d for BGS and correlated (D_M/r_d, D_H/r_d) pairs for six tracers | DESI DR2 Results II, arXiv:2503.14738 v3, Table IV (the combined LRG3+ELG1 bin, as in DESI's baseline). Used by `analyses/joint_fit.py`. |
| `desi_dr2_bao_dv_ap.csv` | DESI DR2 BAO in the other compression: D_V/r_d and the Alcock–Paczyński ratio D_M/D_H, with their correlation | Same table of arXiv:2503.14738 v3. Used by `analyses/timescape_fit.py`. |
| `planck2018_distance_priors.json` | Planck 2018 CMB distance priors (R, l_A, ω_b, n_s) with their correlation matrix | Chen, Huang & Wang, JCAP 02 (2019) 028, arXiv:1808.05724, Table 1 (flat ΛCDM, TT,TE,EE+lowE). Used by `analyses/joint_fit.py`. |
| `desi_dr1_bao_baseline.csv` | A compact DR1-era table of BAO distance ratios, used only by `analyses/w0wa_rd_shift_diagnostic.py` | Described at creation as public DESI DR1 BAO summary values (arXiv:2404.03000). See the discrepancies below. |
| `rc100_table3.csv` | RC100: redshift, baryonic mass, effective radius R_e, dark-matter fraction f_DM(R_e) and circular velocity V_c(R_e), each with its uncertainty, for 100 star-forming disks at z = 0.6–2.5 | Nestor Shachar et al., ApJ 944, 78 (2023), arXiv:2209.12199 v1, Table 3 (columns z, log M_baryon, R_e, f_DM, V_c). Used by `analyses/a0_evolution.py`. See the transcription note below. |

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

**Transcription of `rc100_table3.csv`.** The paper prints Table 3 as an image, and no machine-readable version was
found (none on VizieR), so the five columns were transcribed by hand from the arXiv version. Checks:

- An independent machine reading of the same images (the macOS Vision text recognizer) agrees on 499 of the 500
  values and 368 of the 400 uncertainties and disagrees on none. It missed one redshift (1.5, row 46), which lies
  between its neighbours as the table's ordering requires. The 32 uncertainties it could not read are printed as
  superscripts: 30 are V_c uncertainties, which follow the table's 20% pattern, and two are f_DM uncertainties,
  checked by eye.
- The statistics the paper quotes for the dark-matter fractions and sizes are reproduced by
  `analyses/a0_evolution.py`: median f_DM 0.38 and 0.27 for z = 0.6–1.2 and 1.2–2.5, spreads 0.23 and 0.18,
  shares below 0.28 of 33% and 54% ("roughly 33%" and "half"), median R_e 5.55 kpc ("5.5 kpc").
- The four columns agree with each other: V_bar² R_e / (G M_bar) lies between 0.44 and 0.76 for 80% of the
  galaxies. The one outlier, #83 (K20 ID5), is bulge-dominated with a velocity dispersion of 100 km/s.
- Two V_c uncertainties depart from the 20% pattern (#65: 313 ± 61; #96: 136 ± 26). Both are as printed.
- The paper's median baryonic surface density (10^8.7 M_⊙/kpc²) depends on a definition it does not spell out;
  simple definitions give 10^8.57 to 10^8.87 from this table.
