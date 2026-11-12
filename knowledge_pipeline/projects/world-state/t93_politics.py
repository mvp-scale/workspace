"""T93: where do politics articles drop out between the pool and the supported-triple set? Reader (v6b-student) top-1 topic per article, politics = a topic whose IPTC map (specs/topic_to_iptc_v1.json) includes 'politics'. Three article sets: a random 5000 of the CC-News pool, the core articles (2+ same-event partners, T90), the articles holding a supported triple (T91). Writes the politics share of each and the ratios.
    OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t93_politics.py -> <OUT>/t93_politics.json"""
import os, sys, json, glob, random, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
sys.path.insert(0, "."); from expert1_runtime import ExpertS
OUT = os.environ.get("OUT", "runs/pulse/t93"); os.makedirs(OUT, exist_ok=True); random.seed(93)
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; POL = {t for t, c in M.items() if "politics" in c}
P = json.load(open("runs/pulse/t90/pairs_ids.json")); nb = collections.defaultdict(set)
for a, b in P: nb[a].add(b); nb[b].add(a)
core = sorted(u for u, v in nb.items() if len(v) >= 2); sup = sorted({s["article"] for s in json.load(open("runs/pulse/t91/t91_supported_triples.json"))})
S = {"core": random.sample(core, 5000), "supported": random.sample(sup, 5000 if len(sup) > 5000 else len(sup))}
need = set(S["core"]) | set(S["supported"]); text = {}; pool = []
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "title", "description"]); rows = t.to_pylist(); random.shuffle(rows)
    for r in rows[:1000]:
        ti = " ".join((r["title"] or "").split()); d = " ".join((r["description"] or "").split())
        if len(ti) >= 10 and len(d) >= 30: pool.append(ti + ". " + d)
    mk = pc.is_in(t["url"], value_set=pa.array(list(need)))
    for r in t.filter(mk).to_pylist(): text[r["url"]] = " ".join((r["title"] or "").split()) + ". " + " ".join((r["description"] or "").split())
S["pool"] = pool; e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); res = {}
for k, items in S.items():
    c = collections.Counter(); pol = 0; n = 0
    for x in items:
        r = e.read(text.get(x, x) if k != "pool" else x)["topic_top2"]
        if not r["answer"]: continue
        n += 1; c[r["answer"][0]] += 1; pol += r["answer"][0] in POL
    res[k] = {"articles_read": n, "politics_share": round(pol / max(n, 1), 4), "top_topics": c.most_common(6)}
res["ratio_supported_to_pool"] = round(res["supported"]["politics_share"] / max(res["pool"]["politics_share"], 1e-9), 4); res["ratio_core_to_pool"] = round(res["core"]["politics_share"] / max(res["pool"]["politics_share"], 1e-9), 4)
res["politics_topics"] = sorted(POL); res["note"] = "Reader top-1 topic only; answered items only; politics = topics whose IPTC map includes politics. Pool = 1000 random rows per file."
json.dump(res, open(OUT + "/t93_politics.json", "w"), indent=1); print(json.dumps(res, indent=1))
