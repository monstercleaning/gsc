# Frames, Units, and Invariants (Phase-4, current v11 series)

Introduced in M139; maintained through current Phase-4 milestones.

Purpose: separate definitional choices from empirically testable content.

## 1) Two layers that must not be conflated

1. **Frame/field redefinition layer**:
   mathematical reparameterizations of variables and fields.
2. **Measurement-model layer**:
   operational mapping from instrument-level observables to inferred
   cosmological parameters.

A frame redefinition alone is not evidence of new empirical content.
A measurement-model change can change inferred parameter values and therefore is
an explicit part of the tested hypothesis space.

## 2) Invariant observables used in this repository

- Redshift-drift observable in the Sandage-Loeb form
- Dimensionless BAO ratios (for example `D_M/r_d`, `D_H/r_d`, `D_V/r_d`)
- Distance-prior vector components used in compressed-CMB bridge diagnostics
- Structure diagnostics built from dimensionless growth combinations (for
  example `fσ8`)

These are the quantities compared in diagnostics and verification tooling.

## 3) Definitional or convention-dependent quantities

Examples include unit choices, parameter naming conventions, and coordinate
representations. They are tracked for reproducibility, but they are not treated
as stand-alone evidence.

## 4) Non-trivial prediction standard

A result is considered non-trivial only if it appears in an invariant
observable channel and survives deterministic replay under the same input data
and processing chain.

## 5) Reviewer checklist

- Confirm that a claimed effect is attached to an invariant observable.
- Confirm that the same effect appears after deterministic rerun.
- Confirm that any measurement-model variation is explicitly declared and not
  presented as a frame-only argument.
