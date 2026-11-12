"""T104: teacher ceiling for the Area. Does local Clef (port 8018, approved in CLAUDE.md, already serving) choose the IPTC depth-1 Area better than the embedding mapping? Two typed choice calls per item: the top-level category (17 options), then the depth-1 term under it (options with their definitions). Scored on MN-DS fresh2 in-vocabulary items against the human level-2 labels, scoring only (MN-DS is not used to train anything), paired with the embedding mapping under the same reader constraint on the same items.
    NP=<items> OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t104_clef_teacher.py -> <OUT>/t104_clef_teacher.json"""
import os, sys, json, random, time, urllib.request, concurrent.futures as cf
os.environ.setdefault("MODEL", "BAAI/bge-small-en-v1.5"); os.environ.setdefault("TERM", "def"); os.environ.setdefault("NP", "0")
exec(open("t81_arm.py").read().split("h2 = [G")[0])
NPI = int(os.environ.get("NPI", 300)); h2 = [G[i]["l2"].lower() for i in ids]; h1 = [G[i]["l1"].lower() for i in ids]; inv = np.array([x in set(D1) for x in h2]); tag = np.array([src[i] for i in ids])
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
byq = {c["qcode"]: c for c in O}; labl = lambda c: (c["prefLabel"].get("en-GB") or next(iter(c["prefLabel"].values()))).lower(); defn = {labl(c): ((c.get("definition") or {}).get("en-GB", "")[:140]) for c in O}
tops = sorted({top_of[n] for n in names}); under = {t: [n for n in names if top_of[n] == t] for t in tops}
sel = [k for k in range(len(ids)) if tag[k] == "fresh2" and inv[k]]; random.Random(11).shuffle(sel); sel = sel[:NPI]
def ask(state, instr, crit):
    body = {"state": state, "questions": {"k": {"type": "choice", "instructions": instr, "criteria": crit}}, "model": "clef-flash-q4km"}
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=300)
    return json.load(r)["answers"]["k"]["choice"]
def one(k):
    st = "News item:\n" + txt[ids[k]][:900]
    t = ask(st, "Which broad subject area is this news item mainly about?", {x: x for x in tops}); u = under[t] if t in under else names
    n = ask(st, "Within that area, which specific subject is this news item mainly about?", {x: (defn.get(x) or x) for x in u})
    return k, t, n
hb.beat("t104-clef-teacher", state="running", where="[5090]", every_s=180, alive_pid=os.getpid(), why="Does local Clef choose the Area better than the embedding mapping (T104 teacher ceiling)", success="t104_clef_teacher.json written", progress=f"0 of {len(sel)}")
T0 = time.time(); res = {}
with cf.ThreadPoolExecutor(6) as ex:
    for n_done, (k, t, n) in enumerate(ex.map(one, sel), 1):
        res[k] = (t, n)
        if n_done % 25 == 0: hb.beat("t104-clef-teacher", progress=f"{n_done} of {len(sel)} at {n_done / (time.time() - T0):.2f} items/s")
hc = np.array([int(res[k][1] == h2[k]) for k in sel]); he = np.array([int(names[int(np.argmax(ASc[k]))] == h2[k]) for k in sel]); h1c = np.array([int(res[k][0] == h1[k] or (res[k][0], h1[k]) in {("politics and government", "politics"), ("religion", "religion and belief")}) for k in sel])
rs = np.random.RandomState(0); bs = sorted(float((hc - he)[rs.randint(0, len(sel), len(sel))].mean()) for _ in range(3000))
out = {"items": len(sel), "clef_exact_l2": round(float(hc.mean()), 4), "embedding_exact_l2": round(float(he.mean()), 4), "paired_clef_minus_embedding": round(float((hc - he).mean()), 4), "ci95": [round(bs[75], 4), round(bs[2924], 4)], "clef_top_level_vs_human_l1": round(float(h1c.mean()), 4), "seconds": round(time.time() - T0), "items_per_s": round(len(sel) / (time.time() - T0), 3), "note": "Teacher check only: MN-DS fresh2 in-vocabulary items, human level-2 labels, scoring only. Two choice calls per item to local Clef."}
OUT = os.environ.get("T73DIR", os.environ.get("OUT", OUT)); os.makedirs(OUT, exist_ok=True); json.dump(out, open(OUT + "/t104_clef_teacher.json", "w"), indent=1); hb.finish("t104-clef-teacher", "done", progress=f"{len(sel)} items"); print(json.dumps(out, indent=1))
