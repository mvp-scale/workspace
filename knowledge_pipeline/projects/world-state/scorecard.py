"""Scorecard: what the CPU expert (Expert3 v3.1) can extract, field by field and class by class, on the later unseen items.
    /workspace/models/embed-zs/.venv/bin/python scorecard.py      CPU only, no hosted calls
Truth is Sonnet's label (agreement, never accuracy). Test items = the last fifth by date of the Haiku-labelled pool that Sonnet also labelled (same split as score_natural.py).
Presence is weighted back to the natural stream (Haiku positives were over-sampled for Sonnet voting); every other field is unweighted over the voted items.
Writes runs/snapshots/scorecard.json and scorecard.html (template scorecard_template.html)."""
import json, glob, sys, time, random, collections, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert3
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
e = Expert3("runs/expert1/expert1_v31.pkl"); pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]
hn_t = sum(1 for i in test if not old[i]["conditions"]); hn_v = sum(1 for i in vt if not old[i]["conditions"]); hp_t = len(test) - hn_t; hp_v = len(vt) - hn_v
w = np.array([hp_t / hp_v if old[i]["conditions"] else hn_t / hn_v for i in vt]); W = lambda m: float(w[m].sum())
LV = e.M["LV"]; t0 = time.time(); R = [e.read(pool[i]["text"]) for i in vt]; ms = (time.time() - t0) * 1000 / len(vt)
n = len(vt); F = []
def field(name, what, bar_note, n_items, answered, agree, forced=None, extra=None, note=""):
    d = {"field": name, "what": what, "n": n_items, "answered_share": round(answered, 3) if answered is not None else None, "agreement": round(agree, 3) if agree is not None else None, "forced": round(forced, 3) if forced is not None else None, "note": note}
    if extra: d.update(extra)
    F.append(d)
def verdict(a, ag, nn, strong=False):  # Ready needs 80% agreement, 30+ items, half the stream answered; fields that depend on a detected condition are capped at Partial below (reach rule added 2026-11-01)
    if nn < 30 or ag is None: return "Can't tell"
    if ag >= 0.80 and a >= 0.5: return "Ready"
    return "Partial" if ag >= 0.80 else "Not yet"
# story type
sa = np.array([r["story_type"]["status"] == "answered" for r in R]); sok = np.array([r["story_type"]["answer"] == sn[i]["story_type"] for r, i in zip(R, vt)])
# topic
t1 = np.array([r["topic_top2"]["answer"][0] == sn[i]["topic"] if r["topic_top2"]["answer"] else False for r, i in zip(R, vt)]); t2 = np.array([sn[i]["topic"] in (r["topic_top2"]["answer"] or []) for r, i in zip(R, vt)]); ta = np.array([r["topic_top2"]["status"] == "answered" for r in R])
# presence (weighted)
sp_ = np.array([1 if sn[i]["conditions"] else 0 for i in vt]); cp = [r["condition_present"] for r in R]; pa = np.array([c["status"] == "answered" for c in cp]); pr = np.array([bool(c["answer"]) if c["answer"] is not None else False for c in cp]); pok = pr == (sp_ == 1)
cm = pa & pr
# which condition / direction / size
wc_n = wc_ok = wc_ok_strict = 0; dr_n = dr_ok = sz_n = sz_ok = 0; perc = collections.defaultdict(lambda: {"n": 0, "found": 0, "top1": 0}); cc_all = collections.Counter()
for r, i in zip(R, vt):
    sc = sn[i]["conditions"]; names = [x["condition"] for x in sc]
    for x in sc: perc[x["condition"]]["n"] += 1
    c = r.get("condition")
    if r["condition_present"]["answer"] and r["condition_present"]["status"] == "answered" and sc:
        for x in sc:
            if c and c["status"] == "answered" and x["condition"] in c["answer"]: perc[x["condition"]]["found"] += 1
            if c and c["status"] == "answered" and x["condition"] == c["answer"][0]: perc[x["condition"]]["top1"] += 1
    if c and c["status"] == "answered" and sc:
        wc_n += 1; hit = c["answer"][0] in names; wc_ok += hit; wc_ok_strict += (c["answer"][0] == names[0])
        if hit:
            x = next(x for x in sc if x["condition"] == c["answer"][0]); dr_n += 1; dr_ok += (c["direction"] == x["direction"])
            sz_n += 1; sz_ok += (abs(LV.index(c["size"]) - LV.index(x["level"])) <= 1)
