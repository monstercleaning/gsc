# Pre-Registered Predictions

This directory holds the append-only register of pre-registered numerical predictions made by the GSC framework. See [docs/pre_registration.md](../docs/pre_registration.md) for the methodology.

## Structure

```
predictions_register/
├── README.md                     # This file
├── P1_bao_ruler_shift/           # BAO standard-ruler shift in DESI Year-3
├── P2_21cm_cosmic_dawn/          # 21cm signal at z ~ 15-25
├── P3_neutron_lifetime/          # Beam-trap discrepancy
├── P4_cmb_birefringence/         # σ-induced CMB rotation
├── P5_strong_cp_bound/           # nEDM / θ-evolution
├── P6_kz_defect_spectrum/        # Kibble-Zurek string-network GWs
├── P7_gw_memory_clocks/          # Atomic-clock shifts post-merger
└── P8_redshift_drift/            # ELT/ANDES (supporting)
```

Each prediction directory contains:

- `prediction.md` — the prediction statement, tier label, ansatz and parameters, pipeline reference, target data, scoring algorithm, signature, timestamp.
- `pipeline_output.json` — the deterministic output of the prediction pipeline at registration time, with its SHA-256 hash.
- `scorecard.md` — generated when the target observational data are released.

## Status

All eight prediction directories are scaffolded but **none is yet signed**. Implementation milestones:

- **M201** (target: 2 weeks): P1 (BAO ruler shift) — pipeline implementation, prediction signed.
- **M202** (target: 3 months): P2 (21cm Cosmic Dawn) — module implementation, prediction signed.
- **M203** (target: 1 month): P3 (neutron lifetime) — σ-derivative computation, prediction signed.
- **M204+**: P4–P8 implementations and signatures.

## Signing protocol

A signed prediction is one whose `prediction.md` carries:

- Author cryptographic signature (GPG or equivalent);
- Repository commit SHA at signing time;
- ISO-8601 timestamp (UTC);
- SHA-256 hash of the corresponding `pipeline_output.json`.

Once signed, a prediction cannot be modified. Errors discovered post-signature are recorded as new predictions with explicit reference to the superseded entry.

## Scoring protocol

When target observational data are released:

1. The scoring pipeline (`scripts/predictions_score.py PNN`) loads the pre-registered prediction and the new data;
2. It runs the registered scoring algorithm;
3. It generates `scorecard.md` with pass/fail at the registered confidence level;
4. The scorecard is appended to the register (it does not modify the original prediction);
5. Pass/fail outcomes drive tier/module promotion or demotion in the next framework version.

## Independent reproduction

Independent reproducers are encouraged to:

- Verify the pre-registration hash;
- Re-run the prediction pipeline and confirm the output matches;
- Re-run the scoring pipeline against the released data;
- Add their signature to the scorecard.

This is the operational mechanism by which the framework's predictions become a community asset rather than the assertion of a single research group.
