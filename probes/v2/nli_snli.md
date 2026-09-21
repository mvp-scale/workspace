# nli_snli

- Source: SNLI, Bowman, Angeli, Potts, Manning (2015), "A large annotated corpus for learning natural language inference", EMNLP. https://nlp.stanford.edu/projects/snli/ ; fetched via Hugging Face `stanfordnlp/snli`.
- Licence: CC BY-SA 4.0. Retrieved 2026-09-21. Builder: build_nli_snli.py (seed 20260921).
- Sampling: validation split (label -1 dropped), pairs under 1200 chars, 30 random items per class = 90 items.
- Label mapping: entailment -> supports, contradiction -> contradicts, neutral -> neither. State: "Statement A: <premise>\nStatement B: <hypothesis>". Question: "How does statement B (the hypothesis) relate to statement A (the premise)?"
- Counts: contradicts 30, supports 30, neither 30.
- Caveats: SNLI premises are Flickr30k image captions and hypotheses were crowd-written; labels are the majority of 5 annotator votes (validation items with no majority are label -1 and excluded), yet some noise remains (about 1-2 percent disagreement with gold) and "contradiction" often relies on the assumption that both describe the same scene. Artefacts (e.g. negation words in hypotheses correlate with contradiction) mean high accuracy can partly come from hypothesis-only cues.
- Contamination: MNLI, which the models under test were trained on, is a close relative of SNLI (same genre of crowd-written hypotheses and same label scheme), so this set is not independent of their training data. SNLI itself is widely used in pretraining/fine-tuning mixes.