field("Story type", "Is it a fact, a forecast, an opinion, or unclear", "", n, sa.mean(), sok[sa].mean(), sok.mean(), {"verdict": verdict(sa.mean(), sok[sa].mean(), n)})
field("Topic (one answer)", "Which of 49 topics the story is mainly about, first guess", "", n, ta.mean(), t1[ta].mean(), t1.mean(), {"verdict": verdict(ta.mean(), t1[ta].mean(), n)})
field("Topic (two guesses)", "Sonnet's topic is one of the model's two best guesses", "", n, ta.mean(), t2[ta].mean(), t2.mean(), {"verdict": verdict(ta.mean(), t2[ta].mean(), n)})
pw = W(pa) / W(np.ones(n, bool)); pag = W(pa & pok) / W(pa)
field("Condition present", "Does the story report a change in one of 38 world conditions (weighted to the natural stream)", "", n, pw, pag, W(pok) / W(np.ones(n, bool)), {"verdict": "Partial" if verdict(pw, pag, n) == "Ready" and W(cm & (sp_ == 1)) / W(sp_ == 1) < 0.5 else verdict(pw, pag, n), "commit_precision": round(W(cm & (sp_ == 1)) / W(cm), 3), "catch_rate": round(W(cm & (sp_ == 1)) / W(sp_ == 1), 3)})
field("Which condition", "Of the items where it says present and commits, its first guess is a condition Sonnet listed", "", wc_n, None, wc_ok / wc_n, None, {"strict": round(wc_ok_strict / wc_n, 3), "verdict": verdict(1, wc_ok / wc_n, wc_n), "capped": True}, "Only the items it commits on. The share answered here is the 'Condition present' catch rate.")
field("Direction", "Up or down, when the condition is right", "", dr_n, None, dr_ok / dr_n, None, {"verdict": verdict(1, dr_ok / dr_n, dr_n), "capped": True})
field("Size", "How big, within one step of Sonnet's level (minor, notable, major, severe, extreme)", "", sz_n, None, sz_ok / sz_n, None, {"verdict": verdict(1, sz_ok / sz_n, sz_n), "capped": True})
for d in F:
    if d.pop("capped", False) and d["verdict"] == "Ready": d["verdict"] = "Partial"; d["note"] = (d["note"] + " Only on the stories where it already found the condition (about 1 in 7 of the real ones), so it cannot yet be called Ready.").strip()
for nm, what in (("Claim", "The one sentence the story asserts"), ("Evidence", "The span of text that supports it"), ("Attribution", "Who said it")): F.append({"field": nm, "what": what, "n": 0, "answered_share": None, "agreement": None, "forced": None, "verdict": "Not built", "note": ""})
# per topic
pt = collections.defaultdict(lambda: {"n": 0, "top1": 0, "top2": 0})
for r, i, a, b in zip(R, vt, t1, t2): k = sn[i]["topic"]; pt[k]["n"] += 1; pt[k]["top1"] += int(a); pt[k]["top2"] += int(b)
topics = sorted(({"name": k, "n": v["n"], "top1": round(v["top1"] / v["n"], 3), "top2": round(v["top2"] / v["n"], 3), "verdict": "Can't tell" if v["n"] < 20 else ("Ready" if v["top2"] / v["n"] >= 0.8 else "Not yet")} for k, v in pt.items()), key=lambda d: -d["n"])
conds = sorted(({"name": k, "n": v["n"], "found": round(v["found"] / v["n"], 3), "top1": round(v["top1"] / v["n"], 3), "verdict": "Can't tell" if v["n"] < 20 else ("Ready" if v["found"] / v["n"] >= 0.5 else "Not yet")} for k, v in perc.items()), key=lambda d: -d["n"])
# examples: seeded random, full text
rnd = random.Random(7); ex = []
for i in rnd.sample(range(n), 10):
    r = R[i]; s = sn[vt[i]]; c = r.get("condition")
    ex.append({"id": vt[i], "text": pool[vt[i]]["text"], "sonnet": {"topic": s["topic"], "story": s["story_type"], "conditions": [f'{x["condition"]} {x["direction"]} {x["level"]}' for x in s["conditions"]]},
               "model": {"topic": r["topic_top2"]["answer"], "topic_hit": bool(t2[i]), "story": r["story_type"]["answer"], "story_hit": bool(sok[i]), "present": cp[i]["answer"], "present_status": cp[i]["status"], "present_conf": round(cp[i]["confidence"], 2) if "confidence" in cp[i] else None,
                         "condition": (c["answer"] + [c["direction"], c["size"]]) if c and c["status"] == "answered" else None, "path": r.get("path")}})
out = {"built": time.strftime("%Y-%m-%d %H:%M"), "artefact": "runs/expert1/expert1_v31.pkl", "n_items": n, "ms_per_item_this_run": round(ms, 1), "teacher": "claude-sonnet-5-5 (ws-v2-frozen)", "fields": F, "topics": topics, "conditions": conds, "examples": ex}
json.dump(out, open("runs/snapshots/scorecard.json", "w"), indent=1)
html = open("scorecard_template.html", encoding="utf-8").read().replace("/*DATA*/null", json.dumps(out).replace("</", "<\\/")); open("scorecard.html", "w", encoding="utf-8").write(html)
for f in F: print(f["field"], "| n", f["n"], "| answered", f["answered_share"], "| agree", f["agreement"], "|", f["verdict"])
print("topics ready", sum(t["verdict"] == "Ready" for t in topics), "of", sum(t["n"] >= 20 for t in topics), "with 20+; conditions ready", sum(c["verdict"] == "Ready" for c in conds), "of", sum(c["n"] >= 20 for c in conds), "with 20+; ms/item", round(ms, 1))
