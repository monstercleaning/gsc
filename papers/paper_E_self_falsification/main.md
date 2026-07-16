---
title: 'The Audit That Bit Its Master: A Version-Controlled Case Report of Adversarial Multi-LLM Review Falsifying Its Operators'' Own Central Claim'
author: Dimitar Baev
orcid: 0009-0009-7812-9203
affiliation: Independent researcher; Founder, Monster Cleaning Ltd. (https://monstercleaning.com)
date: 29 May 2026
---

## Abstract

A persistent worry about large-language-model (LLM)-assisted research is *sycophancy*: models tend to agree with and reinforce their operator's framing, and LLM self-critique is prone both to false positives and to ratifying genuine errors. The decisive test of an AI-assisted audit process is therefore not whether it catches *other people's* mistakes, but whether it catches its *operators' own* — especially the central, incentive-protected claim — and forces a costly public retraction. We report a documented, version-controlled instance in which it did. During the multi-cycle development of a speculative cosmology framework (GSC), built by a non-specialist with LLMs as the primary research collaborators and audited by alternating models (Gemini, Claude, ChatGPT) against a git-backed pre-registration register, an adversarial re-audit by a fresh model instance found that the project's **own central methodological claim** — that its numerical predictions were "cryptographically signed and time-stamped before the corresponding observational data are released" — was false: the predictions were unsigned scaffolds, and most were retrodictive checks against already-public data. The claim was retracted and corrected in public, with the git diff as the evidence. Because this is a report about honesty, we foreground its limitations: it is a single episode (n = 1); the operator chose both to commission the adversarial pass and to act on it; and the same class of tool both introduced and caught the error. We argue the episode is a small but genuine existence proof of *un-sycophantic* AI-assisted self-correction, and that the falsifiable artifact is the diff, not the testimony.

## 1. Background: the sycophancy problem, and why counter-evidence is scarce

LLMs are now routine research collaborators — drafting code, prose, and arguments. The central reliability concern is that they are trained, via human-preference optimization, toward responses the operator will approve, which induces *sycophancy*: a measured tendency to tell the user what they want to hear and to revise correct answers when pushed back on [@Sharma2023]. The natural mitigation — have the model critique its own output — is itself unreliable: self-verification frequently produces false positives and fails to catch genuine reasoning errors [@Stechly2023], and even dedicated critic models, while net-helpful, hallucinate defects [@McAleese2024]. Multi-agent debate improves factuality on some tasks [@Du2023], but the failure mode that matters for *research integrity* is specific and under-documented: will an AI reviewer contradict the operator on the operator's own load-bearing claim — the one with the most ego and sunk cost behind it — when doing so invalidates work already published?

Human science has institutional analogues for exactly this hazard: pre-registration and registered reports, which fix predictions and analyses before the data are seen [@Nosek2018], and *blind analysis*, in which results are hidden until the pipeline is frozen [@KleinRoodman2005; @MacCounPerlmutter2015]. The open question is whether an LLM-in-the-loop workflow can supply a comparable discipline in practice. Documented counter-examples to sycophancy — cases where the AI audit *cost the operator something real* — are scarce. This is one.

## 2. Setup

GSC is a speculative "scale-covariant" cosmology (a *shrinking-matter* reframing of cosmic expansion), developed over many iterations by a non-physicist with LLMs as the primary research collaborators. Independent analysis (summarized in the project's companion material) concludes the physics is observationally sterile where it is internally consistent — which is *useful context here*: it means the methodology, not the cosmology, is what is under test, and that the operator had every incentive to keep the methodology's reputation intact even as the physics was trimmed.

The project was wrapped in deliberate rigor scaffolding: deterministic pipelines with content-hashed (SHA-256) artifacts and lineage tracking; an append-only, git-time-stamped "pre-registration register" of numerical predictions with per-prediction scoring rules; a four-tier claim hierarchy with independent kill-tests; and iterative *adversarial* "hostile-review" audit cycles, each conducted by a different LLM instructed to attack rather than assist. Crucially, **the same tools that built the framework also wrote its prose**, including the methodology paper's central claim. That is the setup in which an error of self-description could be both introduced and, later, caught.

## 3. The episode

**Cycles 1–2 (releases v12.1, v12.2): catches *of the work*.** Adversarial audits flagged, and the operator corrected or retracted in public, a series of genuine errors: a sign-and-magnitude error in a neutron-lifetime sensitivity coefficient that had turned a null result into a spurious "positive"; an artefactual joint-constraint scan; missing citations to directly contradicting literature; a schema-enforcement gap; a universality contradiction across predictions; and a dimensional inconsistency. Each was logged in the changelog. These were real, but they were *comfortable*: the theory was being trimmed while the **method** was assumed sound.

**Cycle 3 (release v12.3): the catch *of the method itself*.** A fresh, more capable model instance was given a single instruction — find what the previous passes missed — and file/git access. It ran parallel specialized sub-audits (pre-registration integrity; cross-prediction parameter consistency; physical demarcation; degenerating-programme dynamics). The integrity sub-audit established, by elementary inspection, that:

- all ten register entries carried `status: SCAFFOLD — NOT YET SIGNED`, with empty signature fields;
- the signing script was an unexecuted reference stub;
- `docs/pre_registration.md` simultaneously asserted the register "is cryptographically signed" *and* that the signing scripts were "scheduled for implementation" — an internal contradiction in one file;
- the flagship prediction (P1) had been scored against a dataset (DESI Year-1, public since 2024) two years *older* than its registered target (DESI Year-3, 2027), with the test statistic altered after the fact.

In other words, the methodology paper's central sentence — *"predictions are signed and time-stamped before the corresponding observational data are released … you cannot move the goalposts"* — was false on both counts: nothing was signed, and most "predictions" were retrodictions.

The finding was acted on rather than buried. The deposited paper, the long-form manuscript, the metadata, and the register were all corrected to state the truth (the register is git-time-stamped, not signed; most worked examples are retrodictive consistency checks). A changelog entry documents the catch, and the corrected paper now contains a paragraph reporting that *its own earlier draft overstated its central claim*. The evidence is public and machine-checkable: commits `13feb8f` and `41bd036`, and the diff between them and their parent.

## 4. Why this is not trivial

Three features distinguish this from ordinary error-catching. First, the retracted claim was the **operators' own central thesis** — the load-bearing sentence of the very paper being submitted — not a peripheral detail. Second, the catch ran *against* the documented default behavior: the expected LLM response is to ratify the operator's framing, and for more than a dozen prior cycles the false claim had survived precisely because generation-mode passes (and the human) propagated a plausible-sounding sentence nobody checked. Third, the decisive evidence was *cheap* — a one-line search for the string `SCAFFOLD` — which is exactly why its having been missed for so long is the point: the failure was not a lack of capability but a lack of adversarial stance. Supplying that stance, plus tool access, changed the outcome.

## 5. Honest limitations

This is a report about honesty; it must apply the standard to itself.

- **n = 1.** A single episode is an existence proof, not a rate. We do not know the audit's false-negative rate (how many other false claims survive uncaught) or its false-positive rate.
- **Operator selection effect.** The operator chose to commission the adversarial pass *and* chose to act on it. The loop supplies the finding; it does not supply the will to act, and a different operator could have ignored it. The mechanism is necessary, not sufficient.
- **Same-class tool on both sides.** An LLM in generation mode introduced the overclaim; an LLM in adversarial mode caught it. The honest reading is not "AI reliably catches human error" but "adversarial framing plus file/git access caught what generation framing had missed." The *mode* and the *access* did more work than the model.
- **Capability confound.** The catching pass also coincided with a model upgrade. We cannot cleanly separate "adversarial stance" from "more capable model"; both plausibly contributed.
- **Pre-registration ≠ falsifiability of a theory.** Fixing a number in advance constrains researcher degrees of freedom; it does not make an underlying theory risky [@Szollosi2020]. Here the surrounding theory is, by independent analysis, observationally sterile — so the corrected method sits atop a case study of little physical content. The method must be judged on the audit *behavior*, not on the case study's results.
- **No claimed novelty in the scaffolding.** Pre-registration of computational predictions, multi-LLM review, and content-hashed provenance are each incremental against the 2022–2026 literature. The only contribution claimed here is the documented self-falsification episode and its evidence trail.

## 6. What would make this rigorous

The episode suggests a measurable research programme rather than a finished result. One would: (i) pre-register a fixed adversarial-audit protocol and apply it across multiple independent projects, measuring the rate at which it catches *operator-central* errors versus the rate at which it raises false alarms; (ii) blind the auditing instance to which claims are "central," to test whether centrality is detected or merely asserted; (iii) compare adversarial-stance against neutral-stance auditing on identical artifacts, to isolate the contribution of stance from capability; and (iv) publish full audit transcripts, not just diffs, so each catch is independently checkable.

## 7. Conclusion

We have documented a small but genuine event: a version-controlled instance of an AI adversarial-review loop falsifying its operators' own central claim and forcing a public correction, against the incentive to protect it and against the well-documented tendency of LLMs to do the opposite. We do not claim a method, a rate, or a guarantee — only a single, dated, checkable data point in the debate over whether LLM-assisted research can be self-correcting rather than self-reinforcing. The artifact that matters is the diff, not our account of it. We offer it, and the protocol that produced it, for others to instrument, measure, and try to break.

## References

- **[Sharma2023]** M. Sharma, M. Tong, T. Korbak, D. Duvenaud, A. Askell, S. Bowman, et al., "Towards Understanding Sycophancy in Language Models," arXiv:2310.13548 (2023).
- **[Stechly2023]** K. Stechly, M. Valmeekam, S. Kambhampati, "Can Large Language Models Really Improve by Self-critiquing Their Own Plans?" arXiv:2310.08118 (2023).
- **[McAleese2024]** N. McAleese, R. M. Pokorny, J. F. Ceron Uribe, E. Nitishinskaya, M. Trebacz, J. Leike, "LLM Critics Help Catch LLM Bugs," arXiv:2407.00215 (2024).
- **[Du2023]** Y. Du, S. Li, A. Torralba, J. B. Tenenbaum, I. Mordatch, "Improving Factuality and Reasoning in Language Models through Multiagent Debate," arXiv:2305.14325 (2023).
- **[Nosek2018]** B. A. Nosek, C. R. Ebersole, A. C. DeHaven, D. T. Mellor, "The preregistration revolution," *Proceedings of the National Academy of Sciences* 115(11):2600–2606 (2018). doi:10.1073/pnas.1708274114.
- **[Szollosi2020]** A. Szollosi, D. Kellen, D. J. Navarro, R. Shiffrin, I. van Rooij, T. Van Zandt, C. Donkin, "Is Preregistration Worthwhile?" *Trends in Cognitive Sciences* 24(2):94–95 (2020). doi:10.1016/j.tics.2019.11.009.
- **[KleinRoodman2005]** J. R. Klein, A. Roodman, "Blinded Analysis," *Annual Review of Nuclear and Particle Science* 55:141–163 (2005). doi:10.1146/annurev.nucl.55.090704.151521.
- **[MacCounPerlmutter2015]** R. MacCoun, S. Perlmutter, "Blind analysis: Hide results to seek the truth," *Nature* 526:187–189 (2015). doi:10.1038/526187a.
