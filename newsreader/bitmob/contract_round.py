#!/usr/bin/env python3
"""Append one scored round to data/progress/contract.json (D-0038 loop).  python3 newsreader/bitmob/contract_round.py add-round round.json
Round JSON: {round, made?, stories_added, stories_total, labelling:{five090:{stories,min,per_min}, kaggle:[{kernel,stories,min,per_min,gpu_h?}]}, wall_min, five090_min,
 kaggle_gpu_h?, rows:{P-0016:{value,bar,pass,note,n,text?}}, lever:{row,why}}.
Missing kaggle gpu_h (per session and total) is filled from the Kaggle run ledger ($KAGGLE_RUNS_LEDGER / data/kaggle/runs.jsonl) by kernel name. 'bar' is the numeric pass mark, higher is better."""
import json, sys, os, datetime
W = "/workspace"; F = f"{W}/data/progress/contract.json"
def kaggle_h(kernel):
    led = os.environ.get("KAGGLE_RUNS_LEDGER") or f"{W}/data/kaggle/runs.jsonl"; h = 0.0
    try:
        for l in open(led):
            r = json.loads(l)
            if r.get("kernel", "").split("/")[-1] == kernel.split("/")[-1] and r.get("status") != "ERROR-IGNORE": h += float(r.get("gpu_h_wall") or r.get("gpu_h_meter") or 0)
    except Exception: pass
    return round(h, 3)
def add(rd):
    d = json.load(open(F)) if os.path.exists(F) else {"rounds": []}
    rd.setdefault("made", datetime.datetime.now().isoformat(timespec="seconds"))
    ks = (rd.get("labelling") or {}).get("kaggle") or []
    for k in ks:
        if k.get("gpu_h") is None: k["gpu_h"] = kaggle_h(k["kernel"])
    if rd.get("kaggle_gpu_h") is None: rd["kaggle_gpu_h"] = round(sum(k["gpu_h"] for k in ks), 3)
    d["rounds"] = [r for r in d["rounds"] if r.get("round") != rd["round"]] + [rd]; d["rounds"].sort(key=lambda r: r["round"])
    json.dump(d, open(F, "w"), indent=1); print("rounds:", [r["round"] for r in d["rounds"]])
if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "add-round": add(json.load(open(sys.argv[2])))
    else: print(__doc__)
