# Criteria circling methods: testing a classifier around its target

Scope: published methods that test a classifier from several sides, not only head-on. Only pages opened in this session are cited as verified. Direction key: SIDEWAYS = near neighbours / look-alikes / minimal edits; UP/DOWN = whole area vs single label vs slice; LEFT/RIGHT = pipeline stage (source -> data -> labels -> model -> downstream use).

| # | Method | Citation | URL (opened) | Core idea (<= 25 words) | Direction | Status |
|---|---|---|---|---|---|---|
| 1 | Contrast sets | Gardner et al., 2020, "Evaluating Models' Local Decision Boundaries via Contrast Sets" (arXiv:2004.02709) | https://arxiv.org/abs/2004.02709 | Authors make small, meaningful edits to test instances that usually flip the gold label, exposing behaviour near the decision boundary. | SIDEWAYS | Verified (abstract) |
| 2 | CheckList | Ribeiro et al., 2020, "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList" (ACL 2020) | https://arxiv.org/abs/2005.04118 | Task-agnostic behavioural testing, borrowed from software testing: a matrix of linguistic capabilities times test types. | UP/DOWN (capability x test-type matrix covers the whole area) | Abstract verified. Minimum functionality, invariance and directional test definitions NOT verified (PDF unreadable, README lacks them) |
| 3 | Counterfactually augmented data | Kaushik, Hovy, Lipton, 2019/ICLR 2020, "Learning the Difference that Makes a Difference with Counterfactually-Augmented Data" (arXiv:1909.12434) | https://arxiv.org/abs/1909.12434 | Humans make minimal, coherent rewrites that flip labels; training on original plus revised data resists spurious cues. | SIDEWAYS | Verified (abstract) |
| 4 | Slice-based learning | Chen, Wu, Weng, Ratner, Ré, 2019, "Slice-based Learning: A Programming Model for Residual Learning in Critical Data Slices" (NeurIPS 2019; arXiv:1909.06349) | https://arxiv.org/abs/1909.06349 | Slicing functions flag critical data subsets, giving each slice dedicated capacity so performance improves there. | UP/DOWN (slice) | Verified (abstract) |
| 5 | Model Cards | Mitchell et al., 2018/FAT* 2019, "Model Cards for Model Reporting" (arXiv:1810.03993) | https://arxiv.org/abs/1810.03993 | Model documentation reports performance separately for demographic and intersectional subgroups to clarify suitable uses. | UP/DOWN (subgroup slices); RIGHT (downstream use) | Verified (abstract) |
| 6 | Dynabench | Kiela et al., 2021, "Dynabench: Rethinking Benchmarking in NLP" (arXiv:2104.14337) | https://arxiv.org/abs/2104.14337 | Annotators craft examples that models misclassify, so dataset creation and model evaluation inform each other. | LEFT/RIGHT (collection loop); SIDEWAYS (adversarial near-misses) | Verified (abstract) |
| 7 | Adversarial NLI | Nie et al., 2019/ACL 2020, "Adversarial NLI: A New Benchmark for Natural Language Understanding" (arXiv:1910.14599) | https://arxiv.org/abs/1910.14599 | Rounds of human writers and models in turn, with people writing examples that fool current models, so the benchmark keeps hardening. | LEFT/RIGHT (rounds of data collection); SIDEWAYS | Verified (abstract) |

Not opened or not verified:
- Snorkel slicing: the first ID tried (arXiv:1812.00417) is a different paper (DryBell); the correct one is row 4.
- Hard negatives and "none of the above" / abstain class in evaluation: no primary paper opened. A search returned reject-option and abstaining-classifier papers (e.g. arXiv:1505.04137, arXiv:2104.02334), which are unread leads only, not cited.
- Snorkel slicing functions in code were not checked against the paper beyond the abstract.

## Synthesis: how these combine to circle a target

1. SIDEWAYS rings come from contrast sets and counterfactual edits (rows 1, 3): minimal pairs that should flip the label, testing the local decision boundary.
2. Dynabench and ANLI (rows 6, 7) keep that ring current by adding adversarial near-misses through rounds of model-in-the-loop collection, so the boundary moves with the model.
3. UP/DOWN coverage: CheckList's capability-by-test matrix (row 2) checks the whole area, while slices (rows 4, 5) check single subgroups or critical subsets that aggregate scores hide.
4. LEFT/RIGHT coverage: Dynabench and ANLI audit data collection (rows 6, 7), and Model Cards audits documentation at downstream use (row 5). Source-stage checks are not covered by any verified row here.
5. A target is circled by a sideways ring of flip pairs, an up/down ring of capabilities and slices, and a left/right ring from source to use; the none-of-the-above / hard-negative part of the ring is still unverified.
