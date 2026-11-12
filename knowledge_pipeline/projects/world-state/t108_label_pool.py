"""T108: label pool articles with the two-call dial and direction labeller on hosted Jev (decision D25, public crawled news text only, cost stated in the card). Random sample of the embedded CC-News pool (T95 pool_meta), title plus the first 400 words as the labeller sees them (validated in T107), the first 1200 words kept for the students.
    N=<articles> OUT=<folder> BACKEND=jev /workspace/models/embed-zs/.venv/bin/python -u t108_label_pool.py -> <OUT>/labels.jsonl, <OUT>/t108_label_pool.json"""
import os, sys, json, random, re, time, urllib.request, concurrent.futures as cf, collections, pathlib
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
import pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
N = int(os.environ.get("N", 10000)); OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t108")); OUT.mkdir(parents=True, exist_ok=True)
ONT = {c["id"]: c for c in json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json"))["conditions"]}
D = {k: f"{c['name']}: {c['definition']}" for k, c in ONT.items()}; D["none"] = "The story does not report a change in any of these conditions."
def _key():
    for l in open("/workspace/secrets/vault.env"):
        if l.startswith("TYPESAFE_API_KEY="): return l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
    return ""
HDR = {"Content-Type": "application/json", "User-Agent": "kp-t108/0.1", "Authorization": "Bearer " + _key()}; URL = "https://api.typesafe.ai/v1/systemone"; TOK = [0]; ERR = [0]
meta = [json.loads(l) for l in open("runs/pulse/t95/pool_meta.jsonl")]; random.Random(108).shuffle(meta); pick = {m["url"] for m in meta[:int(N * 1.15)]}
rows = []
for f in sorted(__import__("glob").glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "title", "text"]); mk = pc.is_in(t["url"], value_set=pa.array(list(pick)))
    for r in t.filter(mk).to_pylist():
        w = " ".join((r["text"] or "").split())
        if len(w.split()) >= 60 and len((r["title"] or "").strip()) >= 10: rows.append({"url": r["url"], "title": r["title"].strip(), "body": " ".join(w.split()[:1200])})
random.Random(1).shuffle(rows); rows = rows[:N]
def ask(state, instr, crit):
    b = {"state": state, "questions": {"k": {"type": "choice", "instructions": instr, "criteria": crit}}, "model": "jev-1.14.0"}; last = None
    for a_ in range(4):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(URL, json.dumps(b).encode(), HDR), timeout=90)); TOK[0] += (j.get("usage") or {}).get("input_tokens", 0); a = j["answers"]["k"]; return a["choice"], a.get("confidence")
        except Exception as ex:
            last = ex; ERR[0] += 1; time.sleep(2 + 3 * a_)
    raise last
def one(r):
    try:
        st = "News story:\n" + (r["title"] + "\n" + " ".join(r["body"].split()[:400]))[:2800]; dial, c1 = ask(st, "Which one condition of the world does this story report a change in? Choose none if it reports no such change.", D)
        if dial == "none" or dial not in ONT: return {**r, "dial": "none", "direction": None, "conf": c1}
        dr, c2 = ask(st, f"The condition is '{ONT[dial]['name']}'. Does the story report it going up or down? Up means: {ONT[dial]['up_means']}.", {"up": "It goes up: " + ONT[dial]["up_means"], "down": "It goes down: the reverse of that"}); return {**r, "dial": dial, "direction": dr, "conf": c1}
    except Exception: return {**r, "dial": "error", "direction": None, "conf": None}
hb.beat("t108-label-pool", state="running", where="[HOST]", every_s=180, alive_pid=os.getpid(), why="Label pool articles with hosted Jev for the dial and direction students (T108, D25)", success="labels.jsonl written", progress=f"0 of {len(rows)}")
T0 = time.time(); c = collections.Counter(); n = 0
with open(OUT / "labels.jsonl", "w") as f, cf.ThreadPoolExecutor(12) as ex:
    for res in ex.map(one, rows):
        f.write(json.dumps(res) + "\n"); n += 1; c[res["dial"]] += 1
        if n % 500 == 0: hb.beat("t108-label-pool", progress=f"{n} of {len(rows)} at {n / (time.time() - T0):.1f} per s, {TOK[0]} tokens")
out = {"share_with_dial": round(sum(v for k, v in c.items() if k not in ("none", "error")) / max(len(rows), 1), 4), "articles": len(rows), "with_dial": sum(v for k, v in c.items() if k not in ("none", "error")), "none": c["none"], "errors": c["error"], "dial_counts_top": c.most_common(8), "input_tokens": TOK[0], "cost_usd_at_0_042_per_million": round(TOK[0] * 0.042 / 1e6, 3), "call_errors_retried": ERR[0], "seconds": round(time.time() - T0), "per_s": round(len(rows) / (time.time() - T0), 1)}
json.dump(out, open(OUT / "t108_label_pool.json", "w"), indent=1); hb.finish("t108-label-pool", "done", progress=f"{len(rows)} articles"); print(json.dumps(out, indent=1))
