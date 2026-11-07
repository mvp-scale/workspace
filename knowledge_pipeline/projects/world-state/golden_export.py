"""Reference outputs for each section of analyze.py, so a rewrite (Rust or other) can be checked section by section against the current Python.
Written per article: the windows, the scan spots, the stated facts, the topic and story-type probabilities, the decider inputs and outputs.
    /workspace/models/embed-zs/.venv/bin/python golden_export.py 200   (from projects/world-state)"""
import sys, json, re, random, numpy as np; sys.path.insert(0, ".")
import analyze as AN
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
X = AN.Analyzer(); e = X.e; A = X.A; S = e.S
gl = {v["l1"] for v in json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")).values()}
R = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]; R = [r for r in R if r.get("content") and r.get("title") and r["category_level_1"] in gl and len(r["content"]) >= 800]
random.seed(20261107); out = open("runs/pulse/golden/articles.jsonl", "w")
for i, r in enumerate(random.sample(R, N)):
    title, body, date = r["title"], r["content"], r.get("date"); W = A.windows(body); anchor = (date + "T00:00:00Z") if date else None
    PT, PS = [], []
    for w in W:
        v = e.student(title + ". " + w); PT.append(AN._soft(v @ S["t_W"].T + S["t_b"])); PS.append(AN._soft(v @ S["s_W"].T + S["s_b"]))
    pt, ps = np.mean(PT, axis=0), np.mean(PS, axis=0)
    text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; spots, _ = AN.G.scan(text, anchor or "2026-01-01T00:00:00Z"); facts, _, _ = AN.facts_for(text, anchor)
    dec = {m: [AN.decide(m, 1, True, c, 700, True) for c in (0, 500, 699, 700, 900)] for m in (0, 1, 2, 3)}
    out.write(json.dumps({"id": i, "title": title, "body": body, "date": date, "windows": W, "scan_spots": [list(x) for x in spots], "facts": [{k: f[k] for k in ("kind", "s", "e", "text", "status")} for f in facts],
                          "topic_probs": [round(float(x), 7) for x in pt], "story_probs": [round(float(x), 7) for x in ps], "topic_top2": [S["topic_cl"][k] for k in np.argsort(-pt)[:2]], "decider_by_marker_and_confidence": dec}) + "\n")
out.close(); print("wrote", N, "articles")
