# emotion_fear and emotion_anger (GoEmotions)

- Files: emotion_fear.jsonl, emotion_anger.jsonl (100 rows each: 50 yes / 50 no); builder build_emotion_goemotions.py (seed 20260921).
- Source: GoEmotions raw config, https://huggingface.co/datasets/google-research-datasets/go_emotions ; licence Apache-2.0; retrieved 2026-09-21.
- Citation: Demszky, Movshovitz-Attias, Ko, Cowen, Nemade, Ravi. GoEmotions: A Dataset of Fine-Grained Emotions. ACL 2020.
- Labels: the dataset's own per-rater votes (raw rows are aggregated per example). Yes = at least 2 raters chose fear or nervousness (anger or annoyance). No = zero raters chose either target emotion AND at least 2 raters agree on some other label (neutral included); examples flagged example_very_unclear excluded.
- Available before sampling: fear 1203 positives / anger 5625; negatives 49548 / 41348.
- Sampling: 15-250 chars, whitespace collapsed, duplicates dropped, text verbatim (keeps [NAME] tokens). Positives random; negatives round-robin over agreed-label strata (diversity across emotions, neutral not dominant). Per-example rater votes are in provenance.notes.
- Caveats: Reddit text, single-rater-level noise; the "2 raters chose it" bar is lenient (the union of fear+nervousness or anger+annoyance votes, not necessarily the same one). In a 20-item random sample, fear had ~4 doubtful yes items (e.g. "Yikes that's cringe", "You seem horrible") and anger ~2 doubtful yes; negatives sometimes carry annoyance-like affect for the fear set ("I hate it"). Some negatives for anger are rude ("Yeah, well your just jealous...") yet no rater chose anger.
- Contamination: GoEmotions is a widely used public benchmark; models may have seen it.
