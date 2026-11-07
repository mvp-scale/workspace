"""One tool, one input: analyze(title, body, date) -> the Pulse, with the working.
Combines (1) the trained topic and story-type reader run over the WHOLE article in 64-piece windows, (2) the solver's stated facts (amounts, dates, names), (3) the decider (rules proved in lean/Decide.lean) fed by the field table (runs/pulse/field_table.json).
    /workspace/models/embed-zs/.venv/bin/python analyze.py 100     (from projects/world-state; runs it on 100 full MN-DS articles)"""
import json, re, sys, time, random, collections, numpy as np
sys.path.insert(0, "."); from expert1_runtime import ExpertS; from article_reader import ArticleReader, _soft
_src = open("stated_facts.py").read().split("# ---------------- 4102 stories")[0]; exec(_src, globals())      # the fact functions only; importing the file would rerun its whole job
OUT = ["abstain: field not admitted", "abstain: too few items", "abstain: not validated", "abstain: low confidence", "abstain: gates disagree", "ANSWER (provisional)", "ANSWER"]
def decide(m, s, v, c, thr, a):                                                  # mirror of lean/Decide.lean, checked against its 160 cases in route.py
    if m == 0: return 0
    if m == 1: return 1
    if s == 0 and not v: return 2
    if s == 1 and c < thr: return 3
    if s == 1 and not a: return 4
    return 5 if m == 2 else 6
class Analyzer:
    def __init__(self, thr=700):
        self.e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); self.A = ArticleReader(self.e); self.thr = thr; self.FT = json.load(open("runs/pulse/field_table.json"))
    def analyze(self, title, body, date=None):
        T = {}; t0 = time.perf_counter(); S = self.e.S; W = self.A.windows(body); PT, PS = [], []
        for w in W:
            v = self.e.student(title + ". " + w); PT.append(_soft(v @ S["t_W"].T + S["t_b"])); PS.append(_soft(v @ S["s_W"].T + S["s_b"]))
        pt, ps = np.mean(PT, axis=0), np.mean(PS, axis=0); o2 = np.argsort(-pt)[:2]; T["reader_ms"] = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter(); text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; facts, _, _ = facts_for(text, (date + "T00:00:00Z") if date else None); T["solver_ms"] = (time.perf_counter() - t1) * 1000
        am = [f for f in facts if f["kind"] == "amount" and f["status"] == "stated"]; dt = [f for f in facts if f["kind"] == "date" and f["status"] == "stated"]; nm = [f for f in facts if f["kind"] == "name"]
        prop = {"story_type": (1, int(1000 * ps.max()), True, S["story_cl"][int(ps.argmax())], "reader, " + str(len(W)) + " windows"),
                "topic": (1, int(1000 * pt[o2].sum()), True, " / ".join(S["topic_cl"][k] for k in o2), "reader, " + str(len(W)) + " windows"),
                "change": (0, 0, False, "not run", "no extractor wired yet"),
                "size": (0, 0, bool(am), "; ".join(f["text"] + " (" + (f["noun"] or f["verb"] or "") + ")" for f in am[:4]) or "no stated amount", "solver stated facts: " + str(len(am)) + " amounts stated"),
                "traits": (0, 0, False, "not run", "no extractor wired yet")}
        t2 = time.perf_counter(); res = {}
        for k, (src, conf, ok, ans, how) in prop.items():
            m = self.FT[k]["marker"]; o = decide(m, src, ok if src == 0 else True, conf, self.thr, True)
            res[k] = {"decision": OUT[o], "answer": ans if o >= 5 else None, "proposed": ans, "confidence": conf / 1000 if src == 1 else None, "how": how}
        T["decider_ms"] = (time.perf_counter() - t2) * 1000; T["total_ms"] = sum(T.values())
        return {"fields": res, "evidence": {"stated_amounts": [f["text"] for f in am[:8]], "stated_dates": [f["text"] for f in dt[:5]], "names": len(nm), "windows": len(W)}, "ms": {k: round(v, 2) for k, v in T.items()}}
if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    gl = {v["l1"] for v in json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")).values()}; M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]
    R = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]; R = [r for r in R if r.get("content") and r.get("title") and r["category_level_1"] in gl and len(r["content"]) >= 800]
    random.seed(20261106); S = random.sample(R, N); X = Analyzer(); rows = []; tot = []
    for r in S:
        o = X.analyze(r["title"], r["content"], r.get("date")); tot.append(o["ms"]["total_ms"])
        g = r["category_level_1"]; top = o["fields"]["topic"]; right = any(g in M.get(x.strip(), []) for x in (top["proposed"] or "").split(" / "))
        rows.append({"title": r["title"][:80], "human": g, "right": right, "fields": {k: v["decision"] for k, v in o["fields"].items()}, "topic": top["proposed"], "conf": top["confidence"], "amounts": o["evidence"]["stated_amounts"][:3], "ms": o["ms"]["total_ms"]})
    tot.sort(); C = collections.Counter(); 
    for x in rows:
        for k, v in x["fields"].items(): C[(k, v)] += 1
    ans = [x for x in rows if x["fields"]["topic"].startswith("ANSWER")]; held = [x for x in rows if not x["fields"]["topic"].startswith("ANSWER")]
    summ = {"articles": N, "ms_median": round(tot[N // 2]), "ms_p95": round(tot[int(.95 * N) - 1]), "decisions": {f"{k}: {v}": n for (k, v), n in sorted(C.items())},
            "topic_answered": len(ans), "topic_answered_right": sum(x["right"] for x in ans), "topic_held": len(held), "topic_held_right": sum(x["right"] for x in held)}
    json.dump({"summary": summ, "rows": rows}, open("runs/pulse/analyze_demo.json", "w"), indent=1); print(json.dumps(summ, indent=1))
