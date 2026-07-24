# Claim verification: binding prose to executable facts

**Status:** implemented and validated, July 2026. Tool: [`scripts/verify_claims.py`](../scripts/verify_claims.py). Manifest: [`CLAIMS.json`](../CLAIMS.json). Regression guard: [`scripts/verify_claims_retro_test.sh`](../scripts/verify_claims_retro_test.sh).

## 1. The gap this closes

This repository already shipped a claims linter (`docs_claims_lint.py`, 28 KB). Its entire expressive range is two rule families:

- `BANNED_RULES` — this phrase must **not** appear;
- `REQUIRED_RULES` — this phrase **must** appear in this file.

Both are pure text operations: no subprocess, no introspection of the artifact. Neither can ask whether a sentence is **true**.

That is not a hypothetical limitation. For twelve build cycles and through two hostile-review audits, this project's headline methodological claim — that its predictions were *"cryptographically signed and time-stamped before the corresponding observational data are released"* — was false. Every register entry was an unsigned scaffold. A phrase linter cannot catch this; a `REQUIRED_RULES` entry would happily have **mandated** the sentence. What finally caught it, in the v12.3 honesty pass, was one mechanical check nobody had thought to run: `grep SCAFFOLD`.

The lesson is not "we needed a better model." The decisive evidence was one line long and cost nothing. The failure was that no one had **bound the claim to a check**.

`verify_claims.py` generalizes that binding. Each load-bearing claim in `CLAIMS.json` is paired with a predicate over the repository's real state. The failure mode it exists to catch is:

> **ASSERTED + UNBACKED** — the documentation says it; the artifact does not do it.

## 2. What is exact and what is heuristic

Being precise about this is the difference between a useful instrument and a false-confidence generator.

| Side | Method | Reliability |
|---|---|---|
| **Verification** ("does the artifact do it?") | file/dir counts, YAML front-matter field values, SHA-256 recomputation, JSON schema-name resolution, subprocess exit codes | **Exact and mechanical.** No inference. |
| **Detection** ("is the claim being asserted?") | regex over prose with an explicit `unless` hedge list, or an exact `<!-- claim:id -->` anchor | **Heuristic** in regex mode. Anchors are exact. |

Detection is heuristic because prose varies and legitimate mentions exist: a changelog documenting a retraction, a paper quoting its own corrected wording, a protocol spec describing signing it does not perform. The hedge families in use are (a) explicit self-correction, (b) explicit non-execution, (c) normative/definitional statements. Family (c) is the subtle one — `"the record must be unforgeable"` describes a requirement, not this register.

**The obvious attack on this design is over-hedging**: silence a real finding by adding one more `unless` pattern. Section 4 is how that attack is blocked.

## 3. Validation experiment (retro-detection)

**Method.** Extract the pre-honesty-pass tree (commit `a42d294`, v12.2, 2026-04-27) and run the **current** manifest — hedge list included — against it. The manifest is unchanged from the one that reports the present tree clean.

**Result.** Four independent historical findings, each of which originally cost a human-led audit cycle, were rediscovered mechanically:

| Finding | Originally found by | Retro-detected? | Evidence produced |
|---|---|---|---|
| Register described as cryptographically signed while all 10 entries were unsigned scaffolds | v12.3 hostile re-audit (survived 12 cycles + 2 audits) | **Yes** | **18 assertion sites** across 8 files vs `0/10` entries with a signature field |
| Prose said "eight predictions"; register held ten | July 2026 execution audit (manual grep) | **Yes** | 3 sites (`GSC_Framework.md:34`, `paper_D/main.md:29,165`) vs counted 10 |
| `CITATION.cff` pointed at the private repo — a 404 for anyone following the citation | July 2026 metadata pass | **Yes** | 0 matches for the canonical public repo |
| `GSC_Framework.md` §9 documented only P1–P8 | July 2026 execution audit | **Yes** | highest enumerated section = P8 vs counted 10 |

**Runtime: 0.11–0.20 s** over 134 markdown files. Current tree: **exit 0, clean.**

**The honest caveat, stated plainly.** This is a **regression test, not a blind trial.** The manifest was written by someone who already knew these four findings. It proves the checks are *mechanically sufficient* to catch them and that the hedge list does not neuter them — it does **not** establish a prospective catch rate. A blind trial would require applying the tool to a project whose errors the manifest author does not know. That experiment has not been run.

