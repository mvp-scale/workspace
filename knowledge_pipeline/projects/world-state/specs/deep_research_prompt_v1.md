# Deep research request: enhanceable units for a CPU news-reading classifier

## Your job
Find PROVEN systems, methods, tools and best practices that I can adopt instead of inventing. No background essays. For every item give evidence, not opinion. If you cannot find evidence, say "no evidence found".

## What we are building
A small model that reads one news item (headline + short description + source name) and answers many questions in one pass: topic (49 classes), story type (fact / forecast / opinion / unclear), "conditions" (38 yes/no/direction/size questions, e.g. "prices rising", "unrest"), plus optional claim, evidence, direction and local-vs-world scope.
- Serving limits: one CPU thread, under 50 ms per item, no GPU, no API calls, no generative LLM.
- Training data: 24,775 labelled news items. Labels come from two LLM teachers (a small and a medium model) and are noisy: they agree 83.7% on topic, 92.4% on story type, and name the same condition only 48% of the time. The main disagreement is WHETHER a condition is present (passing mentions), not which one. A 50-item human-checked key exists; larger human labelling is expensive.
- Budget: low hundreds of US dollars in total, so label-hungry methods need a cost estimate.

## Already tried (do not suggest again)
Static-embedding cosine probes (presence AUC 0.88, direction unusable); word-list direction (balanced accuracy 0.69); HDBSCAN on embeddings (no useful clusters); spaCy structure flags (story-type balanced accuracy 0.64); an open-IE extractor and a quantity parser (+0.000 AUC); source name as a feature (+0.001); a single shallow decision tree for rules (7 rules, 9% coverage); re-asking the same LLM (repeats 96-99%).

## Wish list: the units to enhance (research each one)
1. Noisy and disagreeing teachers: noisy-label learning, confident learning, multi-annotator models (Dawid-Skene, MACE), label models (weak supervision), soft labels. Which works best when two teachers disagree on presence?
2. Abstention and guarantees: selective classification, calibration, conformal risk control for multi-label output, so a cheap gate can guarantee a stated recall and send only uncertain items on.
3. Cheap-first cascades: proven routing designs (including LLM cascades) and how they set thresholds.
4. Distilling into a tiny CPU model: soft-label distillation, static or small embeddings, fastText-style, SetFit, int8/ONNX; measured accuracy and single-thread latency.
5. Rule and pattern mining from model behaviour: Anchors, RuleFit, Boolean rule sets, prototype or case-based explanation, retrieval of labelled neighbours. How many labelled items does a stable rule need?
6. Direction of change (up/down/mixed) in news text: proven models, lexicons, datasets.
7. Claim, evidence and attribution extraction that runs on CPU: check-worthiness, claim detection, attribution (CheckThat!, NewsClaims, ClaimBuster and successors). Which parts are solved, which not?
8. Event and condition ontologies with labelled data we can reuse: IPTC Media Topics, CAMEO, PLOVER/POLECAT, ACLED, GDELT, Event Registry. Crosswalks, licences, and datasets usable for pretraining or evaluation.
9. Source credibility and outlet metadata: what is used in practice and how much it adds.
10. Local vs world scope: geoparsing and scope classification with proven tools.
11. Evaluation with noisy teacher labels: how to size a small human gold set, agreement statistics, power, leakage control (near-duplicates, time splits).
12. Choosing what to label next: active learning and data selection for a multi-label problem with rare classes.
13. Continuous learning on a news stream: versioned snapshots, drift detection, learning-curve monitoring.
14. Existing end-to-end news-understanding pipelines or open projects we could reuse parts of.

## Required format for every finding
Name; link to the primary source (paper, repo, docs); what it does in one sentence; reported performance WITH dataset and numbers; compute needed (CPU only?); licence; effort to adopt in days; how it plugs into the setup above; main risk; and the cheapest test we could run in under one day on 24,775 items. Mark each claim as "stated by source" or "your inference". Mark the strength: production use / peer-reviewed benchmark / blog or preprint only.

## Final output
1. A ranked table of the top 15 findings by (expected gain x ease), with the unit number from the wish list.
2. THE EFFICIENT STARTING POINT: the one or two things to do first, why, and what result would tell us to stop.
3. A "do not bother" list: popular approaches that are known not to help in this setting, with evidence.
4. Gaps: wish-list units where nothing proven exists.
Keep it dense and cited. No introductions, no summaries of what machine learning is.
