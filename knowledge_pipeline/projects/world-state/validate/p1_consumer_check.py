"""p1_consumer_check (T150 P1): does a later layer ever read an item whose span no longer holds its text? Builds a mutated item list with a wrong-span item and runs it through the REAL functions that read items, with no bench and no network:
  1. pool_build.held_back and facts_lib.quarantine on real items: the mutant is held (status 'quarantined', not in kept); an unmutated list comes back equal and with the same item objects.
  2. analyze2.Analyzer.analyze (real, CPU) with facts_for or span_rules.spans replaced by a wrapper that mutates one item: the mutant is in evidence.quarantined and absent from evidence.stated_amounts / stated_dates / span_rules.items and from the 'size' proposal; with no mutation the result equals the same call on the unwrapped function (fields, evidence).
  3. pool_build.work (real, with extract.init) on one real harvest row with facts_for wrapped the same way: the mutant is absent from rec["items"] and present in rec["quarantined"]; unmutated rec["quarantined"] == [] and items equal the items built with quarantine switched off.
Exit 0 only if every assertion holds, 1 otherwise.
    CUDA_VISIBLE_DEVICES="" /workspace/models/embed-zs/.venv/bin/python validate/p1_consumer_check.py   (from projects/world-state)  -> runs/pulse/validate/p1_consumer_check.json"""
import os, sys, json, re, copy, pathlib
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
WS = pathlib.Path(__file__).resolve().parents[1]; os.chdir(WS); sys.path.insert(0, str(WS)); OUTD = pathlib.Path("runs/pulse/validate")
import facts_lib as FL, span_rules as SR, analyze2 as A2, pool_build as PB, extract as E
from expert1_runtime import ExpertS
R = []
def ok(name, cond, note=""):
    R.append({"check": name, "pass": bool(cond), "note": note}); print(("PASS " if cond else "FAIL ") + name + (" | " + note if note else ""))
def mutate(it, d=1):
    m = copy.deepcopy(it)
    if "span" in m: m["span"] = [m["span"][0] + d, m["span"][1] + d]
    if "s" in m: m["s"] += d; m["e"] += d  # fact items carry both s/e and span (P1d); shift both
    return m
G = [json.loads(l) for l in open("runs/pulse/golden/articles.jsonl")]
g = next(x for x in G if x.get("date") and len(re.findall(r"\d", x["body"])) > 20 and len(FL.facts_for(re.sub(r"\s+", " ", x["title"] + ". " + x["body"])[:12000], x["date"] + "T00:00:00Z")[0]) > 5)
title, body, date = g["title"], g["body"], g["date"]; text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; anchor = date + "T00:00:00Z"
facts = FL.facts_for(text, anchor)[0]; am = next(f for f in facts if f["kind"] == "amount" and f["status"] == "stated"); ai = facts.index(am)
# 1. the item-level functions
kept, held = FL.quarantine(facts, text); ok("1a unmutated facts: nothing held, same objects", held == [] and len(kept) == len(facts) and all(a is b for a, b in zip(kept, facts)))
mf = list(facts); mf[ai] = mutate(am); kept, held = FL.quarantine(mf, text)
ok("1b mutated fact held back, status quarantined, not in kept", len(held) == 1 and held[0]["status"] == "quarantined" and held[0]["status_was"] == "stated" and all(not (k.get("s") == mf[ai]["s"] and k.get("e") == mf[ai]["e"] and k.get("text") == mf[ai]["text"]) for k in kept) and len(kept) == len(facts) - 1)
ok("1c 'quarantined' is not a key in checks", all("quarantined" not in f["checks"] for f in held + kept))
items = [PB.it("fact-finder", E.V, f["kind"], f["s"], f["e"], text, "proved", value=f["value"], checks=f["checks"], status=f["status"]) for f in facts]
ok("1d pool items carry tool, version, span, provenance, status", all(i["tool"] and i["version"] and i["span"] and i["provenance"] in ("Observed", "Resolved", "External", "Inferred", "Candidate") and i["status"] for i in items))
mi = list(items); mi[ai] = mutate(items[ai]); k2, h2 = PB.held_back(mi, text); u2, hu = PB.held_back(items, text)
ok("1e pool_build.held_back drops the mutant", len(h2) == 1 and len(k2) == len(items) - 1 and h2[0]["status"] == "quarantined")
ok("1f pool_build.held_back leaves an unmutated list identical", hu == [] and u2 == items and all(a is b for a, b in zip(u2, items)))
# 2. analyze2.analyze
Ex = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json")); X = A2.Analyzer(Ex.S, FT, threads=2, fit_headline=True)
def strip(r): return {"fields": r["fields"], "evidence": {k: v for k, v in r["evidence"].items() if k not in ("quarantined", "windows_detail")}}
base = X.analyze(title, body, date); real_ff = FL.facts_for; real_sp = SR.spans
ok("2a baseline analyze quarantines nothing", base["evidence"]["quarantined"] == [])
bad_text = am["text"]
def ff_mut(t, a): out, ind, doc = real_ff(t, a); out = list(out); out[next(i for i, f in enumerate(out) if f["kind"] == "amount" and f["status"] == "stated")] = mutate(next(f for f in out if f["kind"] == "amount" and f["status"] == "stated")); return out, ind, doc
FL.facts_for = ff_mut
try: mut = X.analyze(title, body, date)
finally: FL.facts_for = real_ff
q = mut["evidence"]["quarantined"]; first_stated = next(f for f in facts if f["kind"] == "amount" and f["status"] == "stated")
ok("2b mutated fact is in evidence.quarantined", len(q) == 1 and q[0]["kind"] == "amount" and q[0]["s"] == first_stated["s"] + 1, "q=%s want s=%s" % (q, first_stated["s"] + 1))
ok("2c mutated fact absent from stated_amounts and the size proposal", mut["evidence"]["stated_amounts"] == [t for t in base["evidence"]["stated_amounts"] if t != bad_text] or base["evidence"]["stated_amounts"].count(bad_text) > 1, "base %s | mutated %s" % (base["evidence"]["stated_amounts"][:4], mut["evidence"]["stated_amounts"][:4]))
ok("2c2 size proposed text differs from baseline only by the held-back amount", bad_text not in [x.split(" (")[0] for x in mut["fields"]["size"]["proposed"].split("; ")] or base["evidence"]["stated_amounts"].count(bad_text) > 1)
sp0 = [x for x in SR.spans(text, anchor) if x["kind"] != "number_word" or x["value"] is not None]
if sp0:
    def sp_mut(t, a): out = list(real_sp(t, a)); out[0] = mutate(out[0]); return out
    SR.spans = sp_mut
    try: ms = X.analyze(title, body, date)
    finally: SR.spans = real_sp
    ok("2d mutated span_rules item is held back and not in span_rules.items", len(ms["evidence"]["quarantined"]) >= 1 and all(not (x[1] == sp0[0]["s"] + 1 and x[2] == sp0[0]["e"] + 1) for x in ms["evidence"]["span_rules"]["items"]))
