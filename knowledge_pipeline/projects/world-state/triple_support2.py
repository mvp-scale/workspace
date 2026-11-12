"""T63: filtered triple support per topic. Triples from the first 1500 characters of full text of the 40,000 articles in runs/queue/unsure_v1.jsonl; Domain = encoder topic stored there.
    /workspace/models/embed-zs/.venv/bin/python -u triple_support2.py [N] -> runs/pulse/triple_support2.json, triple_support2_topics.json"""
import os, sys, json, glob, collections, re
os.environ["CUDA_VISIBLE_DEVICES"] = ""
from multiprocessing import Pool
import spacy, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc, spo_chains as S
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
DAYS = {"monday","tuesday","wednesday","thursday","friday","saturday","sunday"}
MONTHS = {"january","february","march","april","may","june","july","august","september","october","november","december"}
FURN = {"name","email","email address","email address post","comment","comments","post","share","password","cookie","cookies","advertisement","subscribe","click","photo","video","story","article","copyright","privacy policy","terms"}
WIRE = {"ap","reuters","afp","upi","cnn","bbc"}
COPULA = {"is","are","was","were","be","been","being","'s","'re"}
BAD = DAYS | MONTHS | FURN | WIRE
nlp = None
def init():
    global nlp
    nlp = spacy.load("en_core_web_sm")
def ok(t):
    s, o = t["s_key"], t["o_key"]
    if not s or not o or s == o or len(s) < 3 or len(o) < 3 or re.fullmatch(r"[\d\W]+", s) or re.fullmatch(r"[\d\W]+", o): return False
    if s in BAD or o in BAD: return False
    return t["p"].lower().split()[-1] not in COPULA
def work(r):
    sents = [s.text for s in nlp(r["text"][:1500]).sents][:12]
    out = set()
    for t in S.extract(nlp, sents):
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and not t["neg"] and not t["modal"] and ok(t):
            out.add((t["s_key"], t["p"].lower(), t["o_key"]))
    return r["topic"], r["domain"], out
if __name__ == "__main__":
    Q = {}
    for l in open("runs/queue/unsure_v1.jsonl"):
        d = json.loads(l); Q[d["id"][3:]] = d
        if len(Q) >= N: break
    rows = []
    for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
        t = pq.read_table(f, columns=["url", "text"]); m = pc.is_in(t["url"], value_set=pa.array(list(Q)))
        for u, x in zip(t["url"].filter(m).to_pylist(), t["text"].filter(m).to_pylist()):
            if u in Q: rows.append({"text": x or "", "topic": Q[u]["topic"], "domain": Q[u]["domain"]}); Q.pop(u)
    print("articles with full text", len(rows), flush=True)
    sup = collections.defaultdict(lambda: collections.defaultdict(set))
    with Pool(18, initializer=init) as P:
        for top, dom, out in P.imap_unordered(work, rows, chunksize=50):
            for k in out: sup[top][k].add(dom)
    per = {}; allsup = collections.defaultdict(set)
    for top, d in sup.items():
        good = {k: v for k, v in d.items() if len(v) >= 3}
        per[top] = {"distinct": len(d), "ge3": len(good), "top": [{"triple": list(k), "domains": len(v)} for k, v in sorted(good.items(), key=lambda kv: -len(kv[1]))[:15]]}
        for k, v in d.items(): allsup[k] |= v
    ge3 = sum(1 for v in allsup.values() if len(v) >= 3)
    res = {"articles": len(rows), "distinct_triples_after_filter": len(allsup), "ge3_domains_total": ge3,
           "topics_with_ge10": sum(1 for v in per.values() if v["ge3"] >= 10), "topics": len(per)}
    json.dump(res, open("runs/pulse/triple_support2.json", "w"), indent=1); json.dump(per, open("runs/pulse/triple_support2_topics.json", "w"), indent=1)
    print(res)
