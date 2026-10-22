"""Fast-mode Clef labelling (round 6): NVFP4 Clef-Flash on vLLM + the two-step screen v2 (ledger F-0047, threshold 0.20), engine question text from classify.py, 64 stories/min measured on the 5090.
  /workspace/models/cygnet-venv/bin/python newsreader/bitmob/clef_fast_label.py IN.jsonl OUT.jsonl [--n N] [--offset K] [--minutes M<=38] [--batch 64] [--job clef-fast] [--util 0.70]
Run only between `newsreader/bitmob/clef_fast_mode.sh pause` and `resume` (vLLM needs the GPU; :8018 llama-server and the live feed must be quiet).
Per story: step 1 = one call with the meta questions (g| s| x|) + 78 screen questions s2|dial|dir ('does the story report any of: <attributes>?'); step 2 = for every screen key >= 0.20, resend the full battery's own
20-question blocks (classify.QS order) that hold an attribute of a flagged key (grouping preserved). P = meta from step 1, then block answers overwrite; attribute questions in blocks never sent are 0.0 (exactly as clef_two_step.py).
Record: id, state_text, day, P (328 keys, same names as clef_label.py), read (classify.read(P)), screen (s2| answers), flagged keys, teacher='clef-nvfp4-two-step-v2', fast=true.
NO place / country / expected / severity in a fast record: the training builder must mask those heads. Resumable by id; STOP file checked before launch and every batch."""
import os, sys, json, time, argparse, datetime
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/data/models/clef-flash-nvfp4-alpha", "/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/newsreader/bitmob"]
import classify as C, torch, concurrent.futures as cf
from progress import event
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--n", type=int, default=10 ** 9); ap.add_argument("--offset", type=int, default=0); ap.add_argument("--minutes", type=float, default=36)
ap.add_argument("--batch", type=int, default=64); ap.add_argument("--job", default="clef-fast"); ap.add_argument("--util", type=float, default=0.70); ap.add_argument("--th", type=float, default=0.20); a = ap.parse_args()
assert a.minutes <= 38, "fast mode runs at most 38 min per cycle"
STOP = "/workspace/data/progress/STOP"
if os.path.exists(STOP): print("STOP file present: not launching"); sys.exit(0)
rows = [json.loads(l) for l in open(a.inp)][a.offset:a.offset + a.n]; done = set()
if os.path.exists(a.out): done = {json.loads(l)["id"] for l in open(a.out) if l.strip()}
todo = [r for r in rows if r["id"] not in done]; total = len(rows); t_end = time.time() + 60 * a.minutes
META = [k for k in C.QS if not k.startswith("a|")]; ATTRQ = [k for k in C.QS if k.startswith("a|")]; NAMES = list(C.QS)
def screen_q(d, dirn): return "Does the story report any of these: " + "; ".join(f"{x['attribute']} ({x['definition'].strip().rstrip('.')})" for x in C.ATTRS[(d, dirn)]) + "?"
SCREEN = {f"s2|{d}|{dirn}": screen_q(d, dirn) for (d, dirn) in C.ATTRS}
def day_of(r): return r.get("date") or r.get("day") or datetime.date.today().isoformat()
def state(r): d = day_of(r); return f"News item (published {d}; today is {d}):\n{r['title']}. {(r.get('description') or '')[:250]}"
req = lambda st, qs: {"state": st, "questions": {k: {"type": "noul", "instructions": q} for k, q in qs.items()}}
from clef_vllm import ClefVLLM
clef = ClefVLLM("/workspace/data/models/clef-flash-nvfp4-alpha", gpu_memory_utilization=a.util)
def run(reqs, chunk=34):      # pipelined as in clef_two_step.py
    out, futs = [], []
    def score(enc, outs): return [clef.decide(e, o.outputs.data.to(clef.device, torch.bfloat16)) for e, o in zip(enc, outs)]
    with cf.ThreadPoolExecutor(1) as ex:
        for i in range(0, len(reqs), chunk):
            part = reqs[i:i + chunk]; enc = [clef.encode(r) for r in part]
            futs.append(ex.submit(score, enc, clef.llm.encode([clef._prompt(r, e) for r, e in zip(part, enc)], pooling_task="token_embed", use_tqdm=False)))
            while len(futs) > 1: out += futs.pop(0).result()
        for f in futs: out += f.result()
    return [{k: v["true"] for k, v in p.items()} for p in out]
event(a.job, "running", f"start: {len(done)}/{total} done, {len(todo)} to label (fast mode)", pid=os.getpid())
run([req(state(todo[0]) if todo else "x", {k: C.QS[k] for k in ATTRQ[:20]})]) if todo else None      # warm-up
t0 = time.time(); n_new = 0
while todo and time.time() < t_end:
    if os.path.exists(STOP): print("STOP file: finishing"); break
    B, todo = todo[:a.batch], todo[a.batch:]; sts = [state(r) for r in B]
    s1 = run([req(st, {**{k: C.QS[k] for k in META}, **SCREEN}) for st in sts]); reqsB, idxB = [], []
    for i, st in enumerate(sts):
        qs = {q for k in SCREEN if s1[i][k] >= a.th for q in ATTRQ if q.startswith("a|" + k[3:] + "|")}
        for j in range(0, len(NAMES), 20):
            blk = NAMES[j:j + 20]
            if qs & set(blk): reqsB.append(req(st, {k: C.QS[k] for k in blk})); idxB.append(i)
    P = [{**{k: s1[i][k] for k in META}, **{k: 0.0 for k in ATTRQ}} for i in range(len(B))]
    for i, p in zip(idxB, run(reqsB)): P[i].update(p)
    with open(a.out, "a") as f:
        for i, r in enumerate(B):
            rd = C.read(P[i]); sc = {k: round(s1[i][k], 4) for k in SCREEN}
            f.write(json.dumps({"id": r["id"], "state_text": f"{r['title']}. {(r.get('description') or '')[:250]}", "day": day_of(r), "P": P[i], "read": rd, "screen": sc,
                                "flagged": [k[3:] for k in SCREEN if s1[i][k] >= a.th], "teacher": "clef-nvfp4-two-step-v2", "fast": True, "labelled_at": datetime.datetime.now().isoformat(timespec="seconds")}) + "\n")
    n_new += len(B); el = time.time() - t0; event(a.job, "running", f"{len(done) + n_new}/{total} labelled in total (this run +{n_new}), {n_new / el * 60:.0f} stories/min", pid=os.getpid())
el = time.time() - t0; msg = f"{len(done) + n_new}/{total} labelled in total, this run {n_new} in {el:.0f}s = {n_new / max(el, 1) * 60:.1f} stories/min"
event(a.job, "done", msg, pid=os.getpid(), win=True); print(json.dumps({"labelled_total": len(done) + n_new, "of": total, "this_run": n_new, "wall_s": round(el), "stories_per_min": round(n_new / max(el, 1) * 60, 1)}))
