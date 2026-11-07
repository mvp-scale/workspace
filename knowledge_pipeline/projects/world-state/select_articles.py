"""Choose three DISCRETE mock-up articles by rule, not by hand (owner 2026-11-05: two of the three were protest stories). Candidates: Clef-read stories (in no training pool) with 14 to 30 sentences that exist in the news reader store (so time fields are real). Strata by number of Clef dials: none, one or two, three or more. Greedy farthest-point sampling in embedding space across strata, with three constraints: different feeds, no Clef dial shared between any two chosen articles, and none close in meaning (cosine 0.75 or more) to the three articles shown before.
    /workspace/models/embed-zs/.venv/bin/python select_articles.py"""
import json, re, sqlite3, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
rows = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding(); so = ort.SessionOptions(); so.intra_op_num_threads = 8
sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t): e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); v = sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]; return v / (np.linalg.norm(v) + 1e-9)
cand = []
for r in rows:
    t = re.sub(r"\s+", " ", r["text"]); ns = len([s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘'])", t) if len(s) > 20])
    if 14 <= ns <= 30 and db.execute("select 1 from items where source=? and title=? limit 1", (r["source"], r["title"])).fetchone():
        dials = {x["dial"] for x in r["readings"] if x["direction"] != "conflict"}; cand.append({"id": r["id"][:8], "source": r["source"], "title": r["title"], "dials": dials, "e": emb(r["title"] + ". " + t[:300])})
print("candidates", len(cand), "by strata", {k: sum(1 for c in cand if (len(c["dials"]) == 0 if k == 0 else 1 <= len(c["dials"]) <= 2 if k == 1 else len(c["dials"]) >= 3)) for k in (0, 1, 2)})
strat = lambda c, k: (len(c["dials"]) == 0) if k == 0 else (1 <= len(c["dials"]) <= 2) if k == 1 else (len(c["dials"]) >= 3)
prev = [c for c in cand if c["id"] in ("fa4a903f", "804b7830", "f2c136c9")] or [{"e": emb(r["title"] + ". " + re.sub(r"\s+", " ", r["text"])[:300])} for r in rows if r["id"][:8] in ("fa4a903f", "804b7830", "f2c136c9")]
cand = [c for c in cand if all(float(c["e"] @ q["e"]) < 0.75 for q in prev)]; print("after excluding stories close to the three shown before", len(cand))
rng = np.random.RandomState(5); first = [c for c in cand if strat(c, 1)]; chosen = [first[rng.randint(len(first))]]
for k in (0, 2):
    pool = [c for c in cand if strat(c, k) and c["source"] not in {x["source"] for x in chosen} and all(not (c["dials"] & x["dials"]) for x in chosen)]
    chosen.append(max(pool, key=lambda c: min(1 - float(c["e"] @ x["e"]) for x in chosen)))
for c in chosen: print(c["id"], c["source"], "|", c["title"][:80], "| clef:", sorted(c["dials"]))
json.dump([c["id"] for c in chosen], open("runs/pulse/mockup_articles.json", "w"))
