"""Open-model teacher on any OpenAI-compatible endpoint (vLLM, Ollama, LM Studio on a local RTX 3090/5090, RunPod).
Same task spec, validation and label/provenance format as claude_batch.py (shared helpers imported from it).
Learned from pipeline/kaggle/teacher/teacher_run.py (vLLM driver, find_loop) and the silver205 judge kernels.

    python open_model.py --spec SPEC --items items.jsonl --out RUN --base-url http://localhost:8000/v1 --model MODEL
        [--cands cands.jsonl] [--guided json_schema|vllm|json_object|none] [--workers 8]
        [--usd-per-hour 0.69 --cap-usd 5]      # rented GPU (RunPod): wall-clock $ cap, R5
        [--api-key-env RUNPOD_API_KEY]         # bearer token read from that env var; never printed
    python open_model.py ... --dry-run         # offline: build + validate request bodies, print counts

Guided decoding: json_schema = response_format {"type": "json_schema", "strict": true} (vLLM >= 0.6, LM Studio,
Ollama >= 0.5, OpenAI); vllm = extra body guided_json (older vLLM); json_object = JSON mode only; none = prompt only.
Every reply is validated in code whatever the mode. Loop guard: max_tokens = spec ceiling (max_new_tokens), optional
repetition_penalty (vLLM / LM Studio) and a repetition detector on the reply (a 20-400 char period repeated 3x at the
end, or >= 8 identical rows): a looped reply is rejected and retried once at temperature 0.2. Concurrency: --workers
requests in flight. Outputs as claude_batch.py: RUN/labels.jsonl, rejects.jsonl, spend.jsonl (tokens, wall s, $).
"""
import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import re
import sys
import threading
import time
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import task_spec as TS  # noqa: E402
import claude_batch as CB  # noqa: E402  (anthropic is imported lazily there; not needed here)

TOOL = "kit/teacher/open_model.py"
_ROW = re.compile(r"\}\s*,\s*\{|\n")


def find_loop(text, min_rep=8):
    """-> cut position when the reply ends in a repetition loop, else None (teacher_run.find_loop, simplified)."""
    if len(text) < 200:
        return None
    rows = [r.strip() for r in _ROW.split(text) if r.strip()]
    if len(rows) >= min_rep:
        norm = [re.sub(r"\d+", "#", r) for r in rows]
        k = 1
        while k < len(norm) and norm[-k - 1] == norm[-1]:
            k += 1
        if k >= min_rep and len(norm[-1]) > 8:
            return text.find(rows[-k]) + len(rows[-k])
    t = text[-1200:]
    for L in range(20, 401):
        if 3 * L <= len(t) and t[-L:] == t[-2 * L:-L] == t[-3 * L:-2 * L]:
            return len(text) - 2 * L
    return None


def body(spec, system, user, max_tokens, schema, model, guided, temperature=0.0, rep_penalty=None):
    b = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
         "max_tokens": max_tokens, "temperature": temperature}
    s = TS.api_schema(schema)
    if guided == "json_schema":
        b["response_format"] = {"type": "json_schema", "json_schema": {"name": "reply", "schema": s, "strict": True}}
    elif guided == "vllm":
        b["guided_json"] = s
    elif guided == "json_object":
        b["response_format"] = {"type": "json_object"}
    if rep_penalty:
        b["repetition_penalty"] = rep_penalty
    return b


def default_post(url, payload, headers, timeout):
    import requests  # lazy
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


