# Criteria practitioner sources (Haiku)

Date: 2026-10-21. Method: each page below was opened with WebFetch on the date above. Quotes are copied from the fetched text and are under 30 words. Level: SOURCE (where texts come from), DATA (the labelled set), MODEL (the trained reader), PIPELINE (how they connect).

## Verified sources

| # | Source | URL | Quote | Level | Note |
|---|---|---|---|---|---|
| 1 | Hugging Face model cards | https://huggingface.co/docs/hub/model-cards | "The model card should describe: ... its intended uses & potential limitations ... the model's evaluation results" | MODEL | Lists intended use, limits, training data and eval results as required card content. |
| 2 | Hugging Face dataset cards | https://huggingface.co/docs/hub/datasets-cards | "it's a good idea to include information about any potential biases within the dataset" | SOURCE | Card guidance on bias and provenance. No split rules. |
| 3 | Hugging Face evaluate, choosing a metric | https://huggingface.co/docs/evaluate/choosing_a_metric | "Reading the metric cards for the relevant metrics and see which ones are a good fit for your use case." | MODEL | Metric choice is left to the use case. No imbalance or held-out rule. |
| 4 | LightEval (Hugging Face) | https://huggingface.co/docs/lighteval/index | "saving and exploring detailed, sample-by-sample results to debug and see how your models stack up." | MODEL | Per-sample results as the debugging unit. |
| 5 | Open LLM Leaderboard, About | https://huggingface.co/docs/leaderboards/open_llm_leaderboard/about | "have sufficient sample sizes for statistical significance" | MODEL | Justifies benchmark choice by sample size and objective metrics. |
| 6 | Open LLM Leaderboard, About (contamination) | https://huggingface.co/docs/leaderboards/open_llm_leaderboard/about | "Access to GPQA is restricted through gating mechanisms to minimize the risk of data contamination." | DATA | Test-set contamination control by gating. |
| 7 | Unsloth fine-tuning guide (fetched at unsloth.ai after 301) | https://unsloth.ai/docs/get-started/fine-tuning-llms-guide | "For testing, you can also take 20% of your training data and use that for testing." | DATA | Test split can come from the training data. This is weaker than a separate held-out set. |
| 8 | Unsloth fine-tuning guide | https://unsloth.ai/docs/get-started/fine-tuning-llms-guide | "If the loss goes to 0, that could mean overfitting, so it's important to check validation too." | MODEL | Training loss is not a stop signal on its own. |
| 9 | Unsloth fine-tuning guide | https://unsloth.ai/docs/get-started/fine-tuning-llms-guide | "automated tools may not perfectly align with your evaluation criteria." | MODEL | Automated metrics need checking against your own criteria. |
| 10 | TRL SFTTrainer | https://huggingface.co/docs/trl/main/en/sft_trainer | "eval_dataset ... It must meet the same requirements as train_dataset." | PIPELINE | The eval set is a separate argument with the same format rules. The page sets no stopping rule. |
| 11 | Axolotl config reference (fetched at docs.axolotl.ai after 301) | http://docs.axolotl.ai/docs/config-reference.html | "How much of the dataset to set aside as evaluation. 1 = 100%, 0.50 = 50%, etc. 0 for no eval." | PIPELINE | Held-out split is a config fraction, default 0. |
| 12 | Axolotl config reference | http://docs.axolotl.ai/docs/config-reference.html | "Stop training after this many evaluation losses have increased in a row." | PIPELINE | Early-stopping rule keyed to eval loss (early_stopping_patience). |
| 13 | Cleanlab, in-depth overview | https://docs.cleanlab.ai/stable/tutorials/indepth_overview.html | "inspect issues and fix issues to ensure high-quality test data labels." | DATA | Test-set labels get a fix pass. Flagged items may be ambiguous, not wrong. |
| 14 | Cleanlab, in-depth overview | https://docs.cleanlab.ai/stable/tutorials/indepth_overview.html | "Low-quality labels indicate examples that should be more closely inspected." | DATA | Scores rank items for review. The page gives no keep/drop threshold. |
| 15 | Cleanlab, Datalab quickstart | https://docs.cleanlab.ai/stable/tutorials/datalab/datalab_quickstart.html | "what to do with the findings will vary case-by-case." | PIPELINE | No numeric cutoff. Decisions are per case. |
| 16 | Great Expectations, create an expectation | https://docs.greatexpectations.io/docs/core/define_expectations/create_an_expectation | "An Expectation is a verifiable assertion about your data." | DATA | Criteria are named, checkable statements. Severity defaults to "critical" if not set. Suites not covered on this page. |
| 17 | Deepchecks, welcome | https://docs.deepchecks.com/stable/getting-started/welcome.html | "CI tests run 'before deploying the model to production.'" | PIPELINE | Checks run in research and again in CI before deploy. The page gives no numeric thresholds. |
| 18 | Evidently docs | https://docs.evidentlyai.com/ | "Test tabular data quality and data drift." | DATA | Weak: quickstart mention only. Tests are described, with no thresholds shown. |

## Opened, no usable rule (not in the table)

- Hugging Face evaluate landing page (https://huggingface.co/docs/evaluate/index): general description only.
- Argilla docs (https://docs.argilla.io/latest/): "Argilla helps you to achieve and keep high-quality standards for your data." Generic, no criteria.
- Snorkel blog (https://snorkel.ai/blog/): no slicing or evaluation rule on the page.
- Great Expectations introduction (https://docs.greatexpectations.io/docs/core/introduction/): no rule. Expectation suites not covered.

## Not covered

No Hugging Face blog post on evaluating classifiers, no GitHub checklist repo, and no Argilla guidelines or agreement page were opened. Snorkel's slicing docs and Great Expectations' suite docs were not found.

## 5-line summary of recurring practices

1. Evaluate on a split held out from the labelled data, never on training loss. Unsloth, TRL and Axolotl all expose an eval set; Unsloth's 20% from training data is the weakest version.
2. Stop training on a validation signal: Axolotl stops after N rising eval losses; Unsloth reads near-zero train loss as a warning.
3. Look at per-sample results and inspect flagged items by hand (LightEval, Cleanlab); aggregate scores alone are not the criterion.
4. Write the card: intended use, limits, data provenance and bias belong on the model and dataset cards (Hugging Face).
5. Name each check and give it a severity or fix step (Great Expectations, Cleanlab, Deepchecks). None of the 13 sources publishes a numeric acceptance threshold.
