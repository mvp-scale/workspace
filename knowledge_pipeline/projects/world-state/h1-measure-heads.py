"""T158-H1: cost and vape-article outputs of the saved heads. Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I h1-measure-heads.py"""
import json, time, sqlite3, re, importlib.util, pathlib, os, sys
SP = "/tmp/claude-0/-workspace/3ed8559b-0aa2-49c4-a429-a0452a913be2/scratchpad/val/"; VAPE = "b9bd5dedf7525c0d06846c5faccf48b317c43b468b9d0d67c80b11704919564c"
arts = []; seen = set()
for f in ("ner_pull1.json", "ner_pull2.json"):
    for a in json.load(open(SP + f))["articles"]:
        if a["id"] not in seen and a.get("text"): seen.add(a["id"]); arts.append(a)
arts = arts[:20]
sp = importlib.util.spec_from_file_location("saved_heads", "saved-heads.py"); M = importlib.util.module_from_spec(sp); sp.loader.exec_module(M)
t0 = time.perf_counter(); H = M.SavedHeads(); load_s = time.perf_counter() - t0
def split(text):
    import scan_gate; return [text[a:b].strip() for a, b in scan_gate.scan(text, "2026-01-01T00:00:00Z")[1] if text[a:b].strip()]
try: scan_ok = True; split(arts[0]["text"])
except Exception as e: scan_ok = False
if not scan_ok:
    def split(text): return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
H.score(["warm up sentence for the encoders."])
ns = 0; tot = 0; per = []
for a in arts:
    ss = split(a["text"]); t = time.perf_counter(); H.score(ss); dt = time.perf_counter() - t; per.append(dt * 1000); ns += len(ss); tot += dt
fn_only = M.SavedHeads(function=True, factuality=False); fa_only = M.SavedHeads(function=False, factuality=True)
def timeit(h):
    t = time.perf_counter(); n = 0
    for a in arts: ss = split(a["text"]); h.score(ss); n += len(ss)
    return (time.perf_counter() - t) * 1000 / len(arts), (time.perf_counter() - t) * 1000 / n
fn = timeit(fn_only); fa = timeit(fa_only)
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); r = db.execute("select title, body, teaser from items where id=?", (VAPE,)).fetchone()
text = r[1] or r[2]; ss = split(text); out = H.score(ss)
res = {"splitter": "scan_gate.scan" if scan_ok else "regex", "n_articles": len(arts), "n_sentences": ns, "load_s_both": round(load_s, 2), "ms_per_article_both": round(tot * 1000 / len(arts), 1), "ms_per_sentence_both": round(tot * 1000 / ns, 2),
       "function_only": {"ms_per_article": round(fn[0], 1), "ms_per_sentence": round(fn[1], 2), "load_s": round(fn_only.load_s, 2)}, "factuality_only": {"ms_per_article": round(fa[0], 1), "ms_per_sentence": round(fa[1], 2), "load_s": round(fa_only.load_s, 2)},
       "vape": {"title": r[0], "n_sent": len(ss), "rows": [{"i": i, "s": s[:160], "function_p": round(out["function_p"][i], 3), "function": out["function_answer"][i], "factuality_p": round(out["factuality_p"][i], 3)} for i, s in enumerate(ss)]}}
json.dump(res, open("runs/pulse/h1_measure.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "vape"}, indent=1)); print(r[0], len(ss))
for x in res["vape"]["rows"]: print(x["i"], x["function_p"], x["function"], x["factuality_p"], x["s"][:110])
