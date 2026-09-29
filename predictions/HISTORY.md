# Register history: outputs changed after registration

The register is meant to be append-only: a registered output is never edited, and a correction becomes a new
revision. That rule was not kept once. This page records the exception, reconstructed from the public git history
(github.com/monstercleaning/gsc) during the v20.2 external review.

## The one in-place change

Entries P1–P10 were registered in v12.2 (27 April 2026, commit `6cf7ee7`). In v12.5 (27 July 2026, commit
`c5c8030`, "retreat to the surviving region") the canonical exponent p was lowered from 1.0×10⁻³ to 6.0×10⁻⁴,
chosen from already-public data (`gsc/canonical_params.py`), and the p-dependent outputs were regenerated in place.
Every changed field follows from that change of p. The commit and its changelog entry disclosed it, but the entries
were overwritten instead of revised.

The v12.2 outputs are now kept beside the current ones as `pipeline_output.v12_2_superseded.json`, byte-identical to
the git blobs of commit `6cf7ee7`:

| Entry | What changed | Verdict at registration (v12.2 scorecard) | Verdict now |
|---|---|---|---|
| P1 | p 1.0×10⁻³ → 6.0×10⁻⁴; Δr_d/r_d +0.695% → +0.417% | FAIL, z = +3.93 (fails the registered \|z\| < 3 too) | PASS, labelled retrodictive |
| P2 | p; the whole brightness-temperature profile | awaiting data | awaiting data |
| P4 | p; β 0.0015° → 0.0009° | FAIL at a 2σ threshold the scorer had drifted to; z = −2.49 passes the registered \|z\| < 3 | PASS |
| P5 | p; the θ_eff trajectory | PASS | PASS |
| P8 | p; the drift table (then revision r2 in v12.7, with r1 kept as `pipeline_output.r1_superseded.json`) | awaiting data | awaiting data |
| P9 | p; the σ trajectory (the prediction itself, μ̇/μ = 0, did not change) | PASS | PASS |

In the same commit the P1, P3 and P4 scorers were set back from 2σ to the registered |z| < 3. That was a
correction toward the registered rule, and it alone turns P4's FAIL into PASS. P1 is different: at the registered p
it fails even at |z| < 3, and it passes only because p was lowered using the data it is scored against. Its PASS is
therefore a retrodictive check of a revised parameter, not a success of the registered prediction.

## Since then

No registered output has been edited in place since 27 July 2026. The P8 revision (v12.7, 22 September 2026) kept
its first revision, and entries P11–P15 were registered later. The SHA-256 manifest (`MANIFEST.sha256`) and the
claim checker now fail on any change to a registered file that the manifest does not record.
