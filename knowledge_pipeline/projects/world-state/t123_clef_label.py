"""T123: label stories of the news queue (data/newsreader/queue.sqlite, headline plus teaser, the engine's 1736 stories left out) with the two-call dial and direction labeller on hosted Jev (decision the owner yes for the local GPU, public RSS headlines and teasers only, no article text). Output: labels.jsonl for the CPU students (T112)."""
import os, sys, json, random, re, time, urllib.request, concurrent.futures as cf, collections, pathlib
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
N = int(os.environ.get("N", 10000)); OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t123")); OUT.mkdir(parents=True, exist_ok=True)
ONT = {c["id"]: c for c in json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json"))["conditions"]}
D = {k: f"{c['name']}: {c['definition']}" for k, c in ONT.items()}; D["none"] = "The story does not report a change in any of these conditions."
def _unused_key():
    for l in open("/workspace/secrets/vault.env"):
        if l.startswith("TYPESAFE_API_KEY="): return l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
    return ""
HDR = {"Content-Type": "application/json", "User-Agent": "kp-t123/0.1"}; URL = "http://127.0.0.1:8018/v1/systemone"; TOK = [0]; ERR = [0]
import sqlite3
eng = set()
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn): eng.add(json.loads(l)["id"])
cn = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
jev = [json.loads(l) for l in open("runs/pulse/t111/labels.jsonl")]
rows = [{"id": r["id"], "url": r["url"], "title": r["title"], "body": r["body"]} for r in jev if r["id"] not in eng][:N]  # the same stories Jev labelled, so teacher agreement is measurable
def ask(state, instr, crit):
    b = {"state": state, "questions": {"k": {"type": "choice", "instructions": instr, "criteria": crit}}, "model": "clef-flash-q4km"}; last = None
    for a_ in range(4):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(URL, json.dumps(b).encode(), HDR), timeout=90)); TOK[0] += (j.get("usage") or {}).get("input_tokens", 0); a = j["answers"]["k"]; return a["choice"], a.get("confidence")
        except Exception as ex:
            last = ex; ERR[0] += 1; time.sleep(2 + 3 * a_)
    raise last
def one(r):
    try:
        st = "News story:\n" + (r["title"] + ". " + r["body"])[:1200]; dial, c1 = ask(st, "Which one condition of the world does this story report a change in? Choose none if it reports no such change.", D)
        if dial == "none" or dial not in ONT: return {**r, "dial": "none", "direction": None, "conf": c1}
        dr, c2 = ask(st, f"The condition is '{ONT[dial]['name']}'. Does the story report it going up or down? Up means: {ONT[dial]['up_means']}.", {"up": "It goes up: " + ONT[dial]["up_means"], "down": "It goes down: the reverse of that"}); return {**r, "dial": dial, "direction": dr, "conf": c1}
    except Exception: return {**r, "dial": "error", "direction": None, "conf": None}
hb.beat("t123-label-pool", state="running", where="[HOST]", every_s=180, alive_pid=os.getpid(), why="Label pool articles with hosted Jev for the dial and direction students (T123, the owner yes for the local GPU)", success="labels.jsonl written", progress=f"0 of {len(rows)}")
T0 = time.time(); c = collections.Counter(); n = 0
with open(OUT / "labels.jsonl", "w") as f, cf.ThreadPoolExecutor(4) as ex:
    for res in ex.map(one, rows):
        f.write(json.dumps(res) + "\n"); n += 1; c[res["dial"]] += 1
        if n % 500 == 0: hb.beat("t123-label-pool", progress=f"{n} of {len(rows)} at {n / (time.time() - T0):.1f} per s, {TOK[0]} tokens")
out = {"share_with_dial": round(sum(v for k, v in c.items() if k not in ("none", "error")) / max(len(rows), 1), 4), "articles": len(rows), "with_dial": sum(v for k, v in c.items() if k not in ("none", "error")), "none": c["none"], "errors": c["error"], "dial_counts_top": c.most_common(8), "input_tokens": TOK[0], "cost_usd_at_0_042_per_million": round(TOK[0] * 0.042 / 1e6, 3), "call_errors_retried": ERR[0], "seconds": round(time.time() - T0), "per_s": round(len(rows) / (time.time() - T0), 1)}
json.dump(out, open(OUT / "t123_label_queue.json", "w"), indent=1); hb.finish("t123-label-pool", "done", progress=f"{len(rows)} articles"); print(json.dumps(out, indent=1))
