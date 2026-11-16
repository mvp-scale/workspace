"""inject_spans (T150 P1b): mutation test for a literal-span checker. Does the checker catch a span that no longer points at the text the item says it holds?
Items come from the fact extractors (facts_for amounts, dates, names, triples; span_rules) on N golden stories, in the pool_build it() shape: {tool, version, kind, span:[s,e], text, ...}. Mutants, each a copy of one item with exactly one defect: shift start +-1/+-3, shift end +-1/+-3, truncate (end-1, or end cut to half), swap one character of the stored text, point at the same length in a different sentence, end beyond len(text), start negative, swapped s>e. A mutant counts only if its slice really differs from the stored text (or is out of range); ineffective ones are dropped and counted.
Checker is pluggable: --checker module:function, signature check_literal(items, text) -> list of flags (each flag a dict with key "i" = index of the item in `items`; any non-empty return for a single-item call means flagged). The reference one below compares each item's stored text with text[s:e] and checks 0 <= s < e <= len(text). Note (planner, confirmed): inside facts_for the item text is built from the same slice, so a check there cannot fail; the real value is as a consumer-side check on items the consumer holds, which is what this tests.
Pass: flagged share of mutants = 100% and false alarms on the unmutated originals = 0. Exit 0 pass, 1 fail, 2 bad input.
    CUDA_VISIBLE_DEVICES="" /workspace/models/embed-zs/.venv/bin/python validate/inject_spans.py [--stories 3] [--min-mutants 200] [--checker module:function] [--synthetic]   (from projects/world-state)  -> runs/pulse/validate/inject_spans.json"""
import os, sys, json, re, random, argparse, importlib, pathlib
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
WS = pathlib.Path(__file__).resolve().parents[1]; OUTD = WS / "runs/pulse/validate"
def span_of(it): return (it["span"][0], it["span"][1]) if "span" in it else (it["s"], it["e"])
def check_literal(items, text):
    """Reference: stored text must equal text[s:e], and 0 <= s < e <= len(text). Returns [{"i": idx, "why": ...}] for each failing item."""
    bad = []
    for i, it in enumerate(items):
        try: s, e = span_of(it)
        except Exception: bad.append({"i": i, "why": "no span"}); continue
        if not (isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text)): bad.append({"i": i, "why": "span out of range"})
        elif it.get("text") != text[s:e]: bad.append({"i": i, "why": "stored text differs from slice"})
    return bad
def load_checker(spec):
    if not spec: return check_literal
    mod, fn = spec.split(":"); sys.path.insert(0, str(WS)); return getattr(importlib.import_module(mod), fn)
def setspan(it, s, e):
    d = json.loads(json.dumps(it))
    if "span" in d: d["span"] = [s, e]
    else: d["s"], d["e"] = s, e
    return d
