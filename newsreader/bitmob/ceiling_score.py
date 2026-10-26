"""R-0181 scorer: Clef against itself. For stories in the ceiling outputs, compare the original Clef answers (data/clef-labels/test.jsonl, P) with the rerun on the engine's own blocks (F1) and on regrouped blocks (F2).
Per step: gate agreement (engine gate_ok), conditions = the engine's (dial, direction) readings (original readings re-found / extra readings per story). Trivial baselines beside each.
  WE_RULES=rules_v2 WORLD_GPU=0 /workspace/kev/.venv/bin/python newsreader/bitmob/ceiling_score.py OUT.txt"""
import os, sys, glob, json
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona"]
import classify as C
O = {}
for l in open("/workspace/data/clef-labels/test.jsonl"):
    r = json.loads(l); O[r["id"]] = r["P"]
R = [json.loads(l) for f in sorted(glob.glob("/workspace/data/kaggle/screen_ceil*/out/screen_ceil[0-9].jsonl")) for l in open(f)]
def view(P):
    x = C.read(P); return x["gate_ok"], {(d["dial"], d["direction"]) for d in x["readings"]}
out = [f"Clef against itself, {len(R)} stories (original answers vs rerun). Files: data/kaggle/screen_ceil*/out"]
for arm, name in (("F1", "same blocks again"), ("F2", "regrouped blocks")):
    g_ok = n_orig = n_found = n_extra = 0; g_pos = 0; cell_pos = cell_found = 0
    for r in R:
        po = O[r["id"]]; pr = r[arm]; go, so = view(po); gr, sr = view(pr)
        g_ok += go == gr; g_pos += go; n_orig += len(so); n_found += len(so & sr); n_extra += len(sr - so)
        for k, v in po.items():
            if k.startswith("a|") and v >= 0.5: cell_pos += 1; cell_found += pr[k] >= 0.5
    n = len(R); base = max(g_pos, n - g_pos) / n
    out.append(f"{arm} ({name}): gate agrees on {g_ok/n:.1%} (always-majority baseline {base:.1%}); engine readings re-found {n_found}/{n_orig} = {n_found/max(n_orig,1):.1%}, extra readings {n_extra/n:.2f}/story; attribute cells >=0.5 in original re-found {cell_found}/{cell_pos} = {cell_found/max(cell_pos,1):.1%}")
out.append(f"time per story: rerun same blocks {sum(r['t1'] for r in R)/len(R):.1f} s, regrouped {sum(r['t2'] for r in R)/len(R):.1f} s")
open(sys.argv[1], "w").write("\n".join(out) + "\n"); print("\n".join(out))
