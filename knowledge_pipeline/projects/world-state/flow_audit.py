"""Trust audit across all BitMob models. Reads result files only (not the ledger) and returns the matrix for the Training tab.
One row per model, one column per stage of the rollout method. Each cell: s = ok | part | no | none, t = plain words, src = the file the words come from.
A stage is 'ok' only when a file shows it; 'part' means shown but weak or not independent; 'no' means tried and failed; 'none' means not started.
    from flow_audit import audit"""
import json, os
P = "runs/pulse/"
def J(f):
    try: return json.load(open(P + f))
    except Exception: return None
def c(s, t, src=None): return {"s": s, "t": t, "src": src}
import re, datetime
def src_files(src):
    """Files a cell's words come from: names in `src`, looked up under runs/pulse/ then runs/ (r0-r2 expands to r0, r1, r2)."""
    out = []
    for tok in re.split(r"[,;]\s*", src or ""):
        tok = tok.split("#")[0].strip()
        if not tok or tok == "this tab": continue
        if tok == "finetune3_r0-r2.json": toks = [f"finetune3_r{i}.json" for i in range(3)]
        else: toks = [tok]
        for t in toks:
            for base in (P, "runs/", ""):
                if os.path.exists(base + t): out.append(base + t); break
    return out
def stamp_rows(rows):
    """Adds `ts` (UTC, file modified time) and `file` to each cell, and `changed` = {ts, file, cell} to each row: the latest result file behind any cell."""
    for r in rows:
        best = None
        for i, x in enumerate(r["cells"]):
            fs = [f for f in src_files(x.get("src")) if not f.endswith("model_rollout.json")]   # the shared rollout notes file is edited for every row; not a result
            if not fs: continue
            m = max(fs, key=os.path.getmtime); ts = datetime.datetime.fromtimestamp(os.path.getmtime(m), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            x["ts"] = ts; x["file"] = os.path.basename(m)
            if best is None or ts > best["ts"]: best = {"ts": ts, "file": os.path.basename(m), "col": i}
        r["changed"] = best
def audit():
    ft = J("finetune_cpu2.json"); r = [J(f"finetune3_r{i}.json") for i in range(3)]; cmp = J("compare_v6b.json"); nd = J("neardup.json"); ll = J("learn_loop.json"); lc = J("lap2_checks.json")
    runs = [x["sealed"] for x in [ft] + r if x]; base = ft["sparse_default_sealed"]; NOISE = {"topic": 0.009, "story_type": 0.007, "presence_f1": 0.019}
    rng = lambda k: (min(x[k] for x in runs), max(x[k] for x in runs))
    def repeat(k):
        lo, hi = rng(k); sp = hi - lo; return c("ok" if sp <= 2 * NOISE[k] else "part", f"{len(runs)} runs, {lo:.3f} to {hi:.3f} (spread {sp:.3f}; seed noise {NOISE[k]})", "finetune_cpu2.json, finetune3_r0-r2.json")
    def beats(k, label):
        d = max(x[k] for x in runs) - base[k]; lo = min(x[k] for x in runs) - base[k]
        return c("ok" if lo > 2 * NOISE[k] else "part", f"{label}: encoder {rng(k)[0]:.3f}-{rng(k)[1]:.3f} vs old sparse head {base[k]:.3f} (gain {lo:+.3f} to {d:+.3f}); agreement with Sonnet", "finetune_cpu2.json#sparse_default_sealed")
    hl = ll["heads"] if ll else {}
    def loop(h):
        x = hl.get(h)
        if not x: return c("none", "no loop result", "learn_loop.json")
        lo, hi = x["delta_ci95"]; return c("ok" if lo > 0 else "no", f"sparse-head tuning loop: {x['delta']:+.3f} on sealed (95% range {lo:+.3f} to {hi:+.3f}); the encoder is not in the loop yet", "learn_loop.json")
    nodup = c("ok", f"{nd['cos_ge_0p95']} of {nd['sealed_items']} sealed items has a near-twin (cosine 0.95+) in the training text; {nd['exact_normalised_matches']} exact", "neardup.json") if nd else c("none", "not checked")
    live = lambda k, name: c("part" if abs(cmp[k]["diff"]) < 0.02 and cmp[k]["diff_ci95"][0] < 0 < cmp[k]["diff_ci95"][1] else "ok", f"vs the live head (v6b-student) on {name}: {cmp[k]['diff']:+.4f}, 95% range {cmp[k]['diff_ci95'][0]:+.3f} to {cmp[k]['diff_ci95'][1]:+.3f}: no measurable difference" if cmp else "not compared", "compare_v6b.json") if cmp else c("none", "not compared")
    cols = ["Data", "In/out defined", "Trained", "Curve", "Beats old head", "Beats live head", "No leakage", "Outside truth", "Self-improving loop", "Repeats", "v1"]
    G = lambda: c("none", "not started")
    ks = [J(f'heademb_kinds_s{i}.json') for i in (7, 11, 13)]; ks = [k for k in ks if k]
    kmin, kmax = min(k['sealed']['micro_f1'] for k in ks), max(k['sealed']['micro_f1'] for k in ks); dmin, dmax = min(k['best_dev'] for k in ks), max(k['best_dev'] for k in ks); kb, k3 = ks[0]['sealed']['baseline_most_common_kind'], ks[0]['sealed']['baseline_top3_kinds']
    zs = [J(f'heademb_size_s{i}.json') for i in (7, 11, 13)]; zs = [z for z in zs if z]
    zmin, zmax, zb = min(z['best_dev'] for z in zs), max(z['best_dev'] for z in zs), zs[0]['majority_baseline_dev']
    ae = J('anchor_encoder_vs_v6b.json')['sets']
    rows = [
     {"model": "Domain (topic, 49)", "cells": [c("ok", "36,092 Sonnet-labelled items", "runs/label_store"), c("ok", "headline + teaser, 64 word pieces -> 1 of 49", "model_rollout.json"), c("ok", "4 encoder runs", "finetune_cpu2.json"), c("ok", "dev score every half epoch, chosen epoch circled", "this tab"), beats("topic", "topic"), live("topic_top2", "top-2 topic"), nodup,
        c("ok", f"MN-DS human topic labels, top-2: encoder {ae['fresh']['encoder_top2']:.3f} and {ae['fresh2']['encoder_top2']:.3f} vs live head {ae['fresh']['v6b_top2']:.3f} and {ae['fresh2']['v6b_top2']:.3f} on the two fresh sets; differences {ae['fresh']['paired_diff']:+.3f} and {ae['fresh2']['paired_diff']:+.3f}", "anchor_encoder_vs_v6b.json"), loop("topic"), repeat("topic"), c("part", "trained, not adopted: it does not beat the live head", "model_rollout.json")]},
     {"model": "Function (story type, 4)", "cells": [c("ok", "36,092 Sonnet-labelled", "runs/label_store"), c("ok", "same input -> 1 of 4", "model_rollout.json"), c("ok", "second head on the same encoder", "finetune_cpu2.json"), c("ok", "same chart", "this tab"), beats("story_type", "story type"), live("story_type", "story type"), nodup,
        c("no", "the outside set (CheckThat) measures fact vs opinion, not our four types; contract unconfirmed", "field_table.json#story_type"), loop("story_type"), repeat("story_type"), c("part", "trained, not adopted", "model_rollout.json")]},
     {"model": "Condition (present)", "cells": [c("ok", "36,092 Sonnet-labelled, 11.9% positive", "lap2_checks.json"), c("ok", "same input -> yes/no", "model_rollout.json"), c("ok", "third head on the same encoder", "finetune_cpu2.json"), c("ok", "same chart", "this tab"), c("part", f"F1 {rng('presence_f1')[0]:.3f}-{rng('presence_f1')[1]:.3f} vs old head {base['presence_f1']:.3f}; the range crosses zero (note on T56)", "finetune_cpu2.json#interval_vs_recorded_sparse"), c("none", "not compared with a live head", None), nodup, c("none", "no outside set", None), G(), repeat("presence_f1"), c("part", "weak: F1 about 0.66, always-yes scores 0.20", "lap2_checks.json#m3_condition_head")]},
     {"model": "Condition (per kind)", "cells": [c("ok", "4,286 items with kinds; 19 kinds with 100+ items", "runs/pulse/heademb_kinds.json"), c("part", "says which kind, given a condition is present; it was never trained on items without one", "head_on_embeddings.py"), c("part", "small head on the frozen fine-tuned encoder, not a fine-tune of its own", "heademb_kinds_s7.json"), c("ok", "dev micro-F1 every 5 epochs, 3 seeds", "heademb_kinds_s7.json"),
        c("ok", f"sealed {kmin:.3f}-{kmax:.3f} vs most-common-kind {kb:.2f} and top-3 kinds {k3:.2f} (141 sealed items with a condition)", "heademb_kinds_s7.json#sealed"), c("none", "no live per-kind head compared", None), c("ok", "sealed ids excluded from the training list (head_on_embeddings.py line 13); sealed read once per seed", "head_on_embeddings.py"), c("none", "no outside set", None), G(),
        c("ok", f"3 seeds: sealed spread {kmax - kmin:.3f}, dev spread {dmax - dmin:.3f}; rerun of seed 7 reproduced the earlier 0.819", "heademb_kinds_s*.json"), c("part", "v1 candidate; agreement with Sonnet only", "model_rollout.json")]},
     {"model": "Area", "cells": [c("part", "triple route measured; independent support is rare (small parser 3.6% exact, 6.2% by embedding; transformer parser 4.5% and 7.6%, so the parser is not the main limit; GLiNER-entity keys add only 6 matches in 4,324 triples, T73; two of three elements match for 11.1% against 0.3% by chance, replicated at 11.1%, T74 and T75; about 10% of triples have 2+ independent supporters and 5% have 3+, mostly in big events, T76; mapped onto IPTC Media Topics the assignment is reproducible across publishers, 67% same term, against MN-DS human IPTC level 2 it is right 25-27% by embedding and 29.6% with a zero-shot rerank fused in, top-5 ceiling 54%, T80-T82)", "triple_pairs2.json"), c("part", "sentences -> triples -> buckets; no human names", "model_rollout.json"), c("part", "T84: a small head on frozen bge-small vectors, distilled from the IPTC term mapping over 36,092 Sonnet-labelled items; a candidate, not a v1", "t84/t84_area_head.json"), c("ok", "dev agreement with its own pseudo-labels per epoch, best epoch 13, early stop (T84)", "t84/t84_area_head.json"), G(), G(), G(), c("part", "MN-DS human level 2: head 0.231 and 0.216 exact, below the embedding mapping it learns from (0.282 and 0.253); paired difference -0.051 and -0.037, intervals below zero (T84)", "t84/t84_area_head.json"), G(), G(), G()]},
     {"model": "Capability", "cells": [c("none", "waits on Area"), c("part", "same route one level down", "model_rollout.json"), G(), G(), G(), G(), G(), G(), G(), G(), G()]},
     {"model": "Novelty", "cells": [c("part", "MN-DS human level 2 marks which items fall outside the IPTC depth-1 list (259 of 1,545 and 239 of 1,352); no labelled novelty set beyond that", "t85/t85_novelty.json"), c("part", "'matches no Area'; T85 used 'outside the Area vocabulary' as a first test", "model_rollout.json"), c("none", "no trained novelty model; scored the Area head and the embedding as novelty scores (T85)", "t85/t85_novelty.json"), G(), G(), G(), G(), c("no", "tried and failed: AUROC for out-of-vocabulary vs in-vocabulary items 0.50 and 0.47 for head confidence, 0.55 and 0.49 for embedding max-similarity; chance is 0.50 (T85)", "t85/t85_novelty.json"), G(), G(), G()]},
     {"model": "Understanding (triples)", "cells": [c("part", "no labels; scored on CaRB-style checks only", "spo_chains.py"), c("ok", "sentences -> triples", "model_rollout.json"), c("none", "rule-based on spaCy; no trained model"), G(), c("part", "37-45% fully correct; CaRB F1 0.40; recall weak", "ledger L1092, L1096"), G(), G(), c("part", "entity bake-off on Few-NERD (Wikipedia): Stanza 0.58 vs spaCy small 0.51", "t67/kaggle/ner_bakeoff.json"), G(), G(), G()]},
     {"model": "Size level", "cells": [c("ok", "4,458 items with a real level 0-3 (of 37,735); majority level is 50.5%", "runs/label_store/labels.jsonl"), c("ok", "same input -> level 0-3", "model_rollout.json"), c("part", "small head on the frozen fine-tuned encoder", "heademb_size_s7.json"), c("ok", "dev accuracy every 5 epochs, 3 seeds", "heademb_size_s7.json"),
        c("part", f"dev {zmin:.3f}-{zmax:.3f} vs majority level {zb:.3f}; dev split only", "heademb_size_s*.json"), c("none", "no live size head compared", None), c("ok", "sealed ids excluded from the training list; none read", "head_on_embeddings.py"), c("no", "the sealed set has no size-level labels, so there is no sealed or outside check", "runs/pulse/sealed/labels.jsonl"), G(),
        c("ok", f"3 seeds: dev spread {zmax - zmin:.3f}", "heademb_size_s*.json"), c("part", "v1 candidate on dev only; agreement with Sonnet", "model_rollout.json")]},
    ]
    pr = J('progress.json'); pred = next((x['now']['v'] for x in (pr or {}).get('rows', []) if x['label'].startswith('Predictions written')), 'unknown')
    works = ["Sealed set is clean: only 1 of 1,499 items has a near-twin in training (MM3-0631 also passed the leakage group on the T56 fine-tune; MM3-0632 on the head factory).",
             "Training is repeatable: 4 encoder runs land within 0.009 topic and 0.007 story type of each other, the same size as seed noise.",
             "The encoder beats the old sparse heads on topic and story type by more than noise. The per-kind Condition head (T69) holds up: sealed 0.81-0.83 against 0.10 for the most-common-kind baseline, across 3 seeds.",
             "The Condition (present) head, with its threshold lowered until dev recall reached 0.80, scores on the sealed set: precision 0.57 (0.50 to 0.63), recall 0.79, agreement 0.911 against 0.891 for always-no (T37; agreement with Sonnet). Adding an event-trigger filter does not help. " + "Every step is recorded: " + pred + " predictions have a score note (progress.json); the Training tab and live rows refresh from the poller every 3 minutes."]
    doesnt = ["The new encoder does NOT clearly beat the head that is live (v6b-student): against Sonnet the paired differences are within noise, and against MN-DS human labels it is 1.4 points worse on one set and 1.1 better on the other. Adopting it buys nothing on these scores.",
              "All encoder scores are agreement with Sonnet, not outside truth. Topic now has an outside check for both engines (MN-DS human labels, about 78-80% top-2); story type, condition, per-kind and size do not.",
              "Condition is weak (F1 about 0.66) and its gain over the old head is not established.",
              "Area, Capability, Novelty and Understanding have no trained model. The triple route is measured but limited by the entity extractor (T73 to T82 measured it on CPU; no model is trained yet).",
              "Two MM3 splits are open: T56 question 9 (resume order) and T49 questions 5-6 (reporting). My code reading says yes on all three; the local reader says no. A second reviewer needs your yes (hosted)."]
    stamp_rows(rows)
    return {"columns": cols, "rows": rows, "works": works, "doesnt": doesnt, "noise": NOISE}
