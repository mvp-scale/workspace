"""T42: data for demo/mockups/decider/index.html. All 1600 MN-DS fresh human-labelled articles are read by the topic head; 120 are drawn at random (seed 20261105) to display; the curves use all 1600.
    /workspace/models/embed-zs/.venv/bin/python decider_mockup_data.py   (from projects/world-state)"""
import json, sys, random, re
sys.path.insert(0, "."); from expert1_runtime import ExpertS
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {json.loads(l)["id"]: json.loads(l)["text"] for l in open("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); R = []
for i, t in items.items():
    r = e.read(t)["topic_top2"]; g = G[i]["l1"]; maps = [sorted(M.get(x, [])) for x in r["answer"]]
    R.append({"id": i, "text": re.sub(r"\s+", " ", t).strip(), "human": g, "guesses": r["answer"], "maps": maps, "conf": int(round(1000 * r["confidence"])), "right": any(g in m for m in maps)})
n = len(R); err = sum(1 for r in R if not r["right"])
curve = []
for line in range(0, 1001, 10):
    a = [r for r in R if r["conf"] >= line]; ab = [r for r in R if r["conf"] < line]
    curve.append({"line": line, "answered": len(a), "answered_right": sum(r["right"] for r in a), "abstained": len(ab), "abstained_right": sum(r["right"] for r in ab)})
S = sorted(R, key=lambda r: r["conf"]); capture = []
for p in range(0, 101, 5):
    k = int(p / 100 * n); capture.append({"pct_reviewed": p, "errors_found": sum(1 for r in S[:k] if not r["right"])})
random.seed(20261105); sample = sorted(random.sample(R, 120), key=lambda r: r["conf"])
import numpy as np
def soft(z): z = z - z.max(); p = np.exp(z); return p / p.sum()
def dec(m, s_, v, c, thr, a):
    if m == 0: return 0
    if m == 1: return 1
    if s_ == 0 and not v: return 2
    if s_ == 1 and c < thr: return 3
    if s_ == 1 and not a: return 4
    return 5 if m == 2 else 6
FT = json.load(open("runs/pulse/field_table.json")); TOPIC_MARKER = FT["topic"]["marker"]; maxdiff = 0
for r in sample:
    full = items[r["id"]]; t = re.sub(r"\s+", " ", full); ids = e.stk.encode(t[:1200]).ids; v = e.student(full)
    z = v @ e.S["t_W"].T + e.S["t_b"]; pt = soft(z); o2 = np.argsort(-pt)[:2]
    ref = e.read(full)["topic_top2"]; assert [e.S["topic_cl"][k] for k in o2] == ref["answer"]; d = abs(float(pt[o2].sum()) - ref["confidence"]); maxdiff = max(maxdiff, d); assert d < 1e-9
    enc = e.stk.encode(t[:1200]); cut = max(b for a, b in enc.offsets)
    r.update(text_full=t[:1200], cut_char=int(cut), chars_in=len(t), chars_used=min(len(t), 1200), tokens=len(ids), vdim=int(len(v)), vnorm=round(float(np.linalg.norm(v)), 4), v8=[round(float(x), 4) for x in v[:8]],
             logits=[round(float(x), 9) for x in z], conf_float=ref["confidence"], by_line="".join(str(dec(TOPIC_MARKER, 1, False, r["conf"], L, True)) for L in range(0, 1001, 10)))
    # which words mattered: remove one word at a time from the part the reader reads, re-read, and see how much the first guess's probability falls
    read_part = t[:cut]; rest = t[cut:]; ws = read_part.split(" "); g1 = int(o2[0]); pa = float(pt[g1]); infl = []
    for k in range(len(ws)):
        t2 = " ".join(ws[:k] + ws[k + 1:]) + rest; p2 = soft(e.student(t2) @ e.S["t_W"].T + e.S["t_b"])
        infl.append(round(pa - float(p2[g1]), 4))
    r["words"] = ws; r["influence"] = infl; r["rest"] = rest
    r["text"] = t[:260]
print("replica vs reader: max difference in confidence", maxdiff)
out = {"classes": e.S["topic_cl"], "max_tokens": e.S["max_tokens"], "reader_cut": e.M["cuts"]["topic_top2"], "topic_row": dict(FT["topic"], bar=800, rare_low=0), "other_rows": {k: FT[k] for k in FT if k != "topic"}, "vectors": [l.strip() for l in open("rust_decider/vectors.txt")], "n": n, "errors": err, "curve": curve, "capture": capture, "sample": sample,
       "src": {"articles": "/workspace/data/anchors/mn_ds/items_T28b.jsonl", "human_labels": "/workspace/data/anchors/mn_ds/gold_T28b.json", "guess_to_label_map": "specs/topic_to_iptc_v1.json", "reader": "runs/expert1/expert1_v6b_student.pkl (pulse-reader)", "ledger": "L980 L981 L983 L984"}}
json.dump(out, open("/workspace/demo/mockups/decider/data.json", "w")); print(n, err, len(sample), sum(1 for r in sample if not r["right"]), "errors in the 120")
