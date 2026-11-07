"""Traces real articles through every layer of analyze2.py and records each layer's input and output, so the page can show what each layer saw.
Eight reference articles (runs/pulse/golden/articles.jsonl), chosen by length: two shortest, two median, two near the 80th percentile, two longest.
    /workspace/models/embed-zs/.venv/bin/python trace_articles.py   (from projects/world-state)  ->  runs/pulse/trace_articles.json"""
import json, re, sys, time, numpy as np
sys.path.insert(0, "."); import decider as D, facts_lib as FL, analyze2 as A2
from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json")); S = e.S
G = [json.loads(l) for l in open("runs/pulse/golden/articles.jsonl")]
order = sorted(range(len(G)), key=lambda i: len(G[i]["body"])); n = len(order)
pick = order[:2] + order[n // 2 - 1:n // 2 + 1] + order[int(n * .8):int(n * .8) + 2] + order[-2:]
X = A2.Analyzer(S, FT, threads=8, fit_headline=True); R = X.reader; out = []
for gi in pick:
    g = G[gi]; title, body, date = g["title"], g["body"], g["date"]
    clean = re.sub(r"\s+", " ", title + ". " + body)[:12000]
    b = re.sub(r"\s+", " ", body); W = R.windows(title, body); pos = 0; wins = []
    pt_all, ps_all = [], []
    for w in W:
        k = b.find(w, pos); k = pos if k < 0 else k; pos = k + len(w)
        ids = R.tkt.encode(re.sub(r"\s+", " ", title) + ". " + w).ids
        ptw, psw, _ = R.read(title, w) if False else (None, None, None)
        wins.append({"start": k, "end": k + len(w), "pieces": len(ids)})
    # per-window reader output
    t = re.sub(r"\s+", " ", title); texts = [t + ". " + w for w in W]; enc = R.tkt.encode_batch([x[:1200] for x in texts]); L = max(len(x.ids) for x in enc)
    ids = np.zeros((len(enc), L), dtype=np.int64); m = np.zeros((len(enc), L), dtype=np.int64)
    for i, x in enumerate(enc): ids[i, :len(x.ids)] = x.ids; m[i, :len(x.ids)] = 1
    V = R.sess.run(None, {"input_ids": ids, "attention_mask": m})[0]; PT = A2.softmax(V @ R.tW + R.tb); PS = A2.softmax(V @ R.sW + R.sb)
    for i, w in enumerate(wins):
        w["topic"] = [[S["topic_cl"][k], round(float(PT[i][k]), 3)] for k in np.argsort(-PT[i])[:2]]; w["story"] = [S["story_cl"][int(PS[i].argmax())], round(float(PS[i].max()), 3)]
    avg = PT.mean(0); avs = PS.mean(0)
    # the old reading: headline + teaser, first 64 pieces of title + body
    old = R.tkt.encode(t + ". " + b[:1200]); oldlen = len(old.offsets); lastchar = max((o[1] for o in old.offsets), default=0)
    first = R.read(title, b[:1])  # unused, keeps API honest
    oldV = R.sess.run(None, {"input_ids": np.array([old.ids], dtype=np.int64), "attention_mask": np.ones((1, len(old.ids)), dtype=np.int64)})[0]; oldT = A2.softmax(oldV @ R.tW + R.tb)[0]
    res = X.analyze(title, body, date); facts = FL.facts_for(clean, (date + "T00:00:00Z") if date else None)[0] if A2.NUM_OR_DATE.search(clean) else []
    fl = [{"kind": f["kind"], "s": f["s"], "e": f["e"], "text": f["text"], "value": f["value"] if not isinstance(f["value"], float) else round(f["value"], 3), "noun": f.get("noun"), "verb": f.get("verb"), "checks": f["checks"], "status": f["status"]} for f in facts if f["kind"] in ("amount", "date")]
    out.append({"id": g["id"], "title": title, "date": date, "raw_chars": len(title) + len(body), "clean": clean, "clean_chars": len(clean),
        "windows": wins, "window_cap": R.cap, "max_pieces": R.max_pieces, "topic_avg": [[S["topic_cl"][k], round(float(avg[k]), 3)] for k in np.argsort(-avg)[:3]], "story_avg": [[S["story_cl"][k], round(float(avs[k]), 3)] for k in np.argsort(-avs)[:2]],
        "body_chars": len(b), "windows_cover_body_chars": wins[-1]["end"], "windows_cover_share": round(wins[-1]["end"] / max(len(b), 1), 3),
        "old_reading": {"pieces": 64, "body_chars_seen": max(0, min(lastchar - len(t) - 2, len(b))), "body_share_seen": round(max(0, min(lastchar - len(t) - 2, len(b))) / max(len(b), 1), 3), "topic": [[S["topic_cl"][k], round(float(oldT[k]), 3)] for k in np.argsort(-oldT)[:2]]},
        "facts": fl, "parse_ran": res["evidence"]["parse_ran"], "decider": res["fields"], "ms": res["ms"]})
    print(g["id"], len(out[-1]["clean"]), "windows", len(wins), "facts", len(fl), res["ms"]["total_ms"].__round__(1) if isinstance(res["ms"]["total_ms"], float) else res["ms"], flush=True)
json.dump({"model_note": "BitMob Reader v6b-student; windows as in analyze2.py (headline kept in every window)", "articles": out}, open("runs/pulse/trace_articles.json", "w"))
print("saved", len(out))
