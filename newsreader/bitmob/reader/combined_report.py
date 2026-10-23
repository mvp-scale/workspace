"""Report for the combined reader run: six steps (fallback, needs Clef) + BitMob-alone on the same stories + Clef time/questions vs the full engine on the control stories.
  /workspace/kev/.venv/bin/python newsreader/bitmob/reader/combined_report.py > data/diag/combined_reader_2026-10-22.txt"""
import sys, json, numpy as np
sys.path.insert(0, "/workspace/newsreader/bitmob/reader"); import combined_score as S
recs = [json.loads(l) for l in open("/workspace/data/diag/combined/combined_out.jsonl")]; ids = {r["id"] for r in recs}; assert len(ids) == len(recs)
sc = S.score(recs)
alone = {m: json.load(open(f"/workspace/data/diag/combined/bitmob_alone_{m}.json")) for m in ("r6c1", "r7")}
print(f"COMBINED READER 'BitMob + Clef check' = FALLBACK (needs Clef), real Clef Flash Q4 on Kaggle 2xT4, {len(recs)} fixed-seed frozen-test stories (seed 20261022), scored with score_mh.py definitions vs Clef's stored full-battery answers.")
print("Settings: shortlist cut 0.14275 (95%, tune-fit), gate d=0.30 (>=95% tune), BitMob round-6 for everything, round-7 for country. No value below is a BitMob pass; the Clef-assisted column is a fallback.\n")
f = lambda v: json.dumps(v) if isinstance(v, dict) else str(v)
print(f"{'step':26s} {'bar':58s} {'FALLBACK (needs Clef)':32s} {'BitMob alone r6c1':24s} {'BitMob alone r7':20s}")
for k in ("P-0016", "P-0017", "P-0018", "P-0019", "P-0020", "P-0021"):
    def a(m):
        v = alone[m][k]; v = v["value"] if isinstance(v, dict) and "value" in v else v
        if k == "P-0017": return f"TPR {v['TPR']} FPR {v['FPR']}" if isinstance(v, dict) else v
        if k == "P-0018": return f"share {v['share_AP>=.7']}, topics {v['mean_topics_model']}/{v['mean_topics_clef']}"
        return v
    v = sc[k]["value"]; vv = f"TPR {v['TPR']} FPR {v['FPR']} ({v['false_alarms']} fa)" if k == "P-0017" else (f"share {v['share_AP>=.7']} ({v['domains_scored']} dom), topics {v['mean_topics_model']}/{v['mean_topics_clef']}" if k == "P-0018" else v)
    print(f"{k+' '+sc[k]['step']:26s} {sc[k]['bar'][:56]:58s} {str(vv)+(' bar met WITH Clef' if sc[k]['pass'] else ' bar MISSED'):32s} {str(a('r6c1')):24s} {str(a('r7')):20s}")
print("(Steps 3 topics, 4 country, 6 severity use BitMob only in the fallback, so those values equal BitMob alone: round-6 for topics/severity, round-7 for country. Steps 1, 2, 5 are the Clef-assisted ones.)\n")
o = [r["out"] for r in recs]; m = lambda g: float(np.mean([g(x) for x in o]))
print(f"FALLBACK COST on {len(o)} stories: Clef seconds/story {m(lambda x: x['clef_s']):.2f} (median {np.median([x['clef_s'] for x in o]):.2f}); Clef questions/story {m(lambda x: x['clef_questions']):.1f} of 328; Clef calls/story {m(lambda x: x['clef_calls']):.2f}; gate block asked on {m(lambda x: x['gate_unsure']):.1%}; shortlist {m(lambda x: x['shortlist_n']):.1f} cells/story")
ph = {}
for x in o:
    for a in x["asked"]: p = ph.setdefault(a["phase"], [0, 0, 0.0]); p[0] += 1; p[1] += a["n_q"]; p[2] += a["secs"]
print("  by phase (calls, questions, seconds, per story): " + "; ".join(f"{k} {v[0]}/{v[1]}/{v[2]:.0f}s/{v[2]/len(o):.2f}s" for k, v in ph.items()))
C_ = [r for r in recs if "ctrl" in r]
if C_:
    cs = lambda r: r["out"]["clef_s"]; fa = np.mean([r["ctrl"]["phases"]["ask"]["s"] for r in C_]); ft = np.mean([r["ctrl"]["total_s"] for r in C_]); fq = np.mean([r["ctrl"]["total_q"] for r in C_]); rs = np.mean([cs(r) for r in C_])
    print(f"BASELINE, same kernels/T4s, {len(C_)} control stories: engine's full Clef path {ft:.1f} s/story (ask {fa:.1f}, " + ", ".join(f"{k} {np.mean([r['ctrl']['phases'][k]['s'] for r in C_]):.1f}" for k in ('place', 'country', 'expected', 'severity')) + f"), {fq:.0f} questions, {np.mean([r['ctrl']['total_calls'] for r in C_]):.0f} calls")
    print(f"  fallback on the same {len(C_)} stories: {rs:.1f} s = {rs/fa:.0%} of the 17-call ask phase, {rs/ft:.0%} of the whole engine path; questions {np.mean([r['out']['clef_questions'] for r in C_]):.0f} vs ask 328 / total {fq:.0f}")
    print(f"  all {len(o)} stories: fallback {m(lambda x: x['clef_s']):.2f} s = {m(lambda x: x['clef_s'])/fa:.0%} of ask phase, {m(lambda x: x['clef_s'])/ft:.0%} of whole engine path")
    rep = np.mean([np.mean([abs(r['ctrl']['F'][k] - S.R[r['id']]['P'][k]) for k in r['ctrl']['F']]) for r in C_]); print(f"  control rerun vs stored answers: mean |diff| {rep:.4f}")
print("\nBitMob CPU local: 107 ms/story for both models (heads precomputed by combined_prep.py).")
json.dump({"fallback": sc, "bitmob_alone": alone}, open("/workspace/data/diag/combined/combined_scores.json", "w"), indent=1)
