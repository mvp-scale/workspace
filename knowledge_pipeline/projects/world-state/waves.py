#!/usr/bin/env python3
"""Wave loop: label a dev slice with two model families, measure agreement, let an improver refine the guideline, repeat.

    python waves.py dry               free: worst-case cost of one wave (both families), no API call
    python waves.py run  --budget 50  [--size 500] [--hours 8] [--predict "..."]   detached loop; prints PID
    python waves.py status            waves done, agreement per wave, spend
    python waves.py stop              stop by verified PID (also: touch runs/waves/STOP)

One wave = Haiku and Sonnet label the same dev slice (pool minus the frozen 300) -> agreement per layer ->
improver (Sonnet, Messages API) reads disagreements and APPENDS short guideline lines -> next wave, fresh slice.
Agreement between families is the signal; it is not truth. Frozen test (pilot300) is never labelled here (R3).
Spend is the client estimate in spend.jsonl; the Console bill is the truth. Key: secrets/vault.env, never printed.
"""
import argparse, json, os, pathlib, random, signal, subprocess, sys, threading, time, copy

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1] / "kit" / "teacher"
PY = str(HERE.parent / ".venv" / "bin" / "python")
KEYFILE = "/workspace/secrets/vault.env"
BASE = HERE / "specs" / "world_state_v1.json"
POOL, PILOT = HERE / "data" / "pool.jsonl", HERE / "data" / "pilot300.jsonl"
W = HERE / "runs" / "waves"
FAMILIES = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}
IMPROVER = "claude-sonnet-5-5"
MAX_ADD_LINES, MAX_GUIDE_GROWTH = 6, 60          # append-only, bounded drift
sys.path.insert(0, str(HERE.parents[1] / "kit" / "live"))
from heartbeat import beat, record, finish   # noqa: E402  (viewer Live runs card)
PRICE_S = {"input": 2.00, "output": 10.00}       # improver cost estimate, standard USD per Mtok


def jl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if pathlib.Path(path).exists() else []


_wave = {}


def log(**kw):
    W.mkdir(parents=True, exist_ok=True)
    kw.setdefault("where", "[CPU]+[API]")
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(W / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(kw) + "\n")
    ev = kw.get("ev"); hb = dict(where="[CPU]+[API]", task="T14", cap=50)
    if ev == "wave_start": _wave.update(t=kw["t"], spent=kw["spent"], n=kw["n"])
    if ev == "agreement": _wave["res"] = f"topic {kw['topic']}, story_type {kw['story_type']}, condition F1 {kw['cond_pair_f1']}"
    if ev == "wave_done": record(f"wave-{kw['n']}", "done", where="[CPU]+[API]", task="T14", started=_wave.get("t"), spent=round(kw["spent"] - _wave.get("spent", 0), 2), last=_wave.get("res", "") + f"; improver added {len(kw['added'])} lines")
    if ev == "stop": finish("wave-loop", "stopped", last=f"stopped: {kw.get('why')}", **hb)
    if ev == "wave_start": beat("wave-loop", state="running", progress=f"wave {kw['n']}", spent=kw["spent"], last=f"wave {kw['n']} labelling {kw['items']} items", **hb)
    elif ev == "agreement": beat("wave-loop", last=f"W{kw['n']} topic {kw['topic']}, condition F1 {kw['cond_pair_f1']}", **hb)
    elif ev == "wave_done": beat("wave-loop", spent=kw["spent"], last=f"W{kw['n']} done; improver added {len(kw['added'])} lines", **hb)
    print(json.dumps(kw), flush=True)


def spent_dir(d):
    return sum(r.get("usd", 0) for r in jl(pathlib.Path(d) / "spend.jsonl"))


def total_spend():
    return sum(r.get("usd", 0) for r in jl(W / "spend.jsonl")) + sum(spent_dir(p) for p in W.glob("w*/*"))


def dev_slice(n, size):
    skip = {r["id"] for r in jl(PILOT)}
    pool = [r for r in jl(POOL) if r["id"] not in skip]
    random.Random(20261030).shuffle(pool)
    return pool[(n - 1) * size: n * size]


def write_spec(n, fam, guide):
    s = copy.deepcopy(json.load(open(BASE)))
    s["model"], s["guideline"] = FAMILIES[fam], guide
    s["prompt_version"] = f"ws-w{n}"
    s["name"] = f"world_state_wave{n}_{fam}"
    p = HERE / "specs" / "waves" / f"w{n}_{fam}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=1))
    return p


def label(spec, items, out, cap, dry=False):
    cmd = [PY, KIT / "claude_batch.py", "--spec", spec, "--items", items, "--out", out, "--key-file", KEYFILE, "--cap-usd", f"{cap:.2f}"]
    if dry: cmd.append("--dry-run")
    return subprocess.run([str(c) for c in cmd]).returncode


def lab(row):
    x = row.get("label", row)
    return x if isinstance(x, dict) else {}


def pairs(x, with_dir=True):
    return {(c.get("condition"), c.get("direction")) if with_dir else c.get("condition") for c in x.get("conditions", [])}


