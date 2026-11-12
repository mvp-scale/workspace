"""jev_wire: wires the Jev one-pass read into the decider, the BitMob gates and the label store (decision D39: nothing off; the owner: 'the Jev answers need to be wired into the decider and the models and the semantics').
 - Decider: each head answer enters as Source.TRAINED_HEAD with Jev's own confidence (choice confidence, or max(p, 1-p) for a noul), gates_agree from an independent source (the BitMob pulse-reader), and the admission marker from rust_decider/fields_read.json graded by the Python mirror of lean/Admit.lean (route.py's own functions). The decider itself is unchanged and replayed against Lean's vectors first.
 - Harvest: the decider's own buckets say what each answer is for (label queue, needs judge, needs more items, discard).
 - Label store: each read becomes a teacher label in labels_jev_*.jsonl (family jev, same columns as labels.jsonl, plus provenance, evidence ids and offsets), kept apart from the existing store; teacher labels are weak labels (playbook 03).
    /workspace/models/embed-zs/.venv/bin/python jev_wire.py   (from projects/world-state; ROWS=<T135 rows jsonl> TAG=<name>)"""
import os, sys, json, math, re, collections, pathlib
sys.path.insert(0, "."); import decider as D
import span_rules as SR
os.environ["NE"] = os.environ["NL"] = os.environ["NM"] = "0"; sys.path.insert(0, "/workspace/probes/world-engine"); os.environ.setdefault("WE_RULES", "rules_v2")
_ns = {"__name__": "t135defs"}; exec(compile(open("t135_full_read.py").read().split("S = sample(); T0")[0], "t135defs", "exec"), _ns); build_state = _ns["build_state"]
assert D.check_against_lean() > 0
src = open("route.py").read().split("# ---- mirror of Decide.lean")[0]; ns = {}; exec(compile(src, "route_admit", "exec"), ns); dig, wilson, mark = ns["dig"], ns["wilson"], ns["mark"]
ROWS = os.environ.get("ROWS", "/workspace/data/newsreader/labels/full-read-100.jsonl"); TAG = os.environ.get("TAG", "t135"); OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t139")); OUT.mkdir(parents=True, exist_ok=True)
T = json.load(open("rust_decider/fields_read.json")); thr = T["thr_permille"]; F = {}
for f in T["fields"]:
    r = dict(f)
    if f["src"]:
        d = json.load(open(f["src"])); n = int(dig(d, f["n"])); acc = (int(dig(d, f["k"])) / n) if f.get("mode") == "counts" else float(dig(d, f["acc"])); lo, hi = wilson(round(acc * n), n); gs = f["guess"]["permille"] / 1000
        r.update(n=n, low=int(lo * 1000), e=math.ceil((hi - lo) * 500), guess=int(gs * 1000), observed=acc)
    else: r.update(n=0, low=0, e=0, guess=int(f["guess"]["permille"]), observed=None)
    r["marker"] = 1 if (not f["src"] and f["judge"] in ("validator", "outsideGold") and f["contract_confirmed"]) else mark(f["judge"], r["n"], r["e"], r["low"], r["guess"], 800, f["contract_confirmed"], 0)   # an outside judge with no evidence file yet means too few items, never an answer
    F[f["field"]] = r
MN = ["not admissible", "too few items", "below bar", "meets"]
# BitMob gate (the pulse-reader, same as route.py)
from expert1_runtime import ExpertS
E = ExpertS("runs/expert1/expert1_v6b_student.pkl")
text = {}
for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl"): r = json.loads(l); text[r["id"]] = (r["title"], r["text"])
for l in open("/workspace/data/newsreader/labels/t135_ls_sample.jsonl"): r = json.loads(l); text[r["id"]] = (r["title"], r["body"])
for l in open("/workspace/data/anchors/mn_ds/items_fresh2.jsonl"): r = json.loads(l); text[r["id"]] = (r["text"].split(". ")[0][:200], r["text"])
LVN = ["minor", "notable", "major", "severe", "extreme"]
def jev_story_type(a):
    po, pp = a["function_opinion"]["noul"], a["function_prediction"]["noul"]
    if po >= 0.5 and po >= pp: return "opinion", int(1000 * po)
    if pp >= 0.5: return "forecast", int(1000 * pp)
    return "fact", int(1000 * (1 - max(po, pp)))
