# RG Crossover vs Pole (ToE-track note)

Disclaimer: this is a conceptual ToE-track note. It is not part of submission/referee canonical claims.

## Why this note exists

The v10 late-time paper uses a pole-like form as an effective sharp-crossover parameterization. This note records safer language and alternative bounded families, so future modules can avoid over-interpreting a literal divergence.

## Operational framing

- Treat "pole-like" as a Pad\'e-like proxy for rapid crossover in an effective coupling.
- Do not claim a physical singularity unless a UV-complete derivation supports it.
- Keep the tested claim at the level of observables and falsifiers, not microscopic narrative.

## Example bounded crossover families (dictionary-level only)

1. Logistic crossover:
- `G_eff(k) = G_IR * [1 + (A_max - 1) / (1 + exp((k0-k)/w))]`
- bounded by `A_max`, no literal divergence.

2. Hyperbolic-tangent crossover:
- `G_eff(k) = G_IR * [1 + 0.5*(A_max-1)*(1 + tanh((k-k0)/w))]`
- smooth monotone transition.

3. Rational bounded Pad\'e family:
- `G_eff(k) = G_IR * (1 + a x) / (1 + b x + c x^2)`, with positivity/stability constraints.

## Practical policy

- Use bounded families for robustness scans.
- Reserve literal-pole language for clearly marked phenomenological shorthand.
- Require kill-test compatibility (drift sign, precision constraints, closure diagnostics) before promotion.
