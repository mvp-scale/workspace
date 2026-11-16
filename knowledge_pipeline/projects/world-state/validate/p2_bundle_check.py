"""p2_bundle_check (T151 P2): evidence bundles must equal the change-lexicon hits on the same text. Rule from the plan: 'bundles match the lexicon hits exactly on the same text', and a bundle's change span is valid (text[s:e] equals the word), inside its sentence span, and carries a factuality tag.
Hits: lexicon_hits(doc) mirrors the change-lexicon loop of extract.py:62-71 (tokens whose lemma is in extract.LEX and pos VERB or NOUN with a nsubj/nsubjpass/dobj child or an in/of prep object; imported from extract.py, so the lexicon cannot drift; the loop itself is copied, and --selftest runs extract.work on the same sentences to prove the copy agrees). It is uncapped; extract.py keeps only the first 20 per story, so a story with more than 20 hits is reported as 'truncated_in_extract' (a bundle count above extract's is not an error). After P2a factors the loop into sentence_tags(doc), point --hits-from at it (module:function(text)->list of hit dicts).
Default compares bundles with the NON-negated hits (plan wording); --include-negated compares with all hits. A bundle on a negated hit is 'extra'.
Input (--bundles): jsonl, one row per story: {"id", "text", "bundles": [{"condition", "span": [s,e], "text"?, "sentence": [s,e], "factuality": tag, ...}]}. Match key is (condition, s, e). Output: exact matches, missing (hit without bundle), extra (bundle without hit), per-check failures (span_literal, in_sentence, factuality_present), coverage (stories with at least 1 bundle). Pass: missing = extra = 0 and every check clean. Exit 0 pass, 1 fail, 2 bad input or not run.
    /workspace/models/embed-zs/.venv/bin/python validate/p2_bundle_check.py --bundles FILE [--include-negated] [--hits-from module:function]   -> runs/pulse/validate/p2_bundle_check.json
    /workspace/models/embed-zs/.venv/bin/python validate/p2_bundle_check.py --selftest     (synthetic cases plus 2 real sentences through extract.py; CPU, no network; writes runs/pulse/validate/p2_bundle_check_selftest.json)   (from projects/world-state)"""
import os, sys, json, argparse, importlib, pathlib
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
WS = pathlib.Path(__file__).resolve().parents[1]; OUTD = WS / "runs/pulse/validate"; sys.path.insert(0, str(WS)); sys.path.insert(0, str(WS / "validate"))
from inject_spans import check_literal
TAGS = {"asserted", "reported", "denied", "request", "decision", "planned", "predicted", "question", "unknown"}
def lexicon_hits(doc, LEX):
    ch = []
    for t in doc:
        lm = t.lemma_.lower()
        if lm in LEX and (t.pos_ == "VERB" or t.pos_ == "NOUN"):
            thing = None
            for c in t.children:
                if c.dep_ in ("nsubj", "nsubjpass", "dobj"): thing = c
                elif c.dep_ == "prep" and c.lower_ in ("in", "of"): thing = next((g for g in c.children if g.dep_ == "pobj"), thing)
            if thing is not None: ch.append({"condition": LEX[lm][0], "direction": LEX[lm][1], "word": t.text, "thing": thing.lemma_.lower(), "span": [t.idx, t.idx + len(t.text)], "negated": any(c.dep_ == "neg" for c in t.children)})
    return ch
