# fallacy_logic

- Source: LOGIC dataset, Jin et al. (2022), "Logical Fallacy Detection", Findings of EMNLP 2022 (arXiv:2202.13758). Files `data/edu_dev.csv` and `data/edu_test.csv` (the educational-website LOGIC set, not LOGIC-Climate).
- URL: https://github.com/causalNLP/logical-fallacy (raw files fetched directly; HF mirror tasksource/logical-fallacy has the same data, listed as license "unknown").
- Licence: the GitHub repo declares none (API returns null). Treat as research-use only; do not redistribute beyond the benchmark without checking with the authors.
- Retrieved: 2026-09-21. Builder: build_fallacy_logic.py (seed 20260921).
- Citation: Jin, Lalwani, Vaidhya, Zhang, Mihalcea, Schölkopf et al. 2022, arXiv:2202.13758. Criteria descriptions are paraphrased from the paper's fallacy definitions (Table of fallacy types) and standard usage, not quoted.
- Sampling: dev+test pooled, exact-duplicate texts dropped, texts over 1500 chars dropped, 15 random items per type over 8 types = 120 items. Label names are the dataset's own (`updated_label`).
- Counts: ad hominem 15, ad populum 15, appeal to emotion 15, false causality 15, false dilemma 15, faulty generalization 15, circular reasoning 15, fallacy of credibility 15.
- Mechanical cleaning: trailing "Is an example of...." prompt (a dataset scraping artefact) removed; whitespace normalised.
- Caveats: this set contains NO "no fallacy" class; every item is a fallacy, so it tests type discrimination only. Labels come from quiz-website answers and were only partly re-annotated; some items are ambiguous between types (e.g. credibility vs ad populum, faulty generalization vs false causality). Five omitted types (intentional, relevance, logic, extension, equivocation) are vaguer or overlapping.
- Contamination: web-scraped educational quiz text, public since 2022; could appear in LLM pretraining.
