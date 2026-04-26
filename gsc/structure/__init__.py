"""Structure-formation bridge diagnostics (approximation-first, stdlib-only)."""

from .growth_factor import (
    fsigma8_from_D_f,
    growth_observables_from_solution,
    solve_growth_D_f,
    solve_growth_ln_a,
)
from .power_spectrum_linear import (
    DEFAULT_K_PIVOT_MPC,
    M_kz_from_curvature,
    P_mm_h_Mpch3,
    P_mm_phys_Mpc3,
    fsigma8,
    linear_matter_pk,
    primordial_P_R,
    primordial_delta2_R,
    primordial_power_law,
    sigma8_0_from_As,
    sigma8_z,
    sigma_R,
    tophat_window,
)
from .rsd_fsigma8_data import chi2_diag, diag_weights, load_fsigma8_csv, profile_scale_chi2_diag
from .rsd_overlay import rsd_overlay_for_e2_record
from .transfer_bbks import sample_k_grid, shape_parameter_sugiyama, transfer_bbks, transfer_bbks_many
from .transfer_eh98 import transfer_eh98_nowiggle

__all__ = [
    "shape_parameter_sugiyama",
    "transfer_bbks",
    "transfer_bbks_many",
    "transfer_eh98_nowiggle",
    "sample_k_grid",
    "solve_growth_ln_a",
    "growth_observables_from_solution",
    "solve_growth_D_f",
    "fsigma8_from_D_f",
    "primordial_delta2_R",
    "primordial_power_law",
    "primordial_P_R",
    "M_kz_from_curvature",
    "P_mm_phys_Mpc3",
    "P_mm_h_Mpch3",
    "linear_matter_pk",
    "tophat_window",
    "sigma_R",
    "sigma8_0_from_As",
    "sigma8_z",
    "fsigma8",
    "DEFAULT_K_PIVOT_MPC",
    "load_fsigma8_csv",
    "diag_weights",
    "chi2_diag",
    "profile_scale_chi2_diag",
    "rsd_overlay_for_e2_record",
]
