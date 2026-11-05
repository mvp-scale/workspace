"""T40 step 2 part 1: ask Qwen (local vLLM, served as qwen on port 8102) to copy word for word the shortest part of each positive item that states the answer; validate that it is an exact substring; draw a same-length random word window as control.
Positives = items where at least 2 of 3 raters said yes in bundle B14 (natural sample). Traits x025 x013 x031 and a seeded sample of 60 for x034. Writes runs/xtest/B15_quotes.json.
    python3 span_quotes.py   (from projects/world-state, Qwen server running)"""
import json, os, random, sys, collections, urllib.request, concurrent.futures as cf
R = ["clef", "gemma", "qwen"]; B = os.environ.get("SPAN_BUNDLE", "runs/xtest/B14"); TR = os.environ.get("SPAN_TRAITS", "t_x025 t_x013 t_x031 t_x034").split(); OUTQ = os.environ.get("SPAN_OUT", "runs/xtest/B15_quotes.json")
Q = ({t: v["question"] for t, v in json.load(open(os.environ["SPAN_QFILE"])).items()} if os.environ.get("SPAN_QFILE") else {"t_" + x["id"]: x["question"] for x in json.load(open("specs/traits_v0.json"))["questions"]})
txt = {r["id"]: r["text"] for r in map(json.loads, open(f"{B}/items.jsonl"))}
ans = {r: collections.defaultdict(dict) for r in R}
for r in R:
    for l in open(f"{B}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: ans[r][x["field"]][x["item"]] = 1 if x["label"] == "yes" else 0
rng = random.Random(20261108); sel = []
for t in TR:
    ids = sorted(set.intersection(*[set(ans[r][t]) for r in R])); pos = [i for i in ids if sum(ans[r][t][i] for r in R) >= 2]
    if t == "t_x034": pos = rng.sample(pos, 60)
    sel += [(t, i) for i in pos]
norm = lambda s: " ".join(s.split())
def ask(t, i):
    prompt = f"News item:\n{txt[i]}\n\nQuestion: {Q[t]}\nThe answer is yes. Copy, word for word, the shortest part of the news item that states this. Output only the copied words, nothing else."
    body = json.dumps({"model": "qwen", "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 160, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request("http://127.0.0.1:8102/v1/chat/completions", data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer local"})
    with urllib.request.urlopen(req, timeout=120) as r: out = json.load(r)["choices"][0]["message"]["content"]
    return out
def clean(q): return norm(q).strip().strip('"\'“”‘’').strip()
res = []
with cf.ThreadPoolExecutor(8) as ex:
    futs = {ex.submit(ask, t, i): (t, i) for t, i in sel}
    for f, (t, i) in futs.items():
        try: q = clean(f.result())
        except Exception as e: q = ""
        res.append((t, i, q))
out = []
for t, i, q in sorted(res):
    text = norm(txt[i]); valid = bool(q) and q in text and len(q.split()) <= 40
    w = text.split(); n = len(q.split()) if valid else min(12, len(w)); n = max(1, min(n, len(w))); s = rng.randrange(0, len(w) - n + 1); control = " ".join(w[s:s + n])
    out.append({"trait": t, "item": i, "quote": q, "valid": valid, "control": control})
json.dump(out, open(OUTQ, "w"), indent=1)
c = collections.Counter((o["trait"], o["valid"]) for o in out); print({t: {"n": sum(v for (tt, _), v in c.items() if tt == t), "valid": c.get((t, True), 0)} for t in TR})
