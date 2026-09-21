# manipulation_dialogue
- Source: MentalManip (Wang, Yang, Hassanpour, Vosoughi; ACL 2024), https://github.com/audreycs/MentalManip (file mentalmanip_con.csv, consensus version; also on HF audreyeleven/MentalManip). Paper: https://aclanthology.org/2024.acl-long.206
- Licence: CC BY-NC 4.0 (non-commercial). Retrieved 2026-09-21.
- Citation: Wang et al. 2024, "MentalManip: A Dataset For Fine-grained Analysis of Mental Manipulation in Conversations", ACL 2024 long papers, pp. 3747-3764.
- Question: "Does one speaker in this dialogue try to manipulate the other, that is, use language to influence, alter, or control the other's psychological state or perception for the manipulator's benefit?" (paper's definition of mental manipulation).
- Sampling (build_manipulation_dialogue.py, seed 20260921): consensus set only (all 3 annotators agree; 2915 dialogues); dialogues <=1400 chars after whitespace cleaning (no truncation was needed; longer ones excluded); manipulative rows require a non-empty consensus technique, stratified round-robin over technique strings; non-manipulative random. Counts: yes 40, no 40 (80 total). Technique and vulnerability labels are in provenance.notes.
- Caveats: dialogues are Cornell Movie-Dialogs excerpts (per the README, dialogues based on movie lines); the annotators' task is subjective (paper notes low-ish agreement), consensus mitigates but some "no" items may contain rude/coercive talk and some "yes" items are subtle. Whitespace cleaning only (speaker-tag lines kept as "Person1:/Person2:").
- Contamination: public GitHub/HF dataset since 2024; movie lines widely seen; models could have seen it. Not one of the excluded training sets.
- Not used: fallbacks (Persuasion for Good, SemEval-2020 T11) were unnecessary.
