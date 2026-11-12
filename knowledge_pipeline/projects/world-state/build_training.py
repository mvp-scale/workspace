"""Builds knowledge_pipeline/training/training.json for the viewer's Training tab. Reads result files only; the ledger is not an input.
    python3 build_training.py"""
import json, glob, os, time, collections
P = "runs/pulse/"; OUT = "../../training/training.json"
roll = json.load(open(P + "model_rollout.json"))["rows"]
runs = []
import datetime
def stamp(f): return datetime.datetime.fromtimestamp(os.path.getmtime(f), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
def active_for(task):
    """A run is live when a runs-live row that names its task is running; the curve then refreshes with the poller."""
    for f in glob.glob("../../runs-live/*.json"):
        try: r = json.load(open(f))
        except Exception: continue
        if r.get("state") == "running" and task.lower() in (f + " " + str(r.get("progress", "")) + " " + str(r.get("job", ""))).lower(): return os.path.basename(f)[:-5]
    return None
def add(tag, label, f, labels, seed=None):
    d = json.load(open(f)); pts = [{"epoch": p["epoch"], "step": p["step"], **p["dev"], "composite": p["composite"], "train_loss": p["train_loss"]} for p in d["dev_curve"]]
    best = max(range(len(pts)), key=lambda i: pts[i]["composite"]) if pts else None
    runs.append({"id": tag, "label": label, "labels": labels, "seed": seed, "planned_epochs": d["planned_epochs"], "stop_reason": d["stop_reason"], "best_index": best, "points": pts, "sealed": d["sealed"], "judge": d["judge"], "task": tag.split("-")[0], "family": "encoder", "updated": stamp(f), "file": os.path.basename(f), "reached_epoch": pts[-1]["epoch"] if pts else 0, "active": active_for(tag.split("-")[0])})
add("T56", "T56 monitored run, hard Sonnet labels", P + "finetune_cpu2.json", "hard")
for t, lab, lb, sd in (("r0", "T60 r0 hard labels", "hard", 7), ("r1", "T60 r1 soft votes", "soft", 11), ("r2", "T60 r2 hard labels", "hard", 11)): add("T60-" + t, lab, P + f"finetune3_{t}.json", lb, sd)
base = json.load(open(P + "finetune_cpu2.json"))["sparse_default_sealed"]
fam = collections.Counter(json.loads(l)["family"] for l in open("runs/label_store/labels.jsonl"))
out = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "note": "Scores are agreement with Sonnet labels on the sealed set (1,499 items), not outside truth. Noise across seeds: about 0.009 topic, 0.007 story type, 0.019 presence F1.",
       "baseline_sparse_sealed": base, "teacher_label_counts": dict(fam), "models": roll, "runs": runs,
       "entity_bakeoff": None}
if os.path.exists("runs/t67/kaggle/ner_bakeoff.json"):
    eb = json.load(open("runs/t67/kaggle/ner_bakeoff.json")); eb["systems"] = {k: v for k, v in eb["systems"].items() if "error" not in v}
    for f_ in sorted(glob.glob("runs/t68/local/ner_bakeoff_*.json")):
        for k, v in json.load(open(f_)).get("systems", {}).items():
            if "error" not in v: eb["systems"][k] = v
    out["entity_bakeoff"] = eb
def hb(j):
    try: return json.load(open(f"../../runs-live/{j}.json"))
    except Exception: return {}
k = hb("kaggle-kp-t67-ner-bakeoff"); t68 = hb("t68-ner-installs"); ent = out["entity_bakeoff"] or {}
have = sorted(ent.get("systems", {})) if ent else []
nov = [m["model"] for m in roll if not str(m.get("status", "")).startswith("v1")]
out["live"] = [{"job": f[:-5].split("/")[-1], **{a: hb(f[:-5].split("/")[-1]).get(a) for a in ("state", "progress", "updated", "last")}} for f in sorted(glob.glob("../../runs-live/*.json")) if any(x in f for x in ("t6", "t7", "t8", "kaggle", "finetune", "train"))]
t83 = hb("t83-paired"); t83_state = "running (CPU), " + str(t83.get("progress", "")) if t83.get("state") == "running" else "done" if (P + "t83/t82_rerank.json") and os.path.exists(P + "t83/t82_rerank.json") else "ready"
out["next_flow"] = [
 {"n": 1, "step": "T83: paired interval on the T82 rerank gain (+4.3 points)", "state": t83_state, "why": "Says whether the gain is real or noise.", "gate": "none, CPU"},
 {"n": 2, "step": "Area: train the first model on supported triples and mapped terms, with a dev curve", "state": "ready (CPU)", "why": "Area has no trained model; a weak v1 still fills the row.", "gate": "none"},
 {"n": 3, "step": "Capability and Novelty: write exact inputs and outputs, then the same steps as Area", "state": "ready (CPU)", "why": "Both rows have only a partial definition.", "gate": "none"},
 {"n": 4, "step": "Understanding (triples): trained head with a leakage check", "state": "ready (CPU)", "why": "Extractor results exist (T73 to T82); no head is trained.", "gate": "none"},
 {"n": 5, "step": "Encoder run for the rows with no encoder run: " + ", ".join(nov[:5]), "state": "ready (CPU)", "why": "Same recipe as T60: dev-chosen epoch, sealed set read once, curve shown here.", "gate": "none"},
 {"n": 6, "step": "Local Clef as a teacher for the IPTC term mapping", "state": "needs owner yes", "why": "Uses the 5090 as a labeller; the one lever left on the 30% level-2 match.", "gate": "owner"},
 {"n": 7, "step": "Adopt a new encoder on the Engine card", "state": "needs owner yes", "why": "Engine change (step 5 of the method).", "gate": "owner"}]
