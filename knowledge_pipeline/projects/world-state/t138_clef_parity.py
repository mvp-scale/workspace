"""T138: Clef parity on the one-pass read. The same call-1 request (144 questions: noul and choice) and the same call-2 request (noul, choice and score) that hosted Jev answered in T135 go to local Clef (port 8018) for N engine stories; answers are compared with Jev's saved answers. Records whether Clef accepts the request size and the Score type, and per-head agreement. Local GPU, owner yes needed.
    N=<stories> OUT=<folder> ROWS=<jsonl of T135> /workspace/kev/.venv/bin/python -I t138_clef_parity.py (from /workspace/probes/world-engine) -> <OUT>/t138_clef_parity.json"""
import os, sys, json, re, time, urllib.request, urllib.error, collections, pathlib
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); os.environ.setdefault("NE", "0"); os.environ.setdefault("NL", "0"); os.environ.setdefault("NM", "0")
src = open("/workspace/knowledge_pipeline/projects/world-state/t135_full_read.py").read().split("S = sample(); T0")[0]; exec(compile(src, "t135defs", "exec"))   # question builders, state builder, COND
N = int(os.environ.get("N", 10)); OUT = pathlib.Path(os.environ.get("OUT", "/workspace/knowledge_pipeline/projects/world-state/runs/pulse/t138")); OUT.mkdir(parents=True, exist_ok=True)
J = [json.loads(l) for l in open(os.environ.get("ROWS", "/workspace/data/newsreader/labels/full-read-100.jsonl"))]; J = [r for r in J if "error" not in r and r["set"] == "engine"][:N]
bodies = {}
for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl"):
    r = json.loads(l); bodies[r["id"]] = r
def clef(qs, state):
    body = {"state": state, "questions": qs, "model": "clef-flash-q4km"}; req = urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t138/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r: return json.load(r)["answers"], None
    except urllib.error.HTTPError as e: return None, f"HTTP {e.code}: {e.read()[:200]!r}"
    except Exception as e: return None, repr(e)[:200]
rows = []; T0 = time.time()
for j in J:
    b = bodies[j["id"]]; st, off = build_state(b["title"], b["text"], None)
    a1, e1 = clef(Q1, st); chunked = False
    if a1 is None:   # request too large: ask in batches of 20 as the engine does for Clef
        a1 = {}; chunked = True; ks = list(Q1)
        for i in range(0, len(ks), 20):
            a, e = clef({k: Q1[k] for k in ks[i:i + 20]}, st)
            if a: a1.update(a)
    fired = j["fired"]; a2, e2 = clef(build_q2(st, fired, j["answers_call1"]["place_region"]["choice"]), st) if fired else ({}, None)
    sc_ok = None; 
    if fired:
        d = fired[0][5:]; one, es = clef({f"{d}__size": build_q2(st, fired[:1], "GLOBAL")[f"{d}__size"]}, st); sc_ok = one is not None
    rows.append({"id": j["id"], "call1_error": e1, "chunked": chunked, "n_answers": len(a1), "call2_error": e2, "score_accepted": sc_ok, "a1": a1, "jev": j["answers_call1"]})
ok = [r for r in rows if r["n_answers"]]
nd = []; ch = []; per = collections.defaultdict(list)
for r in ok:
    for k, ja in r["jev"].items():
        ca = r["a1"].get(k)
        if not ca: continue
        if ja["type"] == "noul": d = abs(ja["noul"] - ca["noul"]); nd.append(d); per[k.split("_")[0]].append(d)
        elif ja["type"] == "choice": ch.append(ja["choice"] == ca["choice"])
res = {"stories": len(rows), "stories_with_answers": len(ok), "call1_request_accepted_whole": sum(1 for r in rows if r["call1_error"] is None), "call1_errors": [r["call1_error"] for r in rows if r["call1_error"]][:3], "needed_batches_of_20": sum(r["chunked"] for r in rows),
       "call2_errors": [r["call2_error"] for r in rows if r["call2_error"]][:3], "score_accepted_share": round(sum(1 for r in rows if r["score_accepted"]) / max(sum(1 for r in rows if r["score_accepted"] is not None), 1), 3),
       "noul_mean_abs_diff_clef_vs_jev": round(sum(nd) / max(len(nd), 1), 4), "noul_agree_within_0.2": round(sum(d < 0.2 for d in nd) / max(len(nd), 1), 4), "choice_exact_agreement": round(sum(ch) / max(len(ch), 1), 4),
       "noul_mean_abs_diff_by_head": {h: round(sum(v) / len(v), 4) for h, v in per.items()}, "seconds": round(time.time() - T0), "note": "Agreement between two models, not accuracy. Same request, same stories."}
json.dump(res, open(OUT / "t138_clef_parity.json", "w"), indent=1); print(json.dumps(res, indent=1))
