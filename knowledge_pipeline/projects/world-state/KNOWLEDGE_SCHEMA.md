# knowledge.json (schema v0, PROVISIONAL)

Written by `slow_consolidate.py` into `<trace>/slow_consolidate/knowledge.json` (sealed like the other five files: sha256 of the body, no clock inside). Read by `educate.py --auto`, `knowledge_yield.py`, `simulation/raw-units.py` (the `knowledge` block of the page feed) and `simulation/check-knowledge.py`. Owner yes L2936; weak numbers are shown, never blocked (L2901).

```
{
  "as_of":      "<consolidation time, ISO>",
  "window":     "<trace folder>",
  "articles":   <int>,                    # observations in this window (len of observations, not the store)
  "publishers": <int>,                    # distinct publishers in the window
  "counters": {                           # each: n = len(evidence); evidence = edge ids resolvable in "edges"
    "new":        {"n", "evidence": [edge id]},   # assertions first seen in the window
    "reinforced": {"n", "evidence": [edge id]},   # same normalised key from >= 2 independent publishers
    "contested":  {"n", "evidence": [edge id]},   # contradiction edges (both sides kept)
    "bridging":   {"n", "evidence": [capability id]}   # capabilities used by >= 2 Areas
  },
  "edges": { "<edge id>": {"subject", "predicate", "object", "kind", "strength",      # strength = independent.n
                           "publishers": [..], "fragments": [{"art", "pub", "sent"}],   # art = article id, pub = publisher, sent = source sentence
                           "anchor": <subject anchor id>,                               # fact-join fix (T158 L2954): slots are formed inside one anchor
                           "independent": {"n", "collapsed", "sources": [{"pub", "arts": [..], "fragments", "copies": [publishers whose copy collapsed], "how": ["story root" | "near-identical sentence" | "single fragment"]}]},
                           "slot": null | {"n", "merged_how", "min_pair_prob", "members": [{"edge": <raw edge id>, "key", "predicate", "object", "fragments_n"}]}} },   # a slot = one fact, >= 2 raw keys merged by fact_join.Scorer (consolidate.slot_merge)
  "contested":  [{"a": <edge id>, "b": <edge id>, "kind": "polarity|amount|status|direction", "earlier": {"edge", "day"}, "later": {"edge", "day"}, "reversal": bool, "note"}],   # a != b, same anchor, both dated, later >= earlier; status only when the later report reverses (dead -> alive)
  "join": {"mode", "threshold", "facts_raw", "slots", "merge_rate", "merged_slots", "anchors", "anchor_merges", "gated_pairs", "independence": {"fragments", "sources", "collapsed", "rule"}, "contested_kept", "contested_dropped": {"self_pair", "timeline", "unordered", "cross_anchor", "unmapped"}, "rule", "status"},
  "capabilities": [{"id", "label", "areas": [..], "areas_n", "bridging"}],   # bridging = areas_n >= 2
  "funnel": {"observations", "fragments", "sources", "facts_raw", "assertions", "reinforced", "contested", "capabilities", "bridging", "concepts"},   # sources = independent sources after syndication collapse; facts_raw = exact-key facts before the slot merge; assertions = slots
  "growth": [{"seq", "assertions", "reinforced", "contested"}],   # cumulative, one row per chain seq
  "yield":  {"pct_reinforced", "contested_per_100", "bridging", "answerable"},   # pct_reinforced = reinforced / assertions * 100; contested_per_100 per 100 articles
  "answer": {"question", "statements": [{"text", "refs": [edge id], "publishers": <int>}]},   # educate.py --auto, question marked auto
  "provisional": true
}
```

Fact join (T158 L2954, PROVISIONAL): `consolidate.py` groups exact-key facts by anchor (subject identity; concept-like subjects also by head word + containment), scores pairs with `fact_join.Scorer` (ECB+-trained, e5-small-v2 features, CPU; `fact-join-model.json`), gates pairs that can never be one fact (status class, direction, amount / date bucket, place id, disjoint objects) and merges by average linkage at the model threshold; `join.mode` names the scorer or the lemma fallback. Independence: fragments collapse into one source per story root or near-identical sentence (content-token Jaccard >= 0.7 on >= 8 tokens); a source is named by its earliest fragment's own publisher. Contested pairs come from the store's contradiction edges (`g4_align.contradict_edges`, time-aware status rule, negation inside the verb's clause) and are kept by `slow_consolidate.contested_pairs`. Gate: `simulation/check-knowledge.py` K8.

Rules: every `evidence` id and every `refs` id is a key of `edges`; every edge has at least one fragment with `art`, `pub` and `sent`; no clock or random value inside (two runs on the same input give the same sha256).

Offline fixtures for the gate: `simulation/fixtures/knowledge/{c1,mix}/trace/` (chain.jsonl, a/<seq>.json, run.json) and `simulation/fixtures/knowledge/areas.json`, built by `simulation/build-knowledge-fixture.py`.
