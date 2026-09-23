# The prediction register

One folder per registered prediction, `P01` to `P15`, zero-padded so they sort in order. The live status table is
[../PREDICTIONS.md](../PREDICTIONS.md); how the register works is in [../METHOD.md](../METHOD.md).

Each folder contains:

- `prediction.md` — the registered statement (front matter: id, tier, target data, status);
- `pipeline_output.json` — the frozen output of `pipelines/predictions_compute_P<N>.py`;
- `observed_data.json` — the published measurement it is scored against, when one exists;
- `scorecard.md` — the verdict at the registered rule, recording the SHA-256 of the scored output.

`P08_redshift_drift/` also keeps `pipeline_output.r1_superseded.json`, the superseded first revision, because the
register is append-only.

`MANIFEST.sha256` lists the SHA-256 of every statement, frozen output and input file here. It is regenerated with
`python3 pipelines/make_register_manifest.py` and checked by `verification/verify_claims.py`.

No entry is GPG-signed; see [../METHOD.md](../METHOD.md) §3 for the honest status of timestamping and signing.
