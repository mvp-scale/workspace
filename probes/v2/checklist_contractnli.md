# checklist_contractnli

- Source: ContractNLI (Koreeda & Manning 2021), https://stanfordnlp.github.io/contract-nli/ (zip: /resources/contract-nli.zip). Retrieved 2026-09-21.
- Licence: CC BY 4.0 (Hitachi America / Stanford; see TERMS in the download). Raw: /workspace/data/sources/contractnli/ (git-ignored).
- Citation: Y. Koreeda, C. D. Manning. "ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts". Findings of EMNLP 2021.
- Build: `build_checklist_contractnli.py` (seed 20260921). Also writes `checklist_hypotheses.json` (the 17 fixed hypotheses with short descriptions, ids nda-1..nda-20 with gaps, as shipped).

## Sampling and windows
Pool: test (123 docs) and dev (61 docs); first annotation set only. One item per (document, hypothesis), at most 2 items per document, round-robin over hypotheses (shuffled, seeded) to 24 items per label. Labels: Entailment=entailed, Contradiction=contradicted, NotMentioned=not_mentioned.
- entailed / contradicted: window = contiguous run of the contract's own annotated sentence spans starting at the first evidence span through the last one (candidates whose evidence does not fit in about 1300 characters are dropped, so ALL evidence is inside the window), then grown with neighbouring sentences alternately left and right up to about 1200 characters. Nothing is inserted.
- not_mentioned: the document has no evidence for the hypothesis. The window is centred on a randomly chosen evidence sentence for a DIFFERENT hypothesis in the same document (so it is topical contract language, not boilerplate) and grown the same way; by construction it holds no evidence for the target hypothesis.
- Only mechanical cleaning: whitespace runs (incl. newlines) collapsed to a single space. Windows start and end at annotated span boundaries (a span is a sentence or list item, so some windows end mid-sentence at a list item). State length max 1238 chars.

## Counts
72 items: 24 entailed, 24 contradicted, 24 not_mentioned; all 17 hypotheses appear (per-hypothesis counts vary 2 to 6; contradictions are only present in ~10 hypotheses in the test/dev data, mostly nda-1, nda-2, nda-7, nda-17, nda-20).

## Caveats
- WINDOWS AROUND EVIDENCE ARE EASIER THAN WHOLE DOCUMENTS: the model is handed the relevant passage, whereas the real task requires finding it in a full NDA (thousands of tokens). Scores here overstate document-level performance.
- Not_mentioned windows are built to be non-trivial but a window that lacks the topic is easier to call than a whole document, and an absence claim is only guaranteed for the window's document at large, not that the window is on-topic.
- Entailment/contradiction in ContractNLI is document-level and often depends on exceptions and definitions elsewhere in the contract; a window can be locally ambiguous. Some hypotheses (nda-2 "only technical information", nda-1) yield contradiction by simple absence of restriction, which is a label convention. Annotation quality: crowd/lawyer-annotated with single annotation set in test; some noise.
- Contamination: public dataset (2021) on GitHub/HF; contracts are public SEC/web NDAs; models may have seen it. The instruction text adds label definitions of my own; the hypotheses are verbatim.
