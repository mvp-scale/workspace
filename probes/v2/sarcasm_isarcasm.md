# sarcasm_isarcasm.jsonl and sarcasm_headlines.jsonl

Builder: `build_sarcasm_isarcasm.py` (seed 20260921; produces both files). Retrieved 2026-09-21.

## sarcasm_isarcasm (primary)
- Source: iSarcasmEval, SemEval-2022 Task 6, English task A **test** split, `test/task_A_En_test.csv`. https://github.com/iabufarha/iSarcasmEval . Licence: MIT (repo LICENSE).
- Citation: Abu Farha, Oprea, Wilson, Magdy (2022). "SemEval-2022 Task 6: iSarcasmEval, Intended Sarcasm Detection in English and Arabic." SemEval-2022.
- Sampling: dedupe, keep 15-300 chars, seeded random sample of 40 sarcastic + 40 not sarcastic (source has 1400 rows, 200 sarcastic; so it is balanced by downsampling). 80 items.
- Cleaning: whitespace collapsed only. Text verbatim (tweets, emoji kept).
- Counts: yes 40, no 40.
- Caveats: labels are the tweet authors' intent as recorded by the dataset creators, but the test labels are noisy for a one-line reading; many sarcastic tweets depend on context, hashtags removed or world knowledge (e.g. "Who says the NHS isn't a wonderful thing?" is labelled no). The question "means the opposite of the literal words" is narrower than sarcasm (irony, understatement, rhetorical questions can be labelled sarcastic without a literal opposite). Expect a ceiling well below 100%.
- Contamination: public since 2022; the test set is in the public repo and may appear in web crawls.

## sarcasm_headlines (fallback, also produced)
- Source: News Headlines Dataset for Sarcasm Detection v2 (Misra & Arora), HF `raquiba/Sarcasm_News_Headline`, `test.json`. Licence: CC0-1.0 per the original Kaggle release (the HF card states none; verify before redistribution).
- Citation: Misra & Arora (2023). "Sarcasm Detection using News Headlines Dataset." AI Open 4; Misra & Grover (2021), Sculpting Data for ML.
- **Labels come from the publication source (The Onion = 1, HuffPost = 0), not from human intent annotation.** Onion headlines are satire, so the question "satirical or sarcastic" is a fair proxy, but some HuffPost headlines are ironic and some Onion headlines read as straight news.
- Sampling: same procedure, 40 yes + 40 no, headlines 15-300 chars. Headlines in this copy are lowercased.
- Contamination: widely used training set for sarcasm classifiers; the test split is from the same distribution as the train split (stylistic Onion cues such as "area man" make it easier than true intent detection).
