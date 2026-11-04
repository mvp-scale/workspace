#!/usr/bin/env python3
"""Local Clef (already loaded, approved in CLAUDE.md) as a third voter: topic, story type, any-condition, with probabilities. 300 W7 dev items; frozen 300 untouched.
Called by registry name through demo/backends.py. Run: python3 clef_probe.py"""
import json, pathlib, sys, time, concurrent.futures as cf
from collections import Counter
sys.path.insert(0, "/workspace/demo"); import backends
HERE = pathlib.Path(__file__).resolve().parent; W = HERE / "runs" / "waves"; BID = backends.DEFAULT_TEACHER
J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
spec = json.load(open(HERE / "specs" / "world_state_v1.json")); G = "\n".join(spec["guideline"])
topics = {}
for l in G.split("TOPICS (id: meaning)")[1].splitlines():
    if ": " in l and not l.startswith(" "): k, v = l.split(": ", 1); topics[k.strip()] = v.strip()
    elif l.strip() and ": " not in l: break
Q = {"topic": {"type": "choice", "instructions": "What is this news item mainly about?", "criteria": topics},
     "story": {"type": "choice", "instructions": "What kind of story is this?", "criteria": {"fact": "It reports something that happened or was announced", "forecast": "It is mainly a prediction about the future", "opinion": "It is mainly commentary or a view", "unclear": "None of these"}},
     "change": {"type": "choice", "instructions": "Does this item report that some condition of a place (prices, health, safety, supply, environment, jobs and so on) is rising or falling, or give a real reason to expect it to?", "criteria": {"yes": "Yes, it reports or clearly implies such a change", "no": "No, it reports an event, a person, a plan or a mention with no clear change in a condition"}}}
items = {r["id"]: r["text"] for r in J(W / "w7_items.jsonl")}
H = {r["item_id"]: r["label"] for r in J(W / "w7/haiku/labels.jsonl")}; S = {r["item_id"]: r["label"] for r in J(W / "w7/sonnet/labels.jsonl")}
ids = [i for i in items if i in H and i in S][:300]
def run(i):
    t0 = time.time(); a = {}
    for k in Q: a.update(backends.ask(BID, f"News item:\n{items[i]}", {k: Q[k]}, timeout=120))      # one question per call: a 3-question call timed out
    return i, a, time.time() - t0
t0 = time.time()
with cf.ThreadPoolExecutor(1) as ex: R = list(ex.map(run, ids))
wall = time.time() - t0
C = {i: a for i, a, _ in R}; print(f"{len(R)} items, 3 questions each, {wall:.0f}s wall ({wall/len(R)*1000:.0f} ms/item, one at a time), model {BID}")
def conf(i, k): return max(C[i][k]["probabilities"].values())
for k, key, hk in (("topic", "topic", "topic"), ("story", "story_type", "story_type")):
    for ref, nm in ((S, "Sonnet"), (H, "Haiku")):
        print(f"{k}: Clef vs {nm} same on {sum(C[i][k]['choice']==ref[i][hk] for i in ids)/len(ids):.3f}", end=" | ")
    print(f"Haiku vs Sonnet {sum(H[i][hk]==S[i][hk] for i in ids)/len(ids):.3f} | majority-guess {Counter(S[i][hk] for i in ids).most_common(1)[0][1]/len(ids):.3f}")
    for c in (0.5, 0.8):
        sel = [i for i in ids if conf(i, k) >= c]; print(f"   Clef sure >= {c}: {len(sel)/len(ids):.0%} of items, matches Sonnet {sum(C[i][k]['choice']==S[i][hk] for i in sel)/max(len(sel),1):.3f}")
st = Counter((S[i]["story_type"], C[i]["story"]["choice"]) for i in ids); print("story type, Sonnet -> Clef:", {f"{a}->{b}": n for (a, b), n in sorted(st.items())})
ys = [bool(S[i]["conditions"]) for i in ids]; yc = [C[i]["change"]["choice"] == "yes" for i in ids]; yh = [bool(H[i]["conditions"]) for i in ids]
tp = sum(a and b for a, b in zip(ys, yc)); print(f"any change: Sonnet says yes on {sum(ys)/len(ids):.0%}; Clef says yes on {sum(yc)/len(ids):.0%}; Clef finds {tp}/{sum(ys)} of Sonnet's yeses and is right on {tp/max(sum(yc),1):.0%} of its own yeses; Haiku finds {sum(a and b for a,b in zip(ys,yh))}/{sum(ys)}")
json.dump({i: {k: {"choice": C[i][k]["choice"], "p": max(C[i][k]["probabilities"].values())} for k in C[i]} for i in C}, open(HERE / "runs" / "retest" / "clef300.json", "w"))
