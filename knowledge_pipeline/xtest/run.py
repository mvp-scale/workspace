"""xtest runner (M1/M2): run one rater over a bundle's tasks through an UNCHANGED jevbench adapter, write per-task results and a run card. No retries beyond the adapter's own, no repair of bad answers, failures stay failures (never scored as wrong, never dropped silently: counted in the card).
    python3 run.py --bundle runs/xtest/B1 --variant A --rater raters/jev.json --fields presence story topic --order-seed 0 [--workers 6] [--cap-usd 0.5] [--limit N]
Rater file: {"id","adapter":"typesafe|openai_compat","endpoint","model","key_env","request_options":{},"price_in_per_m","price_out_per_m"}."""
import argparse, concurrent.futures as cf, hashlib, json, os, random, sys, threading, time
sys.path.insert(0, "/workspace/jevbench"); sys.path.insert(0, "/workspace/knowledge_pipeline/kit/live")
import heartbeat as hb
from jevbench.tasks import Task, load_jsonl
from jevbench.adapters.typesafe import TypeSafeAdapter
from jevbench.adapters.openai_compat import OpenAICompatAdapter
def make(r):
    kw = dict(endpoint=r.get("endpoint"), model=r.get("model"), key_env=r.get("key_env", ""), timeout_s=r.get("timeout_s", 180.0), price_input_per_m=r.get("price_in_per_m"), price_output_per_m=r.get("price_out_per_m"))
    if r["adapter"] == "typesafe": a = TypeSafeAdapter(**kw)
    elif r["adapter"] == "openai_compat": a = OpenAICompatAdapter(**kw)
    else: raise SystemExit("unknown adapter " + r["adapter"])
    if r.get("request_options"): a.request_options = r["request_options"]
    return a
def label_of(task, probs):
    if not probs: return None
    return ("yes" if probs.get("yes", 0) >= 0.5 else "no") if task.question["type"] == "noul" else max(probs, key=probs.get)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bundle", required=True); ap.add_argument("--variant", default="A"); ap.add_argument("--rater", required=True); ap.add_argument("--fields", nargs="+", default=["presence"])
    ap.add_argument("--order-seed", type=int, default=0); ap.add_argument("--workers", type=int, default=6); ap.add_argument("--cap-usd", type=float, default=0.5); ap.add_argument("--limit", type=int); ap.add_argument("--tag", default=""); a = ap.parse_args()
    R = json.load(open(a.rater)); bundle = json.load(open(f"{a.bundle}/bundle.json")); tasks = [t for t in load_jsonl(f"{a.bundle}/tasks_{a.variant}.jsonl") if t.family in a.fields]
    random.Random(a.order_seed).shuffle(tasks); tasks = tasks[:a.limit] if a.limit else tasks
    if (R.get('price_in_per_m') or 0) > 0:
        sys.path.insert(0, '/workspace/knowledge_pipeline/xtest'); import budget as _b; _ok, _s, _c = _b.check(a.cap_usd)
        if not _ok: sys.exit(f"BUDGET REFUSED: hosted spend {_s:.3f} + this run's cap {a.cap_usd} passes the cumulative cap {_c} (xtest/budget_cap.json, raised only by the owner)")
    ad = make(R); name = f"{R['id']}_{a.variant}_s{a.order_seed}{a.tag}"; od = f"{a.bundle}/runs/{name}"; os.makedirs(od, exist_ok=True)
    job = f"xtest-{os.path.basename(a.bundle.rstrip('/'))}-{name}"; done_n = [0]
    hb.beat(job, pid=os.getpid(), where="[HOST]" if str(R.get("endpoint", "")).startswith("https") else "[5090] local model server", task="T21", state="running", progress=f"0 of {len(tasks)}", cap=a.cap_usd, why=f"Cross-family test: rater {R['id']} answers the common-structure questions ({', '.join(a.fields)}), variant {a.variant}, order seed {a.order_seed}", success="At least 95% of calls answered; results and run card written", next="score.py lints and scores the panel", need="Nothing")
    spent = [0.0]; lock = threading.Lock(); stop = [False]
    pin, pout = R.get("price_in_per_m"), R.get("price_out_per_m")
    def one(t):
        if stop[0]: return {"task": t.id, "field": t.family, "item": t.provenance["item"], "ok": False, "error": "not_attempted"}
        res = ad.run(t); u = res.usage or {}
        cost = ((u.get("input_tokens") or u.get("prompt_tokens") or 0) * (pin or 0) + (u.get("output_tokens") or u.get("completion_tokens") or 0) * (pout or 0)) / 1e6
        with lock:
            spent[0] += cost; done_n[0] += 1
            if done_n[0] % 200 == 0: hb.beat(job, progress=f"{done_n[0]} of {len(tasks)}", spent=round(spent[0], 4))
            if spent[0] > a.cap_usd: stop[0] = True
        return {"task": t.id, "field": t.family, "item": t.provenance["item"], "ok": bool(res.ok), "probs": res.probs, "label": label_of(t, res.probs) if res.ok else None, "probs_source": res.probs_source, "error": res.error, "latency_s": round(res.latency_s, 3), "usage": u, "model_resolved": res.model}
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.workers) as ex: out = list(ex.map(one, tasks))
    with open(f"{od}/results.jsonl", "w") as f:
        for r in out: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    card = {"rater": R["id"], "adapter": R["adapter"], "endpoint": R.get("endpoint"), "model_requested": R.get("model"), "models_resolved": sorted({r.get("model_resolved") for r in out if r.get("model_resolved")}), "request_options": R.get("request_options", {}), "bundle": bundle["id"], "variant": a.variant, "fields": a.fields, "order_seed": a.order_seed,
            "tasks_file_dataset_hash": bundle["dataset_hash"][a.variant], "instruction_sha256": {f: bundle["instruction_sha256"][a.variant][f] for f in a.fields}, "guideline_sha256": bundle["guideline_sha256"], "decoding_declared": R.get("decoding_declared", "unspecified"), "n_tasks": len(tasks), "n_ok": sum(r["ok"] for r in out), "n_failed": sum((not r["ok"]) and r.get("error") != "not_attempted" for r in out), "n_not_attempted": sum(r.get("error") == "not_attempted" for r in out),
            "spend_usd_estimate": round(spent[0], 5), "cap_usd": a.cap_usd, "seconds": round(time.time() - t0, 1), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0))}
    json.dump(card, open(f"{od}/run_card.json", "w"), indent=1)
    bad = (card["n_failed"] + card["n_not_attempted"]) / max(card["n_tasks"], 1); hb.finish(job, "done" if bad <= 0.05 else "failed", spent=card["spend_usd_estimate"], last=f"{card['n_ok']} of {card['n_tasks']} answered, {card['n_failed']} failed, {card['n_not_attempted']} not attempted, {card['seconds']} s; {od}/run_card.json"); print(name, {k: card[k] for k in ("n_tasks", "n_ok", "n_failed", "n_not_attempted", "spend_usd_estimate", "seconds")})
main()
