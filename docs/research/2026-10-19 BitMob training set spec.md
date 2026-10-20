# BitMob training set: requirements

Date: 2026-10-19. Each requirement closes a problem already found. Checked by `newsreader/bitmob/audit_trainset.py` (R-numbers match its checks); *manual* items are checked by review. Reviewed by Fable twice (gaps closed in this version). Input filter recorded as D-0010.

## Input (what the model reads)

| # | Requirement | Problem it closes |
|---|---|---|
| R1 | `input` = `title + " — " + description[:250]`, exactly | D-0009 |
| R2 | Title and >= 60 characters of description. Headline-only items are not in the training set; in the live engine they are routed (fetch the description or full text) | 12/29 thin stories; D-0010 |
| R3 | English (common-word test, not character test) | non-English item in the feed |
| R4 | Outlet on the approved list (71 listed, 65 present in CC-News) or in the curated feed catalogue (`newsreader/catalogue.csv`) | ads, clickbait |
| R5 | No adverts (shopping-language screen); a flagged record stays only if the local news check (Clef, never a hosted model) scores >= 0.70 | power-bank sale read as prices down (MM3-0030) |
| R6 | No roundups or live blogs. Sports and other off-ontology news **stay**: they are true negatives | MM3-0047; review |
| R7 | No duplicate stories (same normalised title or same description start) | syndicated copies |

## Labels (what the teacher says)

| # | Requirement | Problem it closes |
|---|---|---|
| R8 | Labels made from exactly `input` (`label_input == input`) | F-0027, D-0009 |
| R9 | Answers stored as probabilities (not 0/1) | F-0025; method row 2 |
| R10 | All 159 attributes in **all three wordings** (engine wordings 0, 1 and the definition wording 2): 477 attribute answers, every vote kept | S-0002 (MV over 3 wordings), method row 2 |
| R11 | Training target rule recorded per record (`target_rule`); default MV-of-3 per S-0002; the final rule is chosen by Step 3/4 against humans | C-0009, C-0010, F-0022 |
| R12 | Topic (one of 49) and country asked **of the reader** and stored with `topic_source`/`country_source = "reader"` | C-0013 |
| R13 | Provenance: teacher, rules, prompt version, date labelled | which model produced the data |
| R14 | Hosted teacher (by the model registry's `hosted` flag): tokens logged per record | D-0008 |
| R15 | The reader's gate is a label, never a filter: gate-failed share reported and >= 10% | 6+ real news stories failed the gate (F-0029) |
| R16 | Near-cut flag: any attribute with mean probability within 0.05 of 0.65 is marked `near_cut` | F-0025 |
| R17 | Replicate reads: >= 2% of records read twice; flip rate reported | F-0025 |
| R18 | Paired full-text labels for >= 2% of records (random), for Step 5's correction of the headline loss | D-0009, F-0027 |

## Sampling, coverage and splits

| # | Requirement | Problem it closes |
|---|---|---|
| R19 | Every record carries `inclusion_prob` (random and mined alike) and `mined_for` when mined | method 4.2 (Horvitz-Thompson); C-0011 |
| R20 | Per-key positives (target rule) reported for train and test; keys under 100 listed as under-sized | F-0026; method 4.2 |
| R21 | Source and year stored; CC-News records carry `ccnews: true` | F-0027 domain shift |
| R22 | Test split follows Step 3's design (S-0003, C-0011): predicted positives + stratified negatives, >= 2 raters + adjudicator; each test record has `raters` (>= 2) and `adjudicated` | Step 3 |
| R23 | No duplicate group (title or description start) in both train and test | leakage |
| R24 | *Manual:* direction-check flags route records to raters; never auto-relabelled | MM3-0036, MM3-0044 |
| R25 | *Manual:* teacher chosen by Step 4 against humans, not by confidence or MM3 | F-0028, F-0029 |
| R26 | *Manual:* CC-News licence unknown: research and training use only until checked | F-0027 |
