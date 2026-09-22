# GSC — a self-checking scale-covariant cosmology

**What it is.** Standard cosmology says the universe expands. GSC asks what follows if instead matter shrinks —
atoms, rulers and clocks all together — against a nearly static background. Mathematically the two descriptions
are equivalent (C. Wetterich, 2013; the idea goes back to Canuto et al., 1977), so the question is whether matter's
"shrinking" has any dynamics of its own that could be measured. GSC turns that question into fourteen registered
predictions, each with a pipeline, a scoring rule fixed in advance, and a condition under which the framework
admits it is wrong.

**Honest status.** Most predictions that could distinguish GSC from standard cosmology are either excluded by
data or indistinguishable from it. The one registered late-universe deviation, a +0.417% shift of the cosmic
"BAO ruler", is absorbed into the Hubble constant once the other cosmological parameters are refitted. What
remains distinctive is a prediction that gravity was slightly weaker in the early universe (P14), which the
next generation of measurements can test ([OPEN_PROBLEMS.md](OPEN_PROBLEMS.md)). What stands independently of the
physics is the method: a prediction register that cannot be quietly edited, and a checker that fails the build
whenever the documents claim something the package does not do.

## Start here

| If you want to… | Read |
|---|---|
| Understand the theory and its current status | [THEORY.md](THEORY.md) |
| See every prediction and its verdict | [PREDICTIONS.md](PREDICTIONS.md) |
| Understand how predictions are registered, scored and verified | [METHOD.md](METHOD.md) |
| See the known problems | [OPEN_PROBLEMS.md](OPEN_PROBLEMS.md) |
| Read the papers | [papers/](papers/) |
| See what changed and why | [CHANGELOG.md](CHANGELOG.md) |

## Check it yourself

Python 3.9 or newer, no other dependencies.

```bash
python3 -m unittest discover -s tests            # unit tests
python3 verification/verify_claims.py            # do the documents tell the truth about the package?
bash pipelines/predictions_compute_all.sh        # recompute every prediction and score it
```

## Layout

```
README.md  THEORY.md  PREDICTIONS.md  METHOD.md  OPEN_PROBLEMS.md  CHANGELOG.md
predictions/   one folder per prediction: statement, frozen output, data, scorecard
pipelines/     the code that computes and scores each prediction
gsc/           the small computational core the pipelines use
verification/  the claim checker, its manifest and its negative control
analyses/      diagnostic studies (not registered predictions)
papers/        papers A–E
docs/          design notes and research notes
data/          the one external dataset the analyses read
schemas/       JSON schemas of the pipeline outputs
tests/         unit tests
```

## Citation and licence

Dimitar Baev (ORCID 0009-0009-7812-9203), independent researcher; founder of Monster Cleaning Ltd.
(https://monstercleaning.com). See [CITATION.cff](CITATION.cff). Code under the MIT licence ([LICENSE](LICENSE));
papers under CC BY 4.0. Developed with AI assistance and audited by adversarial multi-model review
([docs/AI_USAGE_AND_VALIDATION_POLICY.md](docs/AI_USAGE_AND_VALIDATION_POLICY.md)).
