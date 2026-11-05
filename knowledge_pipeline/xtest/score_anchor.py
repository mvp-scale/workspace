"""Score one rater's topic answers against an outside anchor through a mapping (ledger T28). Written independently of the inline check used on 2026-11-04 so the two can be compared.
    python3 score_anchor.py <results.jsonl> <gold.json> <mapping.json>
Lenient: the gold category is in the accepted set of the rater's topic. Strict: it equals the first listed category. A topic answer of 'other', an unknown label, or a failed answer counts as a miss on answered items; unanswered items are reported, not counted."""
import json, math, sys
res, gold, spec = sys.argv[1:4]
M = json.load(open(spec))["map"]; G = json.load(open(gold))
ans = {}
for line in open(res):
    x = json.loads(line)
    if x.get("field") == "topic" and x.get("ok"): ans[x["item"]] = x["label"]
ids = sorted(set(ans) & set(G)); n = len(ids)
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - h, 3), round(c + h, 3)
lenient = sum(1 for i in ids if G[i]["l1"] in M.get(ans[i], []))
strict = sum(1 for i in ids if M.get(ans[i]) and G[i]["l1"] == M[ans[i]][0])
print(json.dumps({"gold_items": len(G), "unanswered": len(set(G) - set(ans)), "n": n, "lenient": lenient, "lenient_rate": round(lenient / n, 3), "lenient_ci95": wilson(lenient, n), "strict": strict, "strict_rate": round(strict / n, 3), "strict_ci95": wilson(strict, n), "said_other": sum(1 for i in ids if ans[i] == "other")}))