def sentence_bounds(text): return [m.span() for m in re.finditer(r"[^.!?]+[.!?]*\s*", text)]
def mutants(it, text, rng):
    s, e = span_of(it); n = len(text); out = []; L = e - s
    for d in (1, 3):
        out += [("start+%d" % d, setspan(it, s + d, e)), ("start-%d" % d, setspan(it, s - d, e)), ("end+%d" % d, setspan(it, s, e + d)), ("end-%d" % d, setspan(it, s, e - d))]
    out += [("truncate_half", setspan(it, s, s + max(L // 2, 1))), ("end_beyond_text", setspan(it, s, n + 5)), ("start_negative", setspan(it, -2, e)), ("swapped", setspan(it, e, s))]
    t = it.get("text") or ""
    if t:
        k = rng.randrange(len(t)); c = rng.choice([x for x in "abcdefghijklmnopqrstuvwxyz0123456789" if x != t[k].lower()]); d = json.loads(json.dumps(it)); d["text"] = t[:k] + c + t[k + 1:]; out.append(("swap_char", d))
    sb = sentence_bounds(text); here = next((i for i, (a, b) in enumerate(sb) if a <= s < b), None)
    if here is not None and len(sb) > 1:
        j = rng.choice([i for i in range(len(sb)) if i != here]); a2 = sb[j][0]; out.append(("other_sentence", setspan(it, a2, min(a2 + L, n))))
    res = []
    for kind, m in out:
        ms, me = span_of(m)
        eff = not (0 <= ms < me <= n) or text[ms:me] != (m.get("text") or "")   # really wrong now?
        res.append((kind, m, eff))
    return res
def items_from_extractors(text, anchor):
    import facts_lib as FL, span_rules as SR
    items = []
    for f in FL.facts_for(text, anchor)[0]: items.append({"tool": "fact-finder", "version": "facts_lib", "kind": f["kind"], "span": [f["s"], f["e"]], "text": f["text"], "status": f["status"]})
    for x in SR.spans(text, anchor): items.append({"tool": "span-rules", "version": "span-rules-v0", "kind": x["kind"], "span": [x["s"], x["e"]], "text": text[x["s"]:x["e"]]})
    return items
SYN = ("Prices rose 12% on Monday, officials said. The ministry will spend $4.5 million by March 3. Three people were hurt in Paris. Shares fell 2.5 percent after the announcement.")
def synthetic():
    out = []
    for k, t in enumerate((SYN, SYN.replace("12%", "7%").replace("Paris", "Lagos"), "Officials in Rome said 40 shops closed on Friday. Output rose 3.1% in May, and two plants will reopen on June 9. Analysts expect $2 billion in losses.")):
        its = [{"tool": "syn", "version": "0", "kind": "x", "span": [m.start(), m.end()], "text": m.group(0)} for m in re.finditer(r"\d+%|\$[\d.]+ (?:million|billion)|\$2 billion|March 3|June 9|Three|two|Paris|Lagos|Rome|\d\.\d+ percent|3\.1%|40|Monday|Friday|May", t)]
        out.append(("syn%d" % k, t, its))
    return out
def run(checker, stories, min_mutants, seed):
    rng = random.Random(seed); orig_flags = 0; n_orig = 0; muts = 0; flagged = 0; dropped = 0; by = {}; misses = []
    for sid, text, items in stories:
        n_orig += len(items); orig_flags += len(checker(items, text))
        for idx, it in enumerate(items):
            for kind, m, eff in mutants(it, text, rng):
                if not eff: dropped += 1; continue
                muts += 1; hit = bool(checker([m], text)); flagged += hit; b = by.setdefault(kind, [0, 0]); b[0] += 1; b[1] += hit
                if not hit and len(misses) < 20: misses.append({"story": sid, "kind": kind, "item": m})
    return {"originals": n_orig, "false_alarms": orig_flags, "mutants": muts, "flagged": flagged, "dropped_ineffective": dropped, "flagged_share": round(flagged / max(muts, 1), 4), "by_kind": {k: {"n": v[0], "flagged": v[1]} for k, v in sorted(by.items())}, "misses": misses}
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--stories", type=int, default=3); ap.add_argument("--min-mutants", type=int, default=200); ap.add_argument("--checker"); ap.add_argument("--synthetic", action="store_true"); ap.add_argument("--seed", type=int, default=7); ap.add_argument("--out", default=str(OUTD / "inject_spans.json")); a = ap.parse_args()
    checker = load_checker(a.checker)
    if a.synthetic: stories = synthetic(); src = "synthetic text"
    else:
        os.chdir(WS); sys.path.insert(0, str(WS)); G = [json.loads(l) for l in open("runs/pulse/golden/articles.jsonl")]; stories = []
        for i, g in enumerate(G[:a.stories]):
            text = re.sub(r"\s+", " ", g["title"] + ". " + g["body"])[:12000]; stories.append(("g%d" % i, text, items_from_extractors(text, (g["date"] + "T00:00:00Z") if g.get("date") else None)))
        src = "golden stories g0..g%d (fact-finder + span-rules items)" % (a.stories - 1)
    r = run(checker, stories, a.min_mutants, a.seed); ok = r["mutants"] >= a.min_mutants and r["flagged"] == r["mutants"] and r["false_alarms"] == 0
    r.update({"checker": a.checker or "reference (inject_spans.check_literal)", "source": src, "min_mutants": a.min_mutants, "pass": ok, "bar": "100%% of >= %d effective mutants flagged and 0 false alarms on originals" % a.min_mutants, "label": "synthetic-or-real self-test of the harness; not a measurement of any extractor"})
    OUTD.mkdir(parents=True, exist_ok=True); os.makedirs(os.path.dirname(a.out), exist_ok=True); json.dump(r, open(a.out, "w"), indent=1)
    print("%s: %d originals, %d false alarms; %d effective mutants (%d dropped as ineffective), %d flagged = %.1f%%  -> %s" % (src, r["originals"], r["false_alarms"], r["mutants"], r["dropped_ineffective"], r["flagged"], 100 * r["flagged_share"], "PASS" if ok else "FAIL")); print("wrote", a.out); sys.exit(0 if ok else 1)
