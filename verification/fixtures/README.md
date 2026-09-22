# Provenance of `historical_false_claim/`

These files are **verbatim historical text**, kept only as a negative control
for the claim detector (`verification/retro_test.py`). They are not part of the
living documentation and are intentionally never corrected.

- Source: the project's v12.2 release, git commit `a42d294`, package directory
  at that time. Every file whose prose asserted that the prediction register was
  "cryptographically signed" is included (18 assertion sites in 8 files), plus
  the ten register statements of that release, whose empty `signed_by` fields
  prove the assertion false.
- Only one change was made: the register folder, then named
  `predictions_register`, is stored under `predictions/`, the current layout.
  File contents are byte-for-byte the historical ones.
- The claim was withdrawn in the v12.3 honesty pass; see CHANGELOG.md.
