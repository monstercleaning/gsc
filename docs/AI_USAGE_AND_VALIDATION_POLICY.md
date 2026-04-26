# AI Usage and Validation Policy (Phase-4, current v11 series)

Purpose: improve transparency and reliability when AI tools are used in this repository.

## What AI is used for

- Code scaffolding and boilerplate generation.
- Drafting and editing documentation.
- Refactoring suggestions and implementation alternatives.

## What AI output is not trusted without independent validation

- New analytic derivations or theorem-like arguments.
- Sign/factor-sensitive formula steps.
- Citation accuracy and source interpretation.

These require explicit human verification and, where applicable, reproducible computational checks.

## Validation rule

No claim should ship without an executable check or artifact.

Operationally:
- map claim boundaries to checks in `docs/VERIFICATION_MATRIX.md`;
- keep claim language within lint guardrails enforced by
  `scripts/docs_claims_lint.py`;
- prefer schema-tagged outputs and deterministic replay paths.

## External disclosure guidance

When preparing `paper.md` or external submissions:
- disclose AI use as an implementation/writing aid;
- do not represent AI output as independent scientific validation;
- reference repository tests/artifacts as the verification basis.

## When in doubt

Convert assumptions into tests, and prefer computational verification over narrative confidence.