class OpenRun:
    def __init__(self, spec, out, base_url, model, guided="json_schema", workers=4, cap_usd=None, usd_per_hour=0.0,
                 api_key=None, rep_penalty=None, timeout=600, post=default_post, log=print):
        self.spec, self.out, self.model, self.guided = spec, pathlib.Path(out), model, guided
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.host = urllib.parse.urlparse(base_url).netloc
        self.workers, self.rate = max(1, workers), float(usd_per_hour or 0.0)
        self.cap = float(cap_usd) if cap_usd is not None else (spec.cap_usd if self.rate else float("inf"))
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._key = api_key
        self.rep_penalty, self.timeout, self.post, self.log = rep_penalty, timeout, post, log
        self.lock = threading.Lock()
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.t0, self.prior = None, CB.spend_total(self.out / "spend.jsonl")
        self.stopped = None

    def usd_now(self):
        return self.prior + (time.time() - self.t0) / 3600 * self.rate if self.t0 else self.prior

    def call(self, r, temperature=0.0):
        b = body(self.spec, r["system"], r["user"], r["max_tokens"], r["schema"], self.model, self.guided,
                 temperature, self.rep_penalty)
        try:
            resp = self.post(self.url, b, self.headers, self.timeout)
        except Exception as e:  # noqa
            return None, f"api: {CB.scrub(e, self._key)[:300]}"
        u = resp.get("usage") or {}
        with self.lock:
            self.usage["input_tokens"] += u.get("prompt_tokens", 0) or 0
            self.usage["output_tokens"] += u.get("completion_tokens", 0) or 0
        return resp, None

    def check(self, r, resp):
        ch = (resp.get("choices") or [{}])[0]
        text = (ch.get("message") or {}).get("content") or ""
        if find_loop(text) is not None:
            return None, {}, ["loop: repetition at end of reply"]
        return CB.check_row(self.spec, r["item"], r["cands"], text, ch.get("finish_reason"))

    def one(self, r):
        if self.usd_now() >= self.cap:
            with self.lock:
                self.stopped = self.stopped or f"cap: ${self.usd_now():.4f} >= cap ${self.cap}"
            return False
        resp, err = self.call(r)
        errs = [err] if err else None
        mode = "sync"
        if resp is not None:
            label, stats, errs = self.check(r, resp)
            if errs and self.usd_now() < self.cap:  # one retry, slightly off greedy so a loop can break
                resp2, err2 = self.call(r, temperature=0.2)
                if resp2 is not None:
                    resp, mode = resp2, "sync_retry"
                    label, stats, errs = self.check(r, resp2)
                else:
                    errs = errs + [f"retry {err2}"]
        with self.lock:
            if errs:
                CB.append_jsonl(self.out / "rejects.jsonl", [{"item_id": str(r["item"]["id"]), "errors": errs,
                                                              "mode": mode, "request_id": (resp or {}).get("id"),
                                                              "date": CB.now()}])
                return False
            p = CB.provenance(self.spec, "open", resp.get("model") or self.model, r["item"], request_id=resp.get("id"),
                              endpoint=self.host, guided=self.guided, mode=mode,
                              stop_reason=(resp.get("choices") or [{}])[0].get("finish_reason"))
            CB.append_jsonl(self.out / "labels.jsonl", [{"item_id": str(r["item"]["id"]), "label": label,
                                                         "stats": stats, "provenance": p,
                                                         "usage": resp.get("usage") or {}}])
            return True

    def run(self, reqs):
        self.t0 = time.time()
        with cf.ThreadPoolExecutor(self.workers) as ex:
            ok = sum(ex.map(self.one, reqs))
        wall = time.time() - self.t0
        usd = wall / 3600 * self.rate
        CB.append_jsonl(self.out / "spend.jsonl", [{
            "ts": CB.now(), "run": self.out.name, "tool": TOOL, "mode": "open", "endpoint": self.host,
            "model": self.model, "prompt_version": self.spec.prompt_version, "n": len(reqs), "ok": ok,
            "usage": self.usage, "wall_s": round(wall, 1), "usd_per_hour": self.rate, "usd": round(usd, 6),
            "cap_usd": self.cap if self.cap != float("inf") else None, "running_total_usd": round(self.prior + usd, 6)}])
        return ok


def build(spec, items, C=None, skip=()):
    system, out = spec.system_text(), []
    if spec.mode == "verify" and C is None:
        raise SystemExit("verify-mode spec needs --cands (candidates.py output)")
    for it in items:
        if str(it["id"]) in skip:
            continue
        cands = CB.item_cands(it, C) if spec.mode == "verify" else None
        schema = spec.reply_schema(cands)
        if TS.closed(schema):
            raise SystemExit(f"reply schema for item {it['id']} has open objects")
        out.append({"item": it, "cands": cands, "system": system, "user": spec.user_text(it, cands),
                    "max_tokens": spec.max_tokens_for(cands), "schema": schema})
    return out


def main(argv=None, post=default_post):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cands")
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", required=True, help="served model name (recorded in provenance)")
    ap.add_argument("--guided", choices=["json_schema", "vllm", "json_object", "none"], default="json_schema")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rep-penalty", type=float)
    ap.add_argument("--usd-per-hour", type=float, default=0.0, help="rented GPU price; 0 = local")
    ap.add_argument("--cap-usd", type=float)
    ap.add_argument("--api-key-env", help="env var holding the endpoint bearer token")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    spec = TS.load(a.spec)
    items = CB.read_jsonl(a.items)
    items = items[: a.limit] if a.limit else items
    C = CB.load_cands(a.cands) if a.cands else None
    reqs = build(spec, items, C, skip=CB.done_ids(a.out))
    if a.dry_run:
        for r in reqs:
            json.dumps(body(spec, r["system"], r["user"], r["max_tokens"], r["schema"], a.model, a.guided))
        print(f"DRY RUN {spec.name} {spec.prompt_version} model={a.model} guided={a.guided}: {len(reqs)} requests, "
              f"max_tokens <= {spec.max_tokens}, prefix ~{spec.prefix_tokens_est()} tok")
        return 0
    key = os.environ.get(a.api_key_env) if a.api_key_env else None
    R = OpenRun(spec, a.out, a.base_url, a.model, a.guided, a.workers, a.cap_usd, a.usd_per_hour, key, a.rep_penalty,
                post=post)
    ok = R.run(reqs)
    print(f"{ok}/{len(reqs)} labels -> {pathlib.Path(a.out) / 'labels.jsonl'}" + (f"; STOPPED {R.stopped}" if R.stopped else ""))
    return 3 if R.stopped else 0


if __name__ == "__main__":
    sys.exit(main())
