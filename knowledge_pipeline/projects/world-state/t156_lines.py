"""T156 (ledger T-0033): decision lines chosen on one split and scored once on another, from saved Jev rows (no new reads).
    python3 t156_lines.py (from projects/world-state) -> runs/pulse/t156/t156_lines.json"""
import csv, json, random
D = "/workspace/data/anchors/checkthat_subj/"
def ba(rows, f, thr):
    P = [r for r in rows if r["pos"]]; N = [r for r in rows if not r["pos"]]; return (sum(f(r) >= thr for r in P) / len(P) + sum(f(r) < thr for r in N) / len(N)) / 2
def pick(rows, f):
    g = [round(0.05 * k, 2) for k in range(1, 20)]; s = {t: ba(rows, f, t) for t in g}; best = max(g, key=lambda t: (s[t], -abs(t - 0.5))); return best, s[best]
def boot(rows, f, thr):
    rng = random.Random(1); b = sorted(ba([rng.choice(rows) for _ in rows], f, thr) for _ in range(500)); return [round(b[12], 3), round(b[487], 3)]
res = {}
# Function: choose on dev_en, score once on test_en_labeled
rows = {r["id"]: r for r in json.load(open("runs/pulse/t148/t148_checkthat_function.json"))["rows"] if "error" not in r}
def split(name):
    out = []
    for r in csv.DictReader(open(D + name + ".tsv", encoding="utf-8"), delimiter="\t"):
        x = rows.get("ct:" + r["sentence_id"])
        if x: out.append({"pos": x["gold"] == "SUBJ", "p": x["noul"]["function_opinion"]})
    return out
sel, tst = split("dev_en"), split("test_en_labeled"); f = lambda r: r["p"]; thr, sa = pick(sel, f)
res["function"] = {"select_set": "dev_en", "n_select": len(sel), "line": thr, "bal_acc_select": round(sa, 3), "score_set": "test_en_labeled", "n_score": len(tst), "bal_acc_at_0_5_on_score_set": round(ba(tst, f, 0.5), 3), "bal_acc_at_line_on_score_set": round(ba(tst, f, thr), 3), "ci95": boot(tst, f, thr)}
# Factuality: choose on a random half of documents, score once on the other half (both directions reported)
rows = [r for r in json.load(open("runs/pulse/t152/t152_factuality_maven.json"))["rows"] if "error" not in r]; docs = sorted({r["id"].split(":")[1] for r in rows}); random.Random(156).shuffle(docs); A = set(docs[:len(docs) // 2])
for r in rows: r["pos"] = r["yes"]; r["p"] = r["happened"]
S = [r for r in rows if r["id"].split(":")[1] in A]; T = [r for r in rows if r["id"].split(":")[1] not in A]; thr, sa = pick(S, f)
res["factuality"] = {"select_half_events": len(S), "line": thr, "bal_acc_select": round(sa, 3), "score_half_events": len(T), "bal_acc_at_0_5_on_score_half": round(ba(T, f, 0.5), 3), "bal_acc_at_line_on_score_half": round(ba(T, f, thr), 3), "ci95": boot(T, f, thr)}
thr2, sb = pick(T, f); res["factuality"]["swap_check"] = {"line_chosen_on_other_half": thr2, "bal_acc_on_first_half": round(ba(S, f, thr2), 3)}
res["note"] = "Lines chosen by maximum balanced accuracy on the selection split only; score split touched once. Function test set is 300 sentences so its interval is wide. Events within a document share the half."
json.dump(res, open("runs/pulse/t156/t156_lines.json", "w"), indent=1); print(json.dumps(res, indent=1))
