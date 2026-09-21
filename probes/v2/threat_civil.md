# threat (Jigsaw Civil Comments)

- Files: threat_civil.jsonl (100 rows: 50 yes / 50 no); builder build_threat_civil.py (seed 20260921).
- Source: https://huggingface.co/datasets/google/civil_comments (CC0-1.0), retrieved 2026-09-21. Train, validation and test pooled.
- Citation: Borkan, Dixon, Sorensen, Thain, Vasserman. Nuanced Metrics for Measuring Unintended Bias with Real Data for Text Classification. WWW 2019 companion; Jigsaw/Conversation AI Civil Comments.
- Labels: yes = published threat score >= 0.5 (share of raters); no = threat == 0 AND toxicity == 0. Availability: 4725 rows with threat >= 0.5, 4063 usable unique (15-300 chars); 886072 usable clean negatives. Yes items are therefore not rare enough to limit balance at 50/50; sampled 50 each with seed.
- Caveats (label noise, 20-item sample): about 6 of 10 sampled yes items are hostile or violent wishes about third parties or public figures ("wish this ... would hurry up and die", "Lock them up!", a stat about guns) rather than a threat to the listener, and a couple are barely threatening. The question says "the listener" but the source label is generic "threat" from raters; treat as a noisy proxy. Negatives (clean) looked correct. Negatives are also much calmer than positives (toxicity 0), so easy tone cues exist.
- Contamination: widely used Jigsaw data; possibly seen in training.