kr = []
for s_ in (7, 11, 13):
    try: d_ = json.load(open(P + f"heademb_kinds_s{s_}.json"))
    except Exception: continue
    pts = d_["curve"]; kr.append({"seed": s_, "points": pts, "best_dev": d_["best_dev"], "best_index": max(range(len(pts)), key=lambda i: pts[i]["dev"]), "stop": d_["stop"], "sealed": d_["sealed"], "dev_baseline_most_common_kind": d_["dev_baseline_most_common_kind"], "dev_baseline_top3_kinds": d_["dev_baseline_top3_kinds"], "task": "T69", "family": "kinds", "updated": stamp(P + f"heademb_kinds_s{s_}.json"), "file": f"heademb_kinds_s{s_}.json", "reached_epoch": pts[-1]["epoch"], "active": active_for("T69")})
out["kinds_runs"] = kr
ar = []
if os.path.exists(P + "t84/t84_area_head.json"):
    a_ = json.load(open(P + "t84/t84_area_head.json")); f_ = P + "t84/t84_area_head.json"
    ar.append({"task": "T84", "family": "area", "seed": 7, "points": a_["curve"], "best_epoch": a_["best_epoch"], "stop": a_["stop"], "fresh": a_["fresh"], "fresh2": a_["fresh2"], "updated": stamp(f_), "file": "t84_area_head.json", "reached_epoch": a_["curve"][-1]["epoch"], "active": active_for("T84")})
out["area_runs"] = ar
# CPU students and heads on the engine stories (T109 to T122): result files only, a missing file is skipped
def _j(p, *keys):
    try:
        d = json.load(open(P + p))
        for k in keys: d = d[k]
        return d
    except Exception: return None
students = []
for tid, label, view, labels, p, k in (
    ("T109", "Pool-news Jev labels, word counts", "headline plus teaser", "9,779 Jev", "t109/t109_students.json", ("headline_view_largest",)),
    ("T112", "Queue Jev labels, word counts", "headline plus teaser", "19,894 Jev", "t112/t112_students.json", ("headline_view_largest",)),
    ("T113", "Queue Jev labels, bge-small embedding", "headline plus teaser", "19,894 Jev", "t113/t113_students.json", ("headline_view_largest",)),
    ("T115", "All queue Jev labels, word counts", "headline plus teaser", "31,005 Jev", "t115/t112_students.json", ("headline_view_largest",)),
    ("T116", "Engine readings only (grouped folds)", "headline plus teaser", "1,388 engine readings per fold", "t116/t116_mix.json", ("engine_only",)),
    ("T116", "Engine readings plus Jev labels", "headline plus teaser", "1,388 engine + 30,989 Jev", "t116/t116_mix.json", ("mix",)),
    ("T119", "Engine readings only, word counts", "full text", "1,388 engine readings per fold", "t119/t119_engine_full.json", ("counts",)),
    ("T119", "Engine readings, counts plus embedding", "full text", "1,388 engine readings per fold", "t119/t119_engine_full.json", ("counts_plus_embedding",)),
    ("T122", "Learning curve at 300 readings", "full text", "300 engine readings", "t122/t122_curve.json", ("curve", "300")),
    ("T122", "Learning curve at 1000 readings", "full text", "1,000 engine readings", "t122/t122_curve.json", ("curve", "1000")),
    ("T122", "Learning curve, all readings", "full text", "1,388 engine readings per fold", "t122/t122_curve.json", ("curve", "0")),
    ("T128", "Encoder fine-tuned on engine readings (fold 0)", "headline plus teaser", "1,780 engine readings", "t128/t128_finetune.json", ("finetuned",)),
    ("T128", "Sparse heads, same fold as the fine-tune", "headline plus teaser", "1,979 engine readings", "t128/t128_finetune.json", ("sparse_same_split",)),
    ("T125", "Mixed training rerun with paired intervals", "headline plus teaser", "1,388 engine + 30,989 Jev", "t125/t125_mix.json", ("mix",))):
    r_ = _j(p, *k)
    if r_: students.append({"task": tid, "label": label, "view": view, "labels": labels, "presence_auroc": r_.get("presence_auroc"), "direction_accuracy": r_.get("direction_accuracy"), "file": "runs/pulse/" + p})
out["students"] = students
from flow_audit import audit
out["audit"] = audit()
os.makedirs(os.path.dirname(OUT), exist_ok=True); json.dump(out, open(OUT, "w"), indent=1); print(len(runs), "runs", len(roll), "models")