def bspan(b): return tuple(b.get("span") or b.get("change_span") or (b.get("s"), b.get("e")))
def check(text, hits, bundles, include_negated=False):
    want = {(h["condition"], h["span"][0], h["span"][1]): h for h in hits if include_negated or not h["negated"]}
    have = {}; dup = 0
    for b in bundles:
        k = (b.get("condition"),) + bspan(b)
        if k in have: dup += 1
        have[k] = b
    exact = sorted(set(want) & set(have)); missing = sorted(set(want) - set(have)); extra = sorted(set(have) - set(want)); fails = {"span_literal": [], "in_sentence": [], "factuality_present": []}
    for k, b in have.items():
        s, e = bspan(b); item = {"span": [s, e], "text": b["text"] if "text" in b else text[s:e] if isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text) else None}
        if check_literal([item], text) or (k in want and text[s:e] != want[k]["word"]): fails["span_literal"].append(k)
        sn = b.get("sentence")
        if not (sn and isinstance(s, int) and sn[0] <= s and e <= sn[1]): fails["in_sentence"].append(k)
        if b.get("factuality") not in TAGS: fails["factuality_present"].append(k)
    return {"hits": len(want), "hits_negated_skipped": sum(1 for h in hits if h["negated"]) if not include_negated else 0, "bundles": len(have), "duplicate_bundles": dup, "exact": len(exact), "missing": [list(k) for k in missing], "extra": [list(k) for k in extra], "check_failures": {k: [list(x) for x in v] for k, v in fails.items()}, "truncated_in_extract": len(hits) > 20}
def verdict(r): return r["missing"] == [] and r["extra"] == [] and not any(r["check_failures"].values()) and r["duplicate_bundles"] == 0
def get_hits_fn(spec):
    if spec: m, f = spec.split(":"); return getattr(importlib.import_module(m), f)
    import spacy, extract as E; nlp = spacy.load("en_core_web_sm"); return lambda text: lexicon_hits(nlp(text), E.LEX)
def run(path, include_negated, hits_from):
    hf = get_hits_fn(hits_from); rows = [json.loads(l) for l in open(path)]; per = []; tot = {"hits": 0, "bundles": 0, "exact": 0, "missing": 0, "extra": 0, "stories_with_bundle": 0, "stories_failing": 0, "stories": len(rows)}
    for r in rows:
        c = check(r["text"], hf(r["text"]), r.get("bundles", []), include_negated); ok = verdict(c)
        for k in ("hits", "bundles", "exact"): tot[k] += c[k]
        tot["missing"] += len(c["missing"]); tot["extra"] += len(c["extra"]); tot["stories_with_bundle"] += c["bundles"] > 0; tot["stories_failing"] += not ok
        if not ok: per.append({"id": r.get("id"), **c})
    tot["pass"] = tot["stories_failing"] == 0; tot["rule"] = "bundles match the lexicon hits exactly on the same text" + (" (negated included)" if include_negated else " (non-negated hits)"); tot["failing_stories"] = per[:100]; tot["coverage_note"] = "stories with >= 1 bundle %d of %d; report beside every number, no gain is claimed" % (tot["stories_with_bundle"], tot["stories"])
    return tot