rows = [json.loads(l) for l in open(ROWS)]; rows = [r for r in rows if "error" not in r]
tally = {k: collections.Counter() for k in F}; harv = {k: collections.Counter() for k in F}; conf = collections.defaultdict(list); gate = collections.defaultdict(list); labels = []; cons = collections.Counter()
for r in rows:
    a = r["answers_call1"]; title, body = text.get(r["id"], (r["title"], "")); bm = E.read(title + ". " + " ".join(body.split()[:60]))
    topic, tconf = a["area_main"]["choice"], int(1000 * a["area_main"]["confidence"]); st, sconf = jev_story_type(a); dom, dconf = a["domain_main"]["choice"], int(1000 * a["domain_main"]["confidence"])
    bm_topics = (bm.get("topic_top2") or {}).get("answer") or []; bm_st = (bm.get("story_type") or {}).get("answer")
    bm_cp = (bm.get("condition_present") or {}).get("answer"); eng_present = bool(r["readings_p328"])
    inp = {"domain_iptc": (dconf, True), "area_topic": (tconf, topic in bm_topics if bm_topics else True), "story_type": (sconf, (st == bm_st) if bm_st else True), "condition_present": (int(1000 * max((x.get("strength", 0.5) for x in r["readings_p328"]), default=0.5)), (bm_cp == eng_present) if bm_cp is not None else True)}   # confidence: the engine's strongest reading strength, 0.5 when it reads nothing
    for k, (c, ag) in inp.items():
        o = D.decide(F[k]["marker"], D.Source.TRAINED_HEAD, True, c, thr, ag); h = D.harvest(o, D.Source.TRAINED_HEAD); tally[k][D.Outcome(o).name] += 1; harv[k][D.Harvest(h).name] += 1; conf[k].append(c); gate[k].append(ag)
    st_, _off = build_state(title, body, r.get("published")); sents = st_["sentences"]
    for dk in r["fired"]:   # evidence path: STATED_FACT, validated when a tool span sits inside the chosen sentence
        ev = r["answers_call2"].get(f"{dk[5:]}__evidence_sentence")
        if not ev or ev["choice"] not in sents: continue
        sp = SR.spans(sents[ev["choice"]]); o = D.decide(F["evidence_fact"]["marker"], D.Source.STATED_FACT, len(sp) > 0, 0, thr, True); h = D.harvest(o, D.Source.STATED_FACT)
        tally["evidence_fact"][D.Outcome(o).name] += 1; harv["evidence_fact"][D.Harvest(h).name] += 1; conf["evidence_fact"].append(int(1000 * ev["confidence"])); gate["evidence_fact"].append(len(sp) > 0)
    conds = []; lv = -1
    for dk in r["fired"]:
        d = dk[5:]; a2 = r["answers_call2"]; dr = a2.get(f"{d}__direction"); sz = a2.get(f"{d}__size"); ev = a2.get(f"{d}__evidence_sentence"); ee = a2.get(f"{d}__evidence_exists")
        if not dr: continue
        level = LVN[min(4, max(0, round(sz["score"])))] if sz else None; lv = max(lv, LVN.index(level) if level else -1)
        conds.append({"condition": d, "direction": dr["choice"] if dr["choice"] in ("up", "down") else None, "direction_probs": dr["probabilities"], "level": level, "evidence_sentence": ev["choice"] if ev else None, "evidence_exists_p": round(ee["noul"], 3) if ee else None, "evidence_offsets": r["sentence_offsets"].get(ev["choice"]) if ev else None, "evidence_tool_spans": [{"kind": x["kind"], "text": x["text"]} for x in SR.spans(sents[ev["choice"]])] if ev and ev["choice"] in sents else []})
    labels.append({"item_id": r["id"], "family": "jev", "model": "jev-1.14.0", "version": r["qset"], "run": f"runs/pulse/{TAG}", "topic": topic, "story_type": st, "n_conditions": len(conds), "kinds": [c["condition"] for c in conds], "max_level": lv,
                   "conditions": conds, "iptc_domain": dom, "provenance": {"teacher": "jev", "ontology_version": r["ontology_version"], "question_set": r["qset"], "state_sha": r["state_sha"], "tokens": r["tokens"], "stored": "raw probabilities in the T135 rows file"}})
    if r["set"] == "label_store": cons["label_store_stories"] += 1; cons["topic_agrees_with_sonnet"] += (topic == r.get("ls_topic")); cons["story_type_agrees_with_sonnet"] += (st == r.get("ls_story_type"))
SCORING = {r["id"] for r in rows if r["set"] == "mnds"}   # outside gold: scoring only, never in the training label file
lab_path = f"runs/label_store/labels_jev_{TAG}.jsonl"; open(lab_path, "w").write("\n".join(json.dumps(x) for x in labels if x["item_id"] not in SCORING))
pathlib.Path("runs/label_store/scoring_only").mkdir(exist_ok=True); open(f"runs/label_store/scoring_only/labels_jev_mnds_{TAG}.jsonl", "w").write("\n".join(json.dumps(x) for x in labels if x["item_id"] in SCORING))
res = {"stories": len(rows), "label_rows_written": len(labels), "label_file": lab_path, "decider_replayed_against_lean_vectors": True,
       "fields": {k: {"marker": MN[F[k]["marker"]], "judge": F[k]["judge"], "n_judge_items": F[k]["n"], "judge_low_end": F[k]["low"] / 1000, "outcomes": dict(tally[k]), "harvest": dict(harv[k]), "mean_confidence": round(sum(conf[k]) / max(len(conf[k]), 1) / 1000, 3), "gate_agreement_with_bitmob": round(sum(gate[k]) / max(len(gate[k]), 1), 3)} for k in F},
       "teacher_consensus_on_label_store_stories": dict(cons), "note": "The decider and its Lean vectors are unchanged. Jev enters as a trained head with confidence and an independent gate; admission comes from outside gold or a validator, never from agreement between models. Teacher labels are weak labels (playbook 03)."}
json.dump(res, open(OUT / "t139_jev_wire.json", "w"), indent=1); print(json.dumps(res, indent=1))
