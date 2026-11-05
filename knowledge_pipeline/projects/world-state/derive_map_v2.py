"""T28 v2 crosswalk: for each of our topics, accept the IPTC categories that humans gave to the items where Clef and Gemma BOTH chose that topic (dev sample only, 1676 clean items). Share >= 0.15, at most 4 categories, v1 kept when a topic has fewer than 10 dev items. Test on a FRESH sample only (ledger T28)."""
import json, collections
v1 = json.load(open("specs/topic_to_iptc_v1.json")); M1 = v1["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28_clean.json"))
def load(rt):
    r = {}
    for l in open(f"runs/xtest/B6/runs/{rt}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["field"] == "topic" and x["ok"]: r[x["item"]] = x["label"]
    return r
C, Ge = load("clef"), load("gemma")
agree = [i for i in G if i in C and i in Ge and C[i] == Ge[i] and C[i] != "other"]
by = collections.defaultdict(list)
for i in agree: by[C[i]].append(G[i]["l1"])
M2 = {}; notes = {}
for t in M1:
    if t == "other": M2[t] = []; continue
    v = by.get(t, [])
    if len(v) < 10: M2[t] = M1[t]; notes[t] = f"kept v1 (only {len(v)} dev items)"; continue
    c = collections.Counter(v); sel = [k for k, n in c.most_common() if n / len(v) >= 0.15][:4]
    M2[t] = sel or [c.most_common(1)[0][0]]; notes[t] = f"{len(v)} dev items; " + ", ".join(f"{k} {n/len(v):.2f}" for k, n in c.most_common(4))
spec = {"version": "topic_to_iptc_v2", "note": "Empirical crosswalk derived from the dev sample (items where Clef and Gemma agree on the topic). Measures consistency with human labels under the raters own behaviour; it is not an a-priori definition. Test on a fresh sample only.", "iptc": v1["iptc"], "map": M2, "derivation": notes}
json.dump(spec, open("specs/topic_to_iptc_v2.json", "w"), indent=1)
ch = [(t, M1[t], M2[t]) for t in M1 if M1[t] != M2[t]]
print("agreed dev items", len(agree), "| topics changed", len(ch))
for t, a, b in ch[:50]: print(f"{t}: {a} -> {b}")
