"""T20 traits pilot scoring (ledger L451). Per question: valid-reply share, 'cannot tell' share, self-agreement of each model across its two runs (exact, within one step), Sonnet-Haiku agreement on run 1. READY = Sonnet self within-one >= 0.90 and Sonnet-Haiku within-one >= 0.80. Agreement between models, never accuracy."""
import json, pathlib, collections, numpy as np
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; base = pathlib.Path("runs/pulse/traits_pilot"); Q = {q["id"]: q for q in json.load(open("specs/traits_v0.json"))["questions"]}
L = {}
for d in ("sonnet_r1", "sonnet_r2", "haiku_r1", "haiku_r2"):
    f = base / d / "labels.jsonl"; L[d] = {r["item_id"]: r["label"] for r in J(f)} if f.exists() else {}
ORD = {"not at all": 0, "slightly": 1, "clearly": 2, "strongly": 3}
def agree(a, b):
    if a == b: return 1, 1
    if a == "cannot tell" or b == "cannot tell": return 0, 0
    return 0, int(abs(ORD[a] - ORD[b]) <= 1)
n_items = len(J(base / "items.jsonl")); out = {"n_items": n_items, "valid_replies": {d: len(v) for d, v in L.items()}, "questions": {}, "groups": {}}
def pair(x, y, q):
    ids = [i for i in L[x] if i in L[y]]; r = [agree(L[x][i][q], L[y][i][q]) for i in ids]; return (round(float(np.mean([a for a, _ in r])), 3), round(float(np.mean([b for _, b in r])), 3), len(ids)) if r else (None, None, 0)
for q in Q:
    ct = [L["sonnet_r1"][i][q] == "cannot tell" for i in L["sonnet_r1"]]
    ss, sh, hh = pair("sonnet_r1", "sonnet_r2", q), pair("haiku_r1", "haiku_r2", q), pair("sonnet_r1", "haiku_r1", q)
    out["questions"][q] = {"group": Q[q]["group"], "question": Q[q]["question"], "cannot_tell_sonnet": round(float(np.mean(ct)), 3) if ct else None, "sonnet_self_exact": ss[0], "sonnet_self_within1": ss[1], "haiku_self_exact": sh[0], "haiku_self_within1": sh[1], "sonnet_haiku_exact": hh[0], "sonnet_haiku_within1": hh[1], "ready": bool(ss[1] is not None and ss[1] >= 0.90 and hh[1] is not None and hh[1] >= 0.80)}
G = collections.defaultdict(list)
for q, v in out["questions"].items(): G[v["group"]].append(v)
for g, vs in G.items(): out["groups"][g] = {"n_questions": len(vs), "ready": sum(v["ready"] for v in vs), "sonnet_self_within1_mean": round(float(np.mean([v["sonnet_self_within1"] for v in vs])), 3), "sonnet_haiku_within1_mean": round(float(np.mean([v["sonnet_haiku_within1"] for v in vs])), 3), "cannot_tell_mean": round(float(np.mean([v["cannot_tell_sonnet"] for v in vs])), 3)}
allq = list(out["questions"].values()); out["overall"] = {"ready": sum(v["ready"] for v in allq), "of": len(allq), "cannot_tell_mean": round(float(np.mean([v["cannot_tell_sonnet"] for v in allq])), 3), "sonnet_self_within1_mean": round(float(np.mean([v["sonnet_self_within1"] for v in allq])), 3), "sonnet_self_exact_mean": round(float(np.mean([v["sonnet_self_exact"] for v in allq])), 3), "haiku_self_within1_mean": round(float(np.mean([v["haiku_self_within1"] for v in allq])), 3), "sonnet_haiku_within1_mean": round(float(np.mean([v["sonnet_haiku_within1"] for v in allq])), 3), "questions_sonnet_self_under_0.85": sum(v["sonnet_self_within1"] < 0.85 for v in allq)}
json.dump(out, open("runs/pulse/traits_pilot_result.json", "w"), indent=1); print(json.dumps({"valid": out["valid_replies"], "overall": out["overall"], "groups": out["groups"]}, indent=1))
