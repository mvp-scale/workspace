"""verify_trace: check a live trace folder (schema live_trace_schema.json, T160; live_trace_schema_v4.json for live-trace-v4 runs). Read-only on the folder.
    verify_trace.py <trace folder>                recompute the chain, seq gaps, text sha1, allowlist
    verify_trace.py <trace folder> --replay N     also re-run N traced articles (by id, from the queue) twice in fresh processes and compare every stage's state, n and out (ms ignored)"""
import sys, os, json, hashlib, subprocess, random
ALLOW = ["id", "url", "source", "title", "teaser", "body", "published", "ready_at"]
HERE = os.path.dirname(os.path.abspath(__file__)); PY = "/workspace/models/embed-zs/.venv/bin/python"
ROOTS = ("first", "generic_title", "no_key")
def jcheck(al, srcs):
    """journal of one traced line against the lines before it: shape, dup kind vs source, publishers recomputed, SYNDICATED gap. Returns a reason or None."""
    j = al["journal"]; d = j.get("dup") or {}; k = d.get("kind"); o = d.get("of_seq"); s = al["seq"]; ids = j.get("ids") or {}
    if k not in ROOTS + ("copy", "republished"): return "journal.dup.kind %r" % k
    if j.get("permission") != "public-news" or not isinstance(j.get("label_version"), dict) or set(j.get("story_key") or {}) != {"title", "prefix"}: return "journal permission, label_version or story_key wrong"
    if not all(x in ids for x in ("topic", "places", "names", "names_id_space")): return "journal.ids incomplete"
    if ("SYNDICATED" in al.get("gaps", [])) != (k in ("copy", "republished")): return "SYNDICATED gap and journal.dup.kind disagree"
    if k in ("copy", "republished"):
        if not isinstance(o, int) or o >= s or o not in srcs: return "journal.dup.of_seq %r is not an earlier root" % o
        if (k == "copy") == (al["source"] in srcs[o]): return "journal.dup.kind %s but the source is %s among the story's sources" % (k, "already" if k == "copy" else "not")
        srcs[o].add(al["source"]); n = len(srcs[o])
    else:
        if o is not None: return "journal.dup.of_seq set on a %s" % k
        n = 1
        if k != "no_key": srcs[s] = {al["source"]}
    if j.get("publishers") != n: return "journal.publishers %r, recomputed %d" % (j.get("publishers"), n)
def check(folder):
    why = []; run = json.load(open(folder + "/run.json")); prev = run["run_id"]; n = 0; ids = []; srcs = {}
    if run.get("version", "live-trace-v1") not in ("live-trace-v1", "live-trace-v2", "live-trace-v2-nojournal", "live-trace-v3", "live-trace-v4"): why.append("run.json version %r is not live-trace-v1, v2, v2-nojournal, v3 or v4" % run.get("version"))
    need_j = run.get("version") in ("live-trace-v2", "live-trace-v3", "live-trace-v4") and "journal_version" in run   # journaled runs (step 3 on) need a journal on every traced line; step 2 runs are accepted without; any journal present is checked
    if run.get("state") == "error" and not os.path.exists(folder + "/chain.jsonl"): return why + ["run refused to start: " + str(run.get("why"))], 0, []
    if run.get("columns_allowlist") != ALLOW: why.append("run.json columns_allowlist differs from the allowlist")
    for i, l in enumerate(open(folder + "/chain.jsonl")):
        c = json.loads(l)
        if c["seq"] != i: why.append("seq gap at line %d (seq %s)" % (i, c["seq"])); break
        if c["prev"] != prev: why.append("prev link broken at seq %d" % i); break
        if hashlib.sha256((c["prev"] + c["line"]).encode()).hexdigest() != c["sha"]: why.append("sha mismatch at seq %d" % i); break
        prev = c["sha"]; a = json.load(open("%s/a/%d.json" % (folder, i))); al = json.loads(c["line"])
        if a["article_line"] != al: why.append("a/%d.json article_line differs from the chain line" % i); break
        if hashlib.sha1(a["text"].encode()).hexdigest() != al["input"]["text_sha1"]: why.append("text_sha1 mismatch at seq %d" % i); break
        if any(k in al for k in ("category", "region", "country", "story")): why.append("forbidden key in line %d" % i); break
        if al["state"] == "traced":
            ids.append(al["id"])
            if "journal" in al:
                e = jcheck(al, srcs)
                if e: why.append("line %d: %s" % (i, e)); break
            elif need_j: why.append("traced line %d has no journal" % i); break
        elif "journal" in al: why.append("skipped line %d carries a journal" % i); break
        n += 1
    return why, n, ids
def replay(ids):
    outs = []
    for _ in range(2):
        r = subprocess.run([PY, os.path.join(HERE, "live_trace.py"), "--replay-run", ",".join(ids)], capture_output=True, text=True, cwd=HERE, env={**os.environ, "THREADS": "4", "PYTHONHASHSEED": "0"})
        j = [x for x in r.stdout.splitlines() if x.startswith("REPLAY_JSON ")]
        if not j: return ["replay process failed: " + r.stderr[-300:]]
        outs.append(json.loads(j[0][12:]))
    diff = [i for i in ids if outs[0].get(i) != outs[1].get(i)]
    return ["replay differs for ids %s" % diff[:5]] if diff else []
if __name__ == "__main__":
    folder = sys.argv[1].rstrip("/"); why, n, ids = check(folder)
    print("chain: %d lines checked" % n)
    if "--replay" in sys.argv and not why:
        k = int(sys.argv[sys.argv.index("--replay") + 1]); pick = random.Random(0).sample(ids, min(k, len(ids))); rw = replay(pick); print("replay: %d articles x2" % len(pick), "PASS" if not rw else "FAIL"); why += rw
    print("PASS" if not why else "FAIL: " + "; ".join(why)); sys.exit(1 if why else 0)
