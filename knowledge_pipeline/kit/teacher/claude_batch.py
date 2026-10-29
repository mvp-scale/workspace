"""Claude teacher over the Message Batches API (stage S3; D6 provenance, R5 cap). Learned from
pipeline/teacher_api/teacher_batch.py (T50) and teacher/teacher_label.py.

    python claude_batch.py --spec SPEC --items items.jsonl --out RUN [--cands cands.jsonl] --dry-run
    python claude_batch.py --spec SPEC --items items.jsonl --out RUN [--cands cands.jsonl] [--key-file secrets/vault.env]
    python claude_batch.py ... --sync          # synchronous Messages calls (pilot / qualify on <= 50 items)

One command does the whole run and BLOCKS until it ends (agents call it once; they never poll): build requests ->
check the $ cap -> submit a batch chunk -> poll with backoff -> fetch -> validate every row -> retry malformed rows once
synchronously -> write labels -> one spend.jsonl line per batch -> next chunk. Re-running resumes: items already in
labels.jsonl are skipped and batches submitted but not fetched (state.json) are polled, never resubmitted.

Requests: system = guideline + layers + few-shot examples (task_spec.system_text) in ONE text block with
cache_control {"type": "ephemeral", "ttl": "1h"} (batches can outlast 5 min); user = item text (+ candidate list in
verify mode); output_config.format = json_schema of the reply (closed objects). Every reply is still validated in code
(refusals and max_tokens truncation break the schema). The prefix only caches at >= 512 tokens on 5.x models: the run
warns when a batch reports cache_read_input_tokens == 0.
Cap: before each chunk, spent (spend.jsonl) + worst case of the chunk (every request writes the cache, every reply
uses max_tokens) must stay <= --cap-usd (default spec cap_usd); the chunk is trimmed to fit, and the run stops when
nothing fits. Retries are checked the same way at non-batch prices. Prices: prices.json (status TO_BE_VERIFIED).
Key: env ANTHROPIC_API_KEY, else --key-file (a bare key or KEY=VALUE lines). Never printed, logged or written.
Outputs in RUN/: labels.jsonl (item_id, label, stats, provenance, usage), rejects.jsonl, spend.jsonl, state.json.
No item text is written to outputs (text_sha256 only); RUN stays private anyway (labels quote spans).
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import task_spec as TS  # noqa: E402

PRICES = HERE / "prices.json"
CID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_BATCH_REQ = 100_000
MAX_BATCH_BYTES = 200 * 2 ** 20  # API limit 256 MB; keep headroom
EXPECTED_OUT_FRAC = 0.4          # expected reply length as a share of max_tokens (estimate only; the cap uses 1.0)
TOOL = "kit/teacher/claude_batch.py"


# ----------------------------------------------------------------------------- shared helpers (open_model uses them)
def now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def g(o, k, default=None):
    """Attribute or key access (SDK objects and plain dicts)."""
    if o is None:
        return default
    if isinstance(o, dict):
        return o.get(k, default)
    return getattr(o, k, default)


def read_jsonl(path):
    if not path or not pathlib.Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def append_jsonl(path, rows):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def load_cands(path):
    """cands.jsonl (candidates.py) -> {item id: (text_sha256, candidates)}."""
    return {str(r["id"]): (r.get("text_sha256"), r["candidates"]) for r in read_jsonl(path)}


def done_ids(out):
    return {r["item_id"] for r in read_jsonl(pathlib.Path(out) / "labels.jsonl")}


def spend_total(path):
    return round(sum(r.get("usd", 0.0) for r in read_jsonl(path)), 6)


def parse_reply(text):
    """Model text -> (obj, error). Tolerates a markdown fence around the JSON."""
    t = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if m:
        t = m.group(1)
    try:
        return json.loads(t), None
    except Exception as e:  # noqa
        return None, f"json: {str(e)[:120]}"


def check_row(spec, item, cands, text, stop):
    """-> (label, stats, errors). Validates the reply schema, then the final label against output_schema."""
    if stop in ("max_tokens", "length"):
        return None, {}, [f"truncated (stop {stop})"]
    if stop == "refusal":
        return None, {}, ["refusal"]
    obj, err = parse_reply(text)
    if err:
        return None, {}, [err]
    errs = TS.validate(obj, spec.reply_schema(cands))
    if errs:
        return None, {}, errs[:5]
    label, stats, errs = spec.finalize(item, obj, cands)
    return (label, stats, errs[:5]) if not errs else (None, stats, errs[:5])


def provenance(spec, teacher, model, item, **kw):
    """D6: teacher, model, prompt version, spec sha, date, request ids; text by sha only."""
    return {"teacher": teacher, "model": model, "prompt_version": spec.prompt_version, "spec_name": spec.name,
            "spec_sha256": spec.sha256, "date": now(), "text_sha256": sha(item["text"]), **kw}


def item_cands(item, C):
    """Candidates for an item from cands.jsonl; refuses a text mismatch (candidates built on other text)."""
    if C is None:
        return None
    h, cands = C.get(str(item["id"]), (None, None))
    if cands is None:
        raise SystemExit(f"no candidates for item {item['id']} (run candidates.py first)")
    if h and h != sha(item["text"]):
        raise SystemExit(f"candidates for item {item['id']} were built on a different text")
    return cands


# ----------------------------------------------------------------------------- key + client
_KEYS = set()  # every key read this process; scrub() redacts all of them (MM3-0022: key-file keys too)


def read_key(key_file=None):
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        _KEYS.add(k.strip())
        return k.strip()
    if key_file:
        raw = pathlib.Path(key_file).read_text(encoding="utf-8")
        for line in raw.splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
                _KEYS.add(k)
                return k
        if "=" not in raw and raw.strip():
            _KEYS.add(raw.strip())
            return raw.strip()
    raise SystemExit("no API key: set ANTHROPIC_API_KEY or pass --key-file (the key is never printed)")


def scrub(msg, key=None):
    s = str(msg)
    for k in (key, os.environ.get("ANTHROPIC_API_KEY"), *_KEYS):
        if k:
            s = s.replace(k, "<redacted>")
    return re.sub(r"sk-ant-[A-Za-z0-9_-]+", "<redacted>", s)


def make_client(key):
    import anthropic  # lazy: --dry-run and tests never import it
    return anthropic.Anthropic(api_key=key, max_retries=4)


# ----------------------------------------------------------------------------- prices
def load_prices(path=PRICES):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def rate(prices, model, batch=True):
    m = prices["models"].get(model)
    if not m:
        raise SystemExit(f"no price row for {model} in prices.json; refusing (add it, marked to be verified)")
    f = prices.get("batch_discount", 0.5) if batch else 1.0
    m = {**m, "cache_write_1h": m.get("cache_write_1h", 2 * m["input"])}
    return {k: m[k] * f / 1e6 for k in ("input", "cache_read", "cache_write_5m", "cache_write_1h", "output")}


def usage_dict(u):
    d = {k: g(u, k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                                   "output_tokens")}
    cc = g(u, "cache_creation")
    if cc is not None:
        d["cache_write_5m"] = g(cc, "ephemeral_5m_input_tokens") or 0
        d["cache_write_1h"] = g(cc, "ephemeral_1h_input_tokens") or 0
    return d


def usage_usd(prices, model, u, batch=True):
    r = rate(prices, model, batch)
    w5 = u.get("cache_write_5m")
    w1 = u.get("cache_write_1h", u["cache_creation_input_tokens"] if w5 is None else 0)
    return (u["input_tokens"] * r["input"] + u["cache_read_input_tokens"] * r["cache_read"]
            + (w5 or 0) * r["cache_write_5m"] + w1 * r["cache_write_1h"] + u["output_tokens"] * r["output"])


def estimate(req, prices, model, batch=True):
    """(worst, expected) USD of one request from character counts (no count_tokens call)."""
    r = rate(prices, model, batch)
    p_lo, u_lo = req["prefix_chars"] / TS.CHARS_PER_TOKEN_LO, req["user_chars"] / TS.CHARS_PER_TOKEN_LO
    p, u = req["prefix_chars"] / TS.CHARS_PER_TOKEN, req["user_chars"] / TS.CHARS_PER_TOKEN
    worst = p_lo * r["cache_write_1h"] + u_lo * r["input"] + req["max_tokens"] * r["output"]
    exp = p * r["cache_read"] + u * r["input"] + EXPECTED_OUT_FRAC * req["max_tokens"] * r["output"]
    return worst, exp


# ----------------------------------------------------------------------------- requests
def custom_id(item_id, used):
    s = str(item_id)
    cid = s if CID_RE.match(s) else "h" + sha(s)[:20]
    if cid in used:
        cid = "h" + sha(s + "#" + str(len(used)))[:20]
    used.add(cid)
    return cid


def params(spec, system, user, max_tokens, schema):
    oc = {"format": {"type": "json_schema", "schema": TS.api_schema(schema)}}
    if spec.effort:
        oc["effort"] = spec.effort
    p = {"model": spec.model, "max_tokens": max_tokens,
         "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
         "messages": [{"role": "user", "content": user}], "output_config": oc}
    if spec.thinking:
        p["thinking"] = spec.thinking
    return p


def build_requests(spec, items, C=None, skip=()):
    """-> list of {cid, item, cands, params, prefix_chars, user_chars, max_tokens, bytes}. Validates offline."""
    system, used, out = spec.system_text(), set(), []
    if spec.mode == "verify" and C is None:
        raise SystemExit("verify-mode spec needs --cands (candidates.py output)")
    for it in items:
        if str(it["id"]) in skip:
            continue
        cands = item_cands(it, C) if spec.mode == "verify" else None
        user = spec.user_text(it, cands)
        mt = spec.max_tokens_for(cands)
        schema = spec.reply_schema(cands)
        bad = TS.closed(schema)
        if bad:
            raise SystemExit(f"reply schema for item {it['id']} has open objects {bad}")
        p = params(spec, system, user, mt, schema)
        b = len(json.dumps(p, ensure_ascii=False).encode("utf-8"))
        out.append({"cid": custom_id(it["id"], used), "item": it, "cands": cands, "params": p,
                    "prefix_chars": len(system), "user_chars": len(user), "max_tokens": mt, "bytes": b})
    return out


def chunks(reqs, size):
    cur, nb = [], 0
    for r in reqs:
        if cur and (len(cur) >= size or nb + r["bytes"] > MAX_BATCH_BYTES):
            yield cur
            cur, nb = [], 0
        cur.append(r)
        nb += r["bytes"]
    if cur:
        yield cur


def fit_cap(reqs, prices, model, room, batch=True):
    """Longest prefix of reqs whose summed worst case fits in room USD."""
    tot, n = 0.0, 0
    for r in reqs:
        w = estimate(r, prices, model, batch)[0]
        if tot + w > room:
            break
        tot, n = tot + w, n + 1
    return n, tot


# ----------------------------------------------------------------------------- run
def text_of(msg):
    return "".join(g(b, "text", "") or "" for b in (g(msg, "content") or []) if g(b, "type") == "text")


class Run:
    def __init__(self, spec, out, client=None, prices=None, cap_usd=None, run_name=None, log=print, sleep=time.sleep):
        self.spec, self.out, self.client = spec, pathlib.Path(out), client
        self.prices = prices or load_prices()
        self.cap = spec.cap_usd if cap_usd is None else float(cap_usd)
        self.name = run_name or self.out.name
        self.log, self.sleep = log, sleep
        self.spend = self.out / "spend.jsonl"
        self.state_p = self.out / "state.json"
        self.state = json.loads(self.state_p.read_text(encoding="utf-8")) if self.state_p.exists() else {"batches": {}}
        self.stopped = None

    def spent(self):
        return spend_total(self.spend)

    def save(self):
        write_json(self.state_p, self.state)

    def log_spend(self, mode, batch_id, model, n, counts, usage, usd):
        tot = round(self.spent() + usd, 6)
        row = {"ts": now(), "run": self.name, "tool": TOOL, "mode": mode, "batch_id": batch_id, "model": model,
               "prompt_version": self.spec.prompt_version, "n": n, "results": counts, "usage": usage,
               "usd": round(usd, 6), "prices_status": self.prices.get("status", "?"), "cap_usd": self.cap,
               "running_total_usd": tot}
        append_jsonl(self.spend, [row])
        if n > 1 and usage.get("cache_read_input_tokens", 0) == 0:
            self.log(f"WARN {batch_id}: cache_read_input_tokens == 0 (prefix < 512 tokens or cache not hit)")
        return row

    def emit(self, r, label, stats, msg, mode, batch_id=None):
        p = provenance(self.spec, "claude", g(msg, "model") or self.spec.model, r["item"], request_id=g(msg, "id"),
                       custom_id=r["cid"], batch_id=batch_id, mode=mode, stop_reason=g(msg, "stop_reason"))
        append_jsonl(self.out / "labels.jsonl", [{"item_id": str(r["item"]["id"]), "label": label, "stats": stats,
                                                  "provenance": p, "usage": usage_dict(g(msg, "usage"))}])

    def reject(self, r, errs, mode, batch_id=None, msg=None):
        append_jsonl(self.out / "rejects.jsonl", [{"item_id": str(r["item"]["id"]), "custom_id": r["cid"],
                                                   "errors": [scrub(e) for e in errs], "mode": mode,
                                                   "batch_id": batch_id, "request_id": g(msg, "id"), "date": now()}])

    # --- one synchronous call, cap-checked
    def call_sync(self, r, mode):
        """-> (message, error). Refuses (and sets .stopped) when the worst case would pass the cap."""
        w = estimate(r, self.prices, self.spec.model, batch=False)[0]
        if self.spent() + w > self.cap:
            self.stopped = f"cap: spent ${self.spent():.4f} + worst ${w:.4f} > cap ${self.cap}"
            return None, "not sent: cap"
        try:
            msg = self.client.messages.create(**r["params"])
        except Exception as e:  # noqa
            return None, f"api: {scrub(e)[:300]}"
        u = usage_dict(g(msg, "usage"))
        self.log_spend(mode, None, self.spec.model, 1, {"succeeded": 1}, u,
                       usage_usd(self.prices, self.spec.model, u, batch=False))
        return msg, None

    def finish(self, r, msg, mode, batch_id=None, retry=True):
        """Validate one reply; malformed -> one synchronous retry (retry=True)."""
        label, stats, errs = check_row(self.spec, r["item"], r["cands"], text_of(msg), g(msg, "stop_reason"))
        if not errs:
            self.emit(r, label, stats, msg, mode, batch_id)
            return True
        if retry:
            m2, err = self.call_sync(r, "sync_retry")
            if m2 is not None:
                return self.finish(r, m2, "sync_retry", batch_id, retry=False)
            errs = errs + [f"retry {err}"]
        self.reject(r, errs, mode, batch_id, msg)
        return False

    def run_sync(self, reqs):
        ok = 0
        for r in reqs:
            if self.stopped:
                break
            msg, err = self.call_sync(r, "sync")
            if msg is not None:
                ok += self.finish(r, msg, "sync")
            elif not self.stopped:
                self.reject(r, [err], "sync")
        return ok

    # --- batches
    def poll(self, bid, first=30, cap=300, max_wait=86400):
        t0, wait = time.time(), first
        while True:
            b = self.client.messages.batches.retrieve(bid)
            if g(b, "processing_status") == "ended":
                return b
            if time.time() - t0 > max_wait:
                return None
            rc = g(b, "request_counts")
            self.log(f"{bid} {g(b, 'processing_status')} processing={g(rc, 'processing', '?')}; next check {wait}s")
            self.sleep(wait)
            wait = min(cap, wait * 2)

    def fetch(self, bid, by_cid):
        counts, usage, usd, rows = {}, {}, 0.0, []
        for res in self.client.messages.batches.results(bid):
            r = by_cid.get(g(res, "custom_id"))
            if r is None:
                continue
            rr = g(res, "result")
            t = g(rr, "type")
            counts[t] = counts.get(t, 0) + 1
            if t != "succeeded":
                rows.append((r, None, [f"batch result {t}: {scrub(json.dumps(g(rr, 'error'), default=str))[:300]}"]))
                continue
            msg = g(rr, "message")
            u = usage_dict(g(msg, "usage"))
            for k, v in u.items():
                usage[k] = usage.get(k, 0) + v
            usd += usage_usd(self.prices, self.spec.model, u, batch=True)
            rows.append((r, msg, None))
        self.log_spend("batch", bid, self.spec.model, sum(counts.values()), counts, usage, usd)
        self.state["batches"][bid]["fetched"] = True
        self.save()
        ok = 0
        for r, msg, errs in rows:  # validate after the spend line, so retries see the batch cost
            if msg is None:  # errored / expired / canceled in the batch: one synchronous retry
                m2, err = self.call_sync(r, "sync_retry")
                if m2 is not None:
                    ok += self.finish(r, m2, "sync_retry", bid, retry=False)
                else:
                    self.reject(r, errs + [f"retry {err}"], "batch", bid)
            else:
                ok += self.finish(r, msg, "batch", bid)
        return ok

    def run_batches(self, reqs, chunk=10000, first=30, cap=300, max_wait=86400):
        by_cid = {r["cid"]: r for r in reqs}
        ok = 0
        for bid, b in self.state["batches"].items():  # resume: poll + fetch what was submitted before
            if not b.get("fetched"):
                if self.poll(bid, first, cap, max_wait) is None:
                    self.stopped = f"batch {bid} still processing after {max_wait}s; re-run to resume"
                    return ok
                ok += self.fetch(bid, by_cid)
        done = done_ids(self.out)
        todo = [r for r in reqs if str(r["item"]["id"]) not in done]
        for ch in chunks(todo, min(chunk, MAX_BATCH_REQ)):
            room = self.cap - self.spent()
            n, worst = fit_cap(ch, self.prices, self.spec.model, room)
            if n == 0:
                self.stopped = f"cap: spent ${self.spent():.4f}, next request worst case exceeds cap ${self.cap}"
                break
            trimmed, ch = n < len(ch), ch[:n]
            batch = self.client.messages.batches.create(requests=[{"custom_id": r["cid"], "params": r["params"]}
                                                                  for r in ch])
            bid = g(batch, "id")
            self.state["batches"][bid] = {"created": now(), "cids": [r["cid"] for r in ch], "fetched": False,
                                          "worst_usd": round(worst, 6)}
            self.save()
            self.log(f"submitted {bid}: {n} requests, worst ${worst:.4f}, spent ${self.spent():.4f} / cap ${self.cap}")
            if self.poll(bid, first, cap, max_wait) is None:
                self.stopped = f"batch {bid} still processing after {max_wait}s; re-run to resume"
                break
            ok += self.fetch(bid, by_cid)
            if trimmed:
                self.stopped = self.stopped or f"cap: chunk trimmed to {n} requests to stay under cap ${self.cap}"
            if self.stopped:
                break
        return ok


def dry_run(spec, reqs, prices, cap, batch=True):
    w = e = 0.0
    for r in reqs:
        a, b = estimate(r, prices, spec.model, batch)
        w, e = w + a, e + b
    pt = spec.prefix_tokens_est()
    mb = sum(r["bytes"] for r in reqs) / 2 ** 20
    print(f"DRY RUN {spec.name} {spec.prompt_version} model={spec.model} mode={spec.mode}: {len(reqs)} requests, "
          f"{mb:.2f} MB, prefix ~{pt} tok ({'caches' if pt >= TS.MIN_CACHE_TOKENS else 'WILL NOT CACHE: < 512'}), "
          f"cache_control ttl=1h")
    print(f"  estimated ${e:.4f} expected, ${w:.4f} worst ({'batch' if batch else 'sync'} prices, status "
          f"{prices.get('status')}); cap ${cap}: {'OK' if w <= cap else 'worst case EXCEEDS cap: run stops at cap'}")
    return {"n": len(reqs), "expected_usd": round(e, 6), "worst_usd": round(w, 6), "prefix_tokens": pt, "mb": mb}


def parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--items", required=True, help="JSONL {id, text, ...}")
    ap.add_argument("--out", required=True, help="run folder (private)")
    ap.add_argument("--cands", help="candidates.py output (verify-mode specs)")
    ap.add_argument("--key-file", help="vault file with ANTHROPIC_API_KEY= (used when the env var is unset)")
    ap.add_argument("--prices", default=str(PRICES))
    ap.add_argument("--cap-usd", type=float, help="override spec cap_usd (never above the workspace limit)")
    ap.add_argument("--chunk", type=int, default=10000, help="requests per batch (<= 100000)")
    ap.add_argument("--limit", type=int, help="first N items only (smoke test R2: --limit 3)")
    ap.add_argument("--sync", action="store_true", help="synchronous calls instead of batches (pilot)")
    ap.add_argument("--max-wait", type=int, default=86400, help="seconds to wait for one batch")
    ap.add_argument("--dry-run", action="store_true", help="offline: build + validate requests, print counts and cost")
    return ap


def main(argv=None, client=None):
    a = parser().parse_args(argv)
    spec = TS.load(a.spec)
    prices = load_prices(a.prices)
    items = read_jsonl(a.items)[: a.limit] if a.limit else read_jsonl(a.items)
    C = load_cands(a.cands) if a.cands else None
    cap = spec.cap_usd if a.cap_usd is None else a.cap_usd
    reqs = build_requests(spec, items, C, skip=done_ids(a.out))
    if a.dry_run:
        dry_run(spec, reqs, prices, cap, batch=not a.sync)
        return 0
    if client is None:
        key = read_key(a.key_file)
        try:
            client = make_client(key)
        except Exception as e:  # noqa
            raise SystemExit(scrub(e, key))
    R = Run(spec, a.out, client, prices, cap)
    try:  # no raw traceback: any failure is printed scrubbed (MM3-0026)
        ok = R.run_sync(reqs) if a.sync else R.run_batches(reqs, a.chunk, max_wait=a.max_wait)
    except BaseException as e:  # noqa
        raise SystemExit(f"stopped: {type(e).__name__}: {scrub(e)[:500]} (spent ${R.spent():.4f}; re-run resumes)")
    print(f"{ok} labels written to {pathlib.Path(a.out) / 'labels.jsonl'}; spent ${R.spent():.4f} of cap ${cap}"
          + (f"; STOPPED {R.stopped}" if R.stopped else ""))
    return 3 if R.stopped else 0


if __name__ == "__main__":
    sys.exit(main())