**One prospective catch, n = 1.** During calibration the tool flagged a site nobody had looked at: `papers/paper_D_methodology/joss/SUBMIT.md:99`, a reviewer talking-point still coaching the author to *"emphasise the deterministic-pipeline + cryptographic signing"* as a selling point. That overclaim survived the July hand-audit hours earlier and was corrected as a result of this run. Also honest: of four failures on that first run, **three were bugs in the tool** (a decimal-place regex bug, a wrong counting glob, and a misuse of enumeration mode), not repository defects. First-run precision was 1/4; after calibration, 0 false positives on the current tree.

## 4. The retro-test as a permanent regression guard

The validation experiment is not a one-off. It is wired in as a check that runs on every change to the tool or the manifest:

```bash
bash scripts/verify_claims_retro_test.sh
```

It asserts that the current tool + manifest **still fail** against the historical v12.2 tree on the signing claim. This inverts the usual polarity of a test — it requires a *failure* to succeed — and that is precisely what defends against over-hedging:

> Any future edit that silences the historical false claim (by relaxing a pattern, widening a hedge, or deleting the claim) breaks CI.

The detector's sensitivity is therefore itself continuously verified against a known ground truth. Adding hedges stays cheap; adding hedges that blind the instrument does not.

### 4.1 A negative control, and what it caught

A guard that has never failed is not a guard. It was tested by sabotage: adding the single over-broad hedge `"signed"` to the manifest, then re-running.

**The first version of the guard passed the sabotage.** Detection had collapsed from 18 assertion sites to 1 — the surviving line said *"cryptographic signing"*, which the hedge `signed` does not match — yet the binary check ("does the claim still fire?") was satisfied. An attacker could have silenced 17 of 18 sites and kept CI green.

The guard now enforces a **sensitivity floor** (`MIN_SITES=10`) rather than mere non-zero firing. Verified both ways:

| Control | Manifest | Guard verdict |
|---|---|---|
| Positive | real | **PASS** — 18 sites, floor 10 |
| Negative | `+ unless: "signed"` | **FAIL** — "still fires, but on only 1 site… firing on one line is not detection; it is luck" |

The general lesson is worth stating, because it generalizes past this repository: **a detector's own regression test must measure sensitivity, not liveness.** Binary "did it alarm?" checks are defeated by partial blinding, and partial blinding is what hedge-list edits actually do.

## 5. Using and extending it

```bash
python3 scripts/verify_claims.py                 # verify this package (exit 1 if any claim unbacked)
python3 scripts/verify_claims.py --explain       # show every claim and its reasoning
python3 scripts/verify_claims.py --include-slow  # also run subprocess facts (determinism)
python3 scripts/verify_claims.py --format json   # machine-readable
python3 scripts/verify_claims.py --root <tree>   # verify some other tree with this manifest
```

Adding a claim means answering one question: **what fact, checkable by a machine, would be false if this sentence were a lie?** Available predicates: `frontmatter_field_nonempty`, `path_count`, `number_agreement` (modes `each`/`max`, counts files or directories), `sibling_hash_match`, `json_field_resolves`, `file_regex_count`, `command_exit_zero`.

If no such fact exists, that is itself worth knowing: the sentence is unfalsifiable as written, and either it should be sharpened or it is decoration.

## 6. Scope and honest limitations

- **Not novel in its parts.** Assertion-style docs testing (doctest, `mdbook test`, literate-programming verification) and policy-as-code (OPA, Conftest) are established. The specific composition here — *load-bearing prose claims of a research artifact, bound to predicates over that artifact's own state, with the detector's sensitivity regression-tested against a historical false claim* — is what we have not found prior art for. Treat that as an unverified novelty claim, appropriately.
- **Covers 10 claims,** not every sentence in the package. It covers the load-bearing ones, chosen by hand.
- **Cannot judge physics.** It verifies that documentation matches artifact. It says nothing about whether the cosmology is correct — that question is settled elsewhere and unfavourably (`docs/cosmic_acceleration_origins_findings.md`).
- **Detection can be defeated** by novel phrasing no pattern anticipates. Anchors (`<!-- claim:id -->`) are the mitigation where exactness matters.
- **This document is excluded from the signing-claim detector**, and the reason is worth recording: on its first run the tool flagged *this file*, because §4.1 quotes the historical false claim verbatim while explaining the negative control. Meta-documentation about a checker necessarily contains the strings the checker hunts. The exclusion is declared in `CLAIMS.json` (`exclude_note`) rather than hidden in a hedge pattern, so a reviewer can see and challenge it. A verifier that cannot be pointed at itself would be a poor advertisement for the idea; a verifier whose self-exclusions are undocumented would be worse.
