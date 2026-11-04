"""T20 step 1 pilot (look before the sweep): is the 10 percent reach a model limit or a Haiku-vs-Sonnet teacher gap? Old 1,466 test items, v5-leaf. Local, CPU."""
import json, glob, sys, numpy as np
sys.path.insert(0, "."); from expert1_runtime import Expert3
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; hk = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
oi = sorted(hk); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; ids = [i for i in test if i in sn]
reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}["v5-leaf"]; e = Expert3(reg["path"]); R = [e.read(pool[i]["text"]) for i in ids]
sp = np.array([bool(sn[i]["conditions"]) for i in ids]); hp = np.array([bool(hk[i]["conditions"]) for i in ids])
conf = np.array([r["condition_present"].get("confidence") or 0 for r in R]); yes = np.array([bool(r["condition_present"].get("answer")) for r in R]); ans = np.array([r["condition_present"]["status"] == "answered" for r in R]); cut = None
f = ans & yes
def line(name, m): print(f"{name:42s} n={int(m.sum()):4d}  found(answered yes)={f[m].mean():.3f}  says yes at all={yes[m].mean():.3f}  mean conf={conf[m].mean():.3f}")
line("Sonnet+ and Haiku+", sp & hp); line("Sonnet+ but Haiku-", sp & ~hp); line("Sonnet- and Haiku+", ~sp & hp); line("Sonnet- and Haiku-", ~sp & ~hp)
print("Haiku-Sonnet presence agreement", round(float((sp == hp).mean()), 3), "| Sonnet+ share", round(float(sp.mean()), 3), "Haiku+ share", round(float(hp.mean()), 3))
print("reach vs Sonnet", round(float(f[sp].mean()), 3), "| reach vs Haiku positives (training target)", round(float(f[hp].mean()), 3))
# threshold curve on presence confidence for the 'yes' side (exploratory)
pr = np.array([r["condition_present"].get("confidence") for r in R], dtype=float)
print("answered share", round(float(ans.mean()), 3), "| yes among answered", round(float(yes[ans].mean()), 3))
