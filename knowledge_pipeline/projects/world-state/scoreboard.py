"""scoreboard: one row per funnel step, each against outside truth (owner yes L2756). Every number is read from a result file when one exists; a step with no result file says 'not started'.
    scoreboard.py <trace dir> [--out file]     build() -> list of rows; funnel_view.py writes it next to the trace as scoreboard.json (the simulation page's section 'Scoreboard').
Row: step, truth_set, score, bar, last_round, next_lever, status (met | below | measured, no bar | not started | check failed), sources (files read)."""
import sys, os, json, re, time, pathlib
HERE = pathlib.Path(__file__).resolve().parent
def jl(p, default=None):
    try: return json.load(open(HERE / p if not str(p).startswith("/") else p))
    except FileNotFoundError: return default
def day(p):
    try: return time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(HERE / p)))
    except OSError: return "?"
def build(tr=None):
    rows = []; ns = lambda step, truth, lever: {"step": step, "truth_set": truth, "score": "not started", "bar": "not set", "last_round": "none", "next_lever": lever, "status": "not started", "sources": []}
    r1 = jl("runs/pulse/topic_loop/r1/results.json"); wire = jl("runs/pulse/topic_loop/r1/live_wire_v7.json"); lw = (wire or {}).get("agreement") or {}
    if r1:
        c = r1["confirm"]["P1"]; n, npub = r1["confirm_n"]; bar = 0.60; top1 = c["top1"]["option"]; land = c["top1"]["landing"]; nx = r1.get("next_primary") or {}; gp = (nx.get("gains_pts") or {}).get(nx.get("choice"))
        sc = "confirm top-1 %.3f (landing alone %.3f), macro recall %.3f; %d items, %d publishers never trained on" % (top1, land, c["macro_recall"]["option"], n, npub) + ("; live publisher-section agreement %.3f (landing alone %.3f) on %s (%d articles with a publisher section)" % (lw["reranker"], lw["landing_alone"], (wire.get("run") or {}).get("run_id"), wire["section_articles"]) if lw else "")
        rows.append({"step": "Topic", "truth_set": "MN-DS human topic labels, clean confirm half (publisher split, ledger L2751)", "score": sc, "bar": "top-level topic 0.60 on MN-DS (build spec 2.1)", "last_round": "r1 (T158), %s, %s" % (day("runs/pulse/topic_loop/r1/results.json"), "ADOPT" if (r1.get("keep_rule_P1") or {}).get("decision") == "ADOPT" else "not adopted"),
                     "next_lever": "%s%s" % (nx.get("choice") or "none named", " (predicted +%.1f points on select)" % gp if gp else ""), "status": "met" if top1 >= bar else "below", "sources": ["runs/pulse/topic_loop/r1/results.json"] + (["runs/pulse/topic_loop/r1/live_wire_v7.json"] if wire else [])})
    else: rows.append(ns("Topic", "MN-DS human topic labels", "run round 1"))
    rows.append(ns("Names", "Few-NERD (human entity labels)", "start with the round template: published structure, CPU model, publisher-split clean test"))
    rows.append(ns("Events / direction", "SENTiVENT (human event and direction labels)", "start with the round template"))
    cb = jl("runs/harvest/relations/carb_score.json"); h = jl("runs/pulse/t151/head_table.json")
    if cb:
        x = cb["results"][0]; rows.append({"step": "Claims", "truth_set": cb["data"] + " (human triples)", "score": "CaRB-style overlap F1 %.3f (precision %.3f, recall %.3f), %s; %d of %d gold triples not recovered" % (x["f1"], x["precision"], x["recall"], cb["scorer"], cb["unrecovered_gold_triples"], x["gold"]), "bar": "none set (head table: set a bar for the extractor)", "last_round": "carb_score.json, %s (old ledger T42)" % day("runs/harvest/relations/carb_score.json"),
                     "next_lever": next((r["next_action"] for r in (h or {}).get("rows", []) if r["head"].startswith("Claims")), "recall: 0.31"), "status": "measured, no bar", "sources": ["runs/harvest/relations/carb_score.json", "runs/pulse/t151/head_table.json"]})
    else: rows.append(ns("Claims", "CaRB (human triples)", "score the extractor on CaRB"))
    rows.append(ns("Places", "GeoNames / WikiNER place labels", "start with the round template"))
    lg = jl(os.path.join(tr, "ledger.json")) if tr else None; sh = (lg or {}).get("split_half") or {}; ck = sh.get("m4_checks") or []
    if ck:
        bad = [x["check"] for x in ck if x["result"] == "FAIL"]; rows.append({"step": "World state", "truth_set": "none outside: publisher halves test consistency, not truth; dated events list not built", "score": "%d of %d pre-registered split-half checks pass (run %s, %d counted articles)" % (len(ck) - len(bad), len(ck), (lg["as_of"] or {}).get("run_id"), sh.get("items", 0)), "bar": "all checks inside the ranges written before the first run",
                     "last_round": "ledger_split.py, %s" % (lg.get("built_at") or "?"), "next_lever": "failed: " + "; ".join(bad) if bad else "dated events (needs the events list)", "status": "check failed" if bad else "met", "sources": [os.path.join(tr, "ledger.json")]})
    else: rows.append(ns("World state", "dated events (list not built)", "python ledger_split.py <trace> --write"))
    rows.append(ns("Learn", "MN-DS fresh2 (student rounds) and the loop's own confirm halves", "start with the round template"))
    return rows
if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None; r = build(t); print(json.dumps(r, indent=1))
    if "--out" in sys.argv: json.dump({"built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": r}, open(sys.argv[sys.argv.index("--out") + 1], "w"), indent=1)