def f1(a, b):                                     # a, b: dict item -> set
    tp = sum(len(a[i] & b[i]) for i in a if i in b)
    p = sum(len(a[i]) for i in a if i in b); r = sum(len(b[i]) for i in a if i in b)
    return round(2 * tp / (p + r), 3) if p + r else None


def agreement(h_rows, s_rows):
    H, S = {r["item_id"]: lab(r) for r in h_rows}, {r["item_id"]: lab(r) for r in s_rows}
    ids = sorted(set(H) & set(S))
    m = lambda k: round(sum(H[i].get(k) == S[i].get(k) for i in ids) / len(ids), 3) if ids else None
    out = {"paired": len(ids), "topic": m("topic"), "story_type": m("story_type"),
           "cond_pair_f1": f1({i: pairs(H[i]) for i in ids}, {i: pairs(S[i]) for i in ids}),
           "cond_id_f1": f1({i: pairs(H[i], False) for i in ids}, {i: pairs(S[i], False) for i in ids})}
    out["none_haiku"] = round(sum(not H[i].get("conditions") for i in ids) / len(ids), 3) if ids else None    # guard: agreement must not come from both saying "none"
    out["none_sonnet"] = round(sum(not S[i].get("conditions") for i in ids) / len(ids), 3) if ids else None
    dis = [i for i in ids if H[i].get("topic") != S[i].get("topic") or pairs(H[i]) != pairs(S[i])]
    return out, dis, H, S


def secret(name):
    for l in open(KEYFILE):
        if l.startswith(name + "="): return l.split("=", 1)[1].strip().strip("'\"")


def improve(n, guide, dis, H, S, items, bad=()):
    import anthropic
    random.Random(n).shuffle(dis)
    cases = "\n\n".join(f"TEXT: {items[i]['text']}\nA (small model): {json.dumps({k: H[i].get(k) for k in ('topic','story_type','conditions')})}\n"
                        f"B (larger model): {json.dumps({k: S[i].get(k) for k in ('topic','story_type','conditions')})}" for i in dis[:40] if i in items)
    prompt = ("Two models label short news items with the guideline below and disagree on the cases shown. Find the most common "
              "ambiguity behind the disagreements and write at most %d NEW guideline lines (one sentence each, plain, no examples "
              "from the cases, no new labels, and NONE that make the reader tag fewer conditions or leave conditions empty more often: the readers are already too quiet; prefer lines that settle topic boundaries and the wording of direction and size) that would make a careful reader choose the same answer. Do not restate existing lines. "
              "Reply JSON only: {\"diagnosis\": str, \"lines\": [str]}.%s\n\nGUIDELINE:\n%s\n\nDISAGREEMENTS:\n%s") % (MAX_ADD_LINES, ("\n\nLINES ALREADY TRIED THAT MADE AGREEMENT WORSE (do not repeat or paraphrase; they were removed):\n" + "\n".join(bad[-12:])) if bad else "", "\n".join(guide), cases)
    c = anthropic.Anthropic(api_key=secret("ANTHROPIC_API_KEY"))
    r = c.messages.create(model=IMPROVER, max_tokens=1200, messages=[{"role": "user", "content": prompt}])
    usd = (r.usage.input_tokens * PRICE_S["input"] + r.usage.output_tokens * PRICE_S["output"]) / 1e6
    with open(W / "spend.jsonl", "a") as f: f.write(json.dumps({"what": f"improver w{n}", "usd": usd}) + "\n")
    txt = r.content[0].text.strip()
    txt = txt[txt.find("{"): txt.rfind("}") + 1]
    d = json.loads(txt)
    return d.get("diagnosis", ""), [l.strip() for l in d.get("lines", []) if isinstance(l, str) and l.strip()][:MAX_ADD_LINES]