def selftest():
    res = {}; T = "Prices rose sharply. The mine did not close. Rents fell in Spain."
    sp = lambda w: [T.index(w), T.index(w) + len(w)]
    h = [{"condition": "rising", "direction": "up", "word": "rose", "thing": "price", "span": sp("rose"), "negated": False}, {"condition": "disrupted", "direction": "none", "word": "close", "thing": "mine", "span": sp("close"), "negated": True}, {"condition": "falling", "direction": "down", "word": "fell", "thing": "rent", "span": sp("fell"), "negated": False}]
    for a in h: assert T[a["span"][0]:a["span"][1]] == a["word"], a
    bd = lambda hh, tag="asserted", sent=None: {"condition": hh["condition"], "span": hh["span"], "text": hh["word"], "sentence": sent or [0, len(T)], "factuality": tag}
    good = [bd(h[0]), bd(h[2])]
    res["exact_match"] = c1 = check(T, h, good); assert verdict(c1) and c1["exact"] == 2 and c1["hits_negated_skipped"] == 1
    res["missing_one"] = c2 = check(T, h, good[:1]); assert len(c2["missing"]) == 1 and not verdict(c2)
    res["extra_negated"] = c3 = check(T, h, good + [bd(h[1])]); assert len(c3["extra"]) == 1 and not verdict(c3)
    res["include_negated"] = c4 = check(T, h, good + [bd(h[1])], include_negated=True); assert verdict(c4) and c4["exact"] == 3
    bad = dict(bd(h[0])); bad["span"] = [bad["span"][0] + 1, bad["span"][1] + 1]; res["shifted_span"] = c5 = check(T, h, [bad, good[1]]); assert len(c5["missing"]) == 1 and len(c5["extra"]) == 1
    res["no_factuality"] = c6 = check(T, h, [dict(good[0], factuality=None), good[1]]); assert c6["check_failures"]["factuality_present"] and not verdict(c6)
    res["sentence_misses_span"] = c7 = check(T, h, [dict(good[0], sentence=[12, 30]), good[1]]); assert c7["check_failures"]["in_sentence"] and not verdict(c7)
    res["synthetic"] = "7 cases asserted green"
    # real sentences through extract.py's own work(): the mirror must give the same hits as extract.py's conditions items
    try:
        import extract as E, spacy; os.chdir(WS); E.init(); nlp = E.nlp; txt = "Rents rose across the city. Officials did not cut the fares in Leeds, and flights were delayed in Spain."; rec = E.work({"row": 0, "domain": "", "text": txt, "title": "", "url": "", "date": None, "description": ""})
        mine = lexicon_hits(nlp(rec["text"]), E.LEX); theirs = rec["conditions"]["items"]; same = [{k: x[k] for k in ("condition", "direction", "word", "thing", "span", "negated")} for x in mine[:20]] == theirs
        res["extract_mirror"] = {"text": rec["text"], "extract_items": len(theirs), "mirror_items": len(mine), "identical": same}; assert same and len(mine) >= 2
        bundles = [{"condition": x["condition"], "span": x["span"], "sentence": [s, e], "factuality": tag} for x in mine if not x["negated"] for s, e, tag in rec["function"]["sentences"] if s <= x["span"][0] < e]
        c = check(rec["text"], mine, bundles); res["real_exact"] = c; assert verdict(c)
        c8 = check(rec["text"], mine, bundles[1:]); res["real_drop_one"] = c8; assert not verdict(c8) and len(c8["missing"]) == 1
    except Exception as ex: res["extract_mirror"] = {"ran": False, "error": repr(ex)[:300]}; return res, False
    return res, True
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--bundles"); ap.add_argument("--include-negated", action="store_true"); ap.add_argument("--hits-from"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--out"); a = ap.parse_args(); OUTD.mkdir(parents=True, exist_ok=True)
    if a.selftest:
        try: res, ok = selftest()
        except AssertionError as ex: import traceback; traceback.print_exc(); res, ok = {"assertion_failed": True}, False
        json.dump(res, open(a.out or OUTD / "p2_bundle_check_selftest.json", "w"), indent=1, default=str); print("selftest:", "PASS" if ok else "FAIL", "| synthetic cases:", res.get("synthetic"), "| extract mirror:", {k: res["extract_mirror"].get(k) for k in ("extract_items", "mirror_items", "identical")} if "extract_mirror" in res else None); sys.exit(0 if ok else 1)
    if not a.bundles or not os.path.exists(a.bundles): print("NOT RUN: need --bundles FILE (jsonl of {id, text, bundles}); P2 code writes it"); sys.exit(2)
    r = run(a.bundles, a.include_negated, a.hits_from); json.dump(r, open(a.out or OUTD / "p2_bundle_check.json", "w"), indent=1); print("%d stories, hits %d, bundles %d, exact %d, missing %d, extra %d; failing stories %d; %s -> %s" % (r["stories"], r["hits"], r["bundles"], r["exact"], r["missing"], r["extra"], r["stories_failing"], r["coverage_note"], "PASS" if r["pass"] else "FAIL")); sys.exit(0 if r["pass"] else 1)
