"""T62: how many extracted triples are backed by several distinct publishers.
    /workspace/models/embed-zs/.venv/bin/python -u triple_support.py [N] -> runs/pulse/triple_support.json, triple_support_top.jsonl"""
import os, sys, json, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
from multiprocessing import Pool
import spacy, spo_chains as S
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
nlp = None
def init():
    global nlp
    nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"] if False else [])
def work(r):
    txt = (r.get("title", "") + ". " + r.get("text", ""))[:1500]
    sents = [s.text for s in nlp(txt).sents][:12]
    out = set()
    for t in S.extract(nlp, sents):
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and not t["neg"] and not t["modal"]:
            out.add((t["s_key"], t["p"].lower(), t["o_key"]))
    return r["domain"], out
if __name__ == "__main__":
    R = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))]
    sup = collections.defaultdict(set); arts = collections.Counter()
    with Pool(18, initializer=init) as P:
        for dom, out in P.imap_unordered(work, R, chunksize=50):
            for k in out: sup[k].add(dom)
    cnt = collections.Counter(len(v) for v in sup.values())
    res = {"articles": len(R), "distinct_triples": len(sup),
           "ge2_domains": sum(1 for v in sup.values() if len(v) >= 2), "ge3_domains": sum(1 for v in sup.values() if len(v) >= 3),
           "share_ge3": round(sum(1 for v in sup.values() if len(v) >= 3) / max(1, len(sup)), 4), "max_domains": max(cnt)}
    json.dump(res, open("runs/pulse/triple_support.json", "w"), indent=1)
    with open("runs/pulse/triple_support_top.jsonl", "w") as w:
        for k, v in sorted(sup.items(), key=lambda kv: -len(kv[1]))[:500]: w.write(json.dumps({"triple": k, "domains": len(v)}) + "\n")
    print(res)