def loop(budget, size, hours, margin=2.0):
    W.mkdir(parents=True, exist_ok=True)
    (W / "pid").write_text(str(os.getpid()))
    def pulse():
        while True:
            time.sleep(60); beat("wave-loop")
    threading.Thread(target=pulse, daemon=True).start()
    t0 = time.time()
    base = json.load(open(BASE))["guideline"]
    guide = json.loads((W / "guideline.json").read_text()) if (W / "guideline.json").exists() else base
    done = [r for r in jl(W / "log.jsonl") if r.get("ev") == "wave_done"]
    n = len(done) + 1
    lst = json.loads((W / "loop_state.json").read_text()) if (W / "loop_state.json").exists() else {"prev": None, "before": None, "added": [], "bad": []}
    while True:
        why = ("STOP file" if (W / "STOP").exists() else "wall clock" if time.time() - t0 > hours * 3600
               else "budget" if total_spend() > budget - margin else "pool exhausted" if not dev_slice(n, size) else None)
        if why: log(ev="stop", why=why, spent=round(total_spend(), 2), waves=n - 1); break
        items = dev_slice(n, size); ip = W / f"w{n}_items.jsonl"
        ip.write_text("".join(json.dumps(r) + "\n" for r in items))
        left = budget - margin - total_spend()
        log(ev="wave_start", n=n, items=len(items), guide_lines=len(guide), spent=round(total_spend(), 2))
        ts = [threading.Thread(target=label, args=(write_spec(n, fam, guide), ip, W / f"w{n}" / fam), kwargs={"cap": min(left / 2, 25.0)}) for fam in FAMILIES]
        [t.start() for t in ts]; [t.join() for t in ts]          # both families label the same slice at the same time
        h, s = jl(W / f"w{n}" / "haiku" / "labels.jsonl"), jl(W / f"w{n}" / "sonnet" / "labels.jsonl")
        if min(len(h), len(s)) < len(items) * 0.9:                          # a trimmed or partial batch: label the missing items once more before judging
            log(ev="relabel_missing", n=n, haiku=len(h), sonnet=len(s))
            ts = [threading.Thread(target=label, args=(write_spec(n, fam, guide), ip, W / f"w{n}" / fam), kwargs={"cap": min(left, 40.0)}) for fam in FAMILIES]
            [t.start() for t in ts]; [t.join() for t in ts]
            h, s = jl(W / f"w{n}" / "haiku" / "labels.jsonl"), jl(W / f"w{n}" / "sonnet" / "labels.jsonl")
        rej = max(len(jl(W / f"w{n}" / f / "rejects.jsonl")) for f in FAMILIES) / max(len(items), 1)
        ag, dis, H, S = agreement(h, s)
        log(ev="agreement", n=n, rejects=round(rej, 3), **ag)
        if rej > 0.05 or ag["paired"] < len(items) * 0.9:
            log(ev="stop", why="reject rate or missing labels", n=n); break
        if lst["prev"] and lst["added"] and ag["topic"] is not None:       # learn from the last change: did it hurt?
            drop = max((lst["prev"]["cond"] or 0) - (ag["cond_pair_f1"] or 0), (lst["prev"]["topic"] or 0) - ag["topic"])
            quiet = max((ag["none_haiku"] or 0) - (lst["prev"].get("nh") or 0), (ag["none_sonnet"] or 0) - (lst["prev"].get("ns") or 0))   # agreement through silence
            if drop > 0.05 or quiet > 0.02:
                log(ev="rollback", n=n, drop=round(drop, 3), quieter=round(quiet, 3), removed=len(lst["added"]), lines=lst["added"])
                guide = lst["before"]; lst["bad"] += lst["added"]; lst["added"] = []
        lst["prev"] = {"topic": ag["topic"], "cond": ag["cond_pair_f1"], "nh": ag["none_haiku"], "ns": ag["none_sonnet"]}; lst["before"] = list(guide)
        try:
            diag, lines = improve(n, guide, dis, H, S, {r["id"]: r for r in items}, lst["bad"])
        except Exception as e:
            diag, lines = f"improver failed: {type(e).__name__}", []
        if len(guide) - len(base) + len(lines) <= MAX_GUIDE_GROWTH: guide = guide + lines
        lst["added"] = [l for l in lines if l in guide]
        (W / "guideline.json").write_text(json.dumps(guide, indent=1)); (W / "loop_state.json").write_text(json.dumps(lst))
        log(ev="wave_done", n=n, diagnosis=diag[:600], added=lines, spent=round(total_spend(), 2))
        n += 1


def status():
    for r in jl(W / "log.jsonl"):
        if r["ev"] in ("agreement", "stop"): print({k: v for k, v in r.items() if k != "diagnosis"})
    print("spent (client estimate): $%.2f" % total_spend() if W.exists() else "no waves yet")


def stop():
    p = W / "pid"
    if not p.exists(): return print("no pid file")
    pid = int(p.read_text()); cmd = pathlib.Path(f"/proc/{pid}/cmdline")
    if cmd.exists() and b"waves.py" in cmd.read_bytes():
        os.kill(pid, signal.SIGTERM); print("stopped", pid)
    else: print("pid", pid, "is not a waves.py process; nothing killed")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--budget", type=float, default=50)
    ap.add_argument("--size", type=int, default=500); ap.add_argument("--hours", type=float, default=8); ap.add_argument("--predict", default="")
    ap.add_argument("--foreground", action="store_true"); a = ap.parse_args()
    if a.cmd == "dry":
        ip = W / "dry_items.jsonl"; W.mkdir(parents=True, exist_ok=True)
        ip.write_text("".join(json.dumps(r) + "\n" for r in dev_slice(1, a.size)))
        for fam in FAMILIES:
            print("==", fam); label(write_spec(0, fam, json.load(open(BASE))["guideline"]), ip, W / "dry" / fam, 50, dry=True)
    elif a.cmd == "run":
        if a.foreground:
            log(ev="run_start", budget=a.budget, size=a.size, hours=a.hours, predict=a.predict); loop(a.budget, a.size, a.hours)
        else:
            W.mkdir(parents=True, exist_ok=True)
            pr = subprocess.Popen([sys.executable, __file__, "run", "--foreground", "--budget", str(a.budget), "--size", str(a.size),
                                   "--hours", str(a.hours), "--predict", a.predict], stdout=open(W / "out.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
            print("started PID", pr.pid, "- log runs/waves/out.log; stop: python waves.py stop")
    elif a.cmd == "status": status()
    elif a.cmd == "stop": stop()


if __name__ == "__main__":
    main()
