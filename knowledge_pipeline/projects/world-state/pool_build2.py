"""pool_build2 (T50): run the BitMob toolchain of pool_build.py over every label-store item that has text (data/pool.jsonl + runs/pulse/queue_texts.jsonl), so evidence and labels share ids. Same work(), same strength rule (playbook 15 rules 2 and 5). The text is split at its first '. ' into title and body so extract.work rebuilds the same string and spans index the stored text.
    /workspace/models/embed-zs/.venv/bin/python -u pool_build2.py [MAXSEC]  -> runs/harvest/pool_v2/labelled.jsonl, summary_labelled.json"""
import json, sys, time, collections, os
from multiprocessing import Pool
import extract as E, pool_build as PB
SEALED = len(sys.argv) > 2 and sys.argv[2] == "sealed"; PB.V = "pool-v2"; OUT = "runs/harvest/pool_v2/"; os.makedirs(OUT, exist_ok=True)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
def rows():
    txt = {r["id"]: r for r in J("data/pool.jsonl")}
    for r in J("runs/pulse/queue_texts.jsonl"): txt.setdefault(r["id"], r)
    lab = sorted({json.loads(l)["item_id"] for l in open("runs/pulse/sealed/labels.jsonl")} & set(txt)) if SEALED else sorted({json.loads(l)["item_id"] for l in open("runs/label_store/labels.jsonl")} & set(txt))
    for k, i in enumerate(lab):
        t = txt[i]["text"]; a, _, b = t.partition(". ")
        yield {"url": i, "row": k, "domain": "", "title": a, "text": b if _ else "", "date": txt[i].get("date"), "description": ""}
def work(r):
    o = PB.work(r); o["item_id"] = r["url"]; o["v"] = "pool-v2"; return o
if __name__ == "__main__":
    MAXS = float(sys.argv[1]) if len(sys.argv) > 1 else 2400; t0 = time.time(); n = 0; cnt = collections.Counter(); anyp = 0
    with Pool(18, initializer=E.init) as P, open(OUT + ("sealed_evidence.jsonl" if SEALED else "labelled.jsonl"), "w") as w:
        for rec in P.imap(work, rows(), chunksize=16):
            w.write(json.dumps(rec) + "\n"); n += 1; hp = False
            for x in rec["items"]: cnt[(x["tool"], x["strength"])] += 1; hp |= x["strength"] == "proved"
            anyp += hp
            if n % 5000 == 0: print(n, round(time.time() - t0), flush=True)
            if time.time() - t0 > MAXS: print("time budget reached", flush=True); P.terminate(); break
    wall = time.time() - t0; labn = len({json.loads(l)["item_id"] for l in open("runs/label_store/labels.jsonl")})
    s = {"v": "pool-v2", "articles_done": n, "label_store_ids": labn, "coverage_of_label_store": round(n / labn, 4), "wall_seconds": round(wall, 1), "seconds_per_article": round(wall / n, 4),
         "items_per_article_by_tool_strength": {f"{t}|{s_}": round(c / n, 3) for (t, s_), c in sorted(cnt.items())}, "share_articles_with_proved": round(anyp / n, 4)}
    json.dump(s, open(OUT + ("summary_sealed.json" if SEALED else "summary_labelled.json"), "w"), indent=1); print(json.dumps(s))
