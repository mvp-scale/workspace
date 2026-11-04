"""Summary for the traits bundle (B4) from score.json and the main runs: per trait the panel alpha, verdict and pooled yes share; SKEWED if the pooled yes share is under 0.05 or over 0.95 (declared in ledger L690 before the result). Prints counts per verdict and the CLEAR and TENTATIVE lists by group.
    /workspace/models/embed-zs/.venv/bin/python -I traits_summary.py <bundle> <score.json> rater1 rater2 ..."""
import json, sys, collections
b, sj, raters = sys.argv[1], sys.argv[2], sys.argv[3:]; B = json.load(open(f"{b}/bundle.json")); S = json.load(open(sj)); Q = {x["id"]: x for x in json.load(open("/workspace/knowledge_pipeline/projects/world-state/specs/traits_v0.json"))["questions"]}
yes = collections.defaultdict(list)
for r in raters:
    for l in open(f"{b}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: yes[x["field"]].append(x["label"] == "yes")
rows = []
for f, res in S["fields"].items():
    p = res["panel"]; share = sum(yes[f]) / max(len(yes[f]), 1); skew = share < 0.05 or share > 0.95
    rows.append((f, B["groups"][f], p["alpha"], p["ci95"], "SKEWED" if skew else p["verdict"], share, Q[f[2:]]["question"]))
c = collections.Counter(r[4] for r in rows); print("verdict counts:", dict(c), "of", len(rows))
for v in ("CLEAR", "TENTATIVE"):
    print(f"\n{v}:"); [print(f"  {r[0]} [{r[1]}] alpha {r[2]} {r[3]} yes share {r[5]:.2f} - {r[6][:70]}") for r in rows if r[4] == v]
g = collections.defaultdict(collections.Counter)
for r in rows: g[r[1]][r[4]] += 1
print("\nby group:"); [print(f"  {k:17s} {dict(v)}") for k, v in g.items()]
print("\nsame-rater paraphrase alpha, median over questions:")
for r in raters:
    v = sorted(S["fields"][f]["self"][r]["paraphrase"]["alpha"] for f in S["fields"]); print(f"  {r:6s} median {v[len(v)//2]:.3f}  min {v[0]:.3f}")