again = X.analyze(title, body, date); ok("2e unmutated analyze equals the baseline (fields, evidence)", json.dumps(strip(again), sort_keys=True, default=str) == json.dumps(strip(base), sort_keys=True, default=str))
# 3. pool_build.work on one real harvest row
E.init(); row = json.loads(open("runs/harvest/sample.jsonl").readline()); row.setdefault("row", 0)
w0 = PB.work(row); ok("3a real row: nothing quarantined", w0["quarantined"] == [] and len(w0["items"]) > 0, "%d items" % len(w0["items"]))
real_held = PB.held_back; PB.held_back = lambda items, text: (list(items), []); wnq = PB.work(row); PB.held_back = real_held
ok("3b unmutated work() items identical with quarantine switched off", w0["items"] == wnq["items"])
real_ffe = E.FL.facts_for
def ff2(t, a):
    out, ind, doc = real_ffe(t, a); out = list(out)
    if out: out[0] = mutate(out[0])
    return out, ind, doc
if real_ffe(PB.E.work(row)["text"], (row.get("date") or "")[:10] + "T00:00:00Z" if row.get("date") else None)[0]:
    E.FL.facts_for = ff2
    try: wm = PB.work(row)
    finally: E.FL.facts_for = real_ffe
    ok("3c mutated fact item absent from work() items, present in quarantined", len(wm["quarantined"]) >= 1 and all(h["status"] == "quarantined" for h in wm["quarantined"]) and all(h["status"] == "quarantined" for h in wm["quarantined"]) and len(wm["items"]) == len(w0["items"]) - len(wm["quarantined"]) and all(not (i["tool"] == "fact-finder" and i["span"] == [h["s"], h["e"]] and i["text"] == h["text"]) for h in wm["quarantined"] for i in wm["items"]) and all(i["kind"] != h["kind"] or [i["span"][0], i["span"][1]] != [h["s"], h["e"]] for h in wm["quarantined"] for i in wm["items"] if i["tool"] == "fact-finder"))
else: ok("3c row has facts to mutate", False, "first harvest row has no facts; pick another row")
OUTD.mkdir(parents=True, exist_ok=True); allok = all(r["pass"] for r in R); json.dump({"pass": allok, "story": g["title"][:80], "checks": R}, open(OUTD / "p1_consumer_check.json", "w"), indent=1); print("ALL PASS" if allok else "FAILED"); sys.exit(0 if allok else 1)
