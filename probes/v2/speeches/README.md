# Speeches (unlabelled, for windowed-analysis demo)
Rebuild: `/workspace/kev/.venv/bin/python build_speeches.py` (raw files in /workspace/data/sources/speeches/, retrieved 2026-09-21).

| slug | source | public-domain basis |
|---|---|---|
| gettysburg-address | https://avalon.law.yale.edu/19th_century/gettyb.asp | 1863, Lincoln d. 1865 |
| fdr-first-inaugural | https://avalon.law.yale.edu/20th_century/froos1.asp | US federal-government work (17 USC 105) |
| antony-funeral-oration | https://www.gutenberg.org/cache/epub/1522/pg1522.txt (Julius Caesar 3.2) | Shakespeare d. 1616 |

Paragraphs: source paragraphs (Avalon: one per line; Gettysburg: one). For Antony, each contiguous Antony speech block is a paragraph, with verse lines joined by spaces; other speakers' lines and stage directions are dropped (blocks run from "Friends, Romans, countrymen" to "Take thou what course thou wilt!"; the last block follows the citizens' exit).
Sentence splitter (deterministic): collapse whitespace; split after `.`, `!` or `?` (plus an optional closing quote) followed by whitespace and an uppercase letter (optionally after an opening quote). Verse lines mean Antony "sentences" may span capitalised line breaks joined without punctuation; no abbreviation handling. No labels added.
