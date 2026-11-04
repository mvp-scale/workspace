"""Teacher labels vs Clef labels on the same stories. Compares sets of (condition, direction). Free; reads two files."""
import json, sys
lab = {}
for l in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(l); lab[r["item_id"]] = {(c["condition"], c["direction"]) for c in r["label"]["conditions"]}
clef = {}
for l in open(sys.argv[2], encoding="utf-8"):
    r = json.loads(l); clef[r["id"]] = ({(x["dial"], x["direction"]) for x in r["read"]["readings"] if x["direction"] != "conflict"}, r["read"]["gate_ok"])
ids = [i for i in lab if i in clef]
def prf(sel):
    tp = sum(len(lab[i] & clef[i][0]) for i in sel); fp = sum(len(lab[i] - clef[i][0]) for i in sel); fn = sum(len(clef[i][0] - lab[i]) for i in sel)
    p = tp / (tp + fp) if tp + fp else 0; r = tp / (tp + fn) if tp + fn else 0
    return f"stories {len(sel)} | Clef readings {tp + fn} | teacher readings {tp + fp} | agree {tp} | precision {p:.2f} recall {r:.2f}"
print("all stories     :", prf(ids)); print("Clef gate passed:", prf([i for i in ids if clef[i][1]]))
print("note: Clef readings count only when its gate passed; this measures how much two different LLMs agree, not who is right.")
