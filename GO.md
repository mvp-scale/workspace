# GO — session handoff

Written 2026-10-19 21:00. Overwritten at each handoff.

## Tone
- Follow the decision rule in `CLAUDE.md` and D-0006: act inside the method, record concerns, stop only for raters, engine changes, or new spend the user has not approved.
- Every claim cites a ledger item, a pinned file, or an MM3 run id. Predict before each run, score after. Short replies, bottom line first.

## Start of session
1. `node tools/ledger.mjs board` and `node tools/ledger.mjs score`.
2. Read the plan: `docs/research/2026-10-19 BitMob plan.md` (validated MM3-0051..0053).
3. Continue at the first open step below.

## Goal (user, 2026-10-19)
BitMob = CPU models, one per World engine read layer (story type, scope/focus, topic, country, 78 condition keys) from headline + description (~250 chars, D-0009); no GPU, a few GB RAM, under 100 ms/article (D-0007); 65-70%+ detection, proven against human labels. Ontology: `exports/world-engine-ontology.yaml`. Person states, decisions, resources are computed by engine rules, not read (C-0013).

## Where things stand
- Fable Steps 1-2 closed; Step 3 open, blocked on raters (S-0003).
- Training-set spec R1-R26 + checker: `docs/research/2026-10-19 BitMob training set spec.md`, `newsreader/bitmob/audit_trainset.py` (D-0010).
- Builder: `newsreader/bitmob/build_trainset.py` (Jev teacher, tokens logged). Pilot 1: 1,000 records, 10.9 min, $0.87, audit 20/23 then builder bugs fixed (F-0030). Data `data/trainset/pilot1.jsonl`.
- Rare keys: 1 of 16 priority keys >= 30 positives at random (F-0030) -> mining needed.
- Jev approved for article text (D-0008): $0.042 per million input tokens, output free (registry). ~92 records/min.
- Engine logs every read: `data/world-engine/reads.jsonl`. Reader check write-up: `docs/research/2026-10-19 World engine reader check.md`.
- CC-News downloaded: `data/ccnews/raw/` (708k; 70,546 after D-0010 filter). Licence unknown: research/training only.
- Transfer tarball: `transfer/workspace-2026-10-19.tar` (24.7 GB, git-ignored).

## Next steps (plan table)
1. Mine rare keys in CC-News (row 7): pass = hit rate >= 5x random for >= 10 of 16 keys; cap 16k candidates / $16.
2. Full training set (10-20k records), audit 0 failures.
3. Per-element CPU models (row 8): shared fine-tuned encoder + heads vs TF-IDF and potion; agreement with Jev only.
4. Learning curves (row 10).
5-7. Human reference (Step 3), teacher choice (Step 4), correction/thresholds/monitoring (Steps 5, 9, 11, 12).

## Decisions for the user
1. Raters: two raters + adjudicator (blocks step 5).
2. Engine gate: should gate-failed stories still move the world?
3. Live input filter: apply D-0010 to the live feed?
4. CC-News licence check before any commercial use.
