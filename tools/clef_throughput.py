#!/usr/bin/env python3
"""Throughput of a /v1/systemone server (default: clef-flash-q4km on :8018) at rising concurrency.

    python3 tools/clef_throughput.py                       # sweep 1,2,4,8,16 workers, 24 requests each level
    python3 tools/clef_throughput.py -c 8 -n 64            # one level
    python3 tools/clef_throughput.py --words 100,400,1600  # state sizes cycled across requests

Every request is different: a random-length state (so size varies), a unique opening line (so the server's prompt cache
cannot answer it), a random 0..--jitter ms pause before each request, GPU stats sampled from nvidia-smi, and a question battery of --noul noul + --choice choice + --score score questions. Standard library only.
"""
import argparse, json, random, statistics, subprocess, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

WORDS = ("the customer asked about billing and the invoice was late so the team checked the payment system while a "
         "service outage blocked orders and managers worried about risk, cost, trust and deadlines this week").split()
NOUL = ["Is a service down?", "Is money involved?", "Is anyone angry?", "Is there a deadline?", "Is a customer waiting?",
        "Is this a repeat problem?", "Is a manager involved?", "Does it need an apology?", "Is data at risk?",
        "Is this urgent?", "Is legal risk present?", "Can it be fixed today?"]
CHOICE = [("Which team should handle this?", {"billing": "Payments or invoices", "technical": "Bugs or outages", "account": "Access or profile"}),
          ("What is the tone?", {"calm": "Neutral and polite", "tense": "Frustrated", "hostile": "Angry or threatening"})]
SCORE = [("How urgent is it?", ["Can wait", "This week", "Today"]), ("How severe is the impact?", ["Minor", "Moderate", "Severe"])]


def make_request(rng, words, n_noul, n_choice, n_score):
    n = rng.choice(words)
    state = f"Case {rng.getrandbits(48):x}. " + " ".join(rng.choice(WORDS) for _ in range(n))
    q = {}
    for i in range(n_noul): q[f"n{i}"] = {"type": "noul", "instructions": NOUL[i % len(NOUL)]}
    for i in range(n_choice): t, c = CHOICE[i % len(CHOICE)]; q[f"c{i}"] = {"type": "choice", "instructions": t, "criteria": c}
    for i in range(n_score): t, c = SCORE[i % len(SCORE)]; q[f"s{i}"] = {"type": "score", "instructions": t, "criteria": c}
    return {"state": state, "questions": q}, n


def post(url, key, body, timeout):
    h = {"Content-Type": "application/json"}
    if key: h["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url + "/v1/systemone", json.dumps(body).encode(), h)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read()); ok = r.status == 200 and len(data.get("answers", {})) == len(body["questions"])
            tok = data.get("usage", {}).get("input_tokens", 0)
    except urllib.error.HTTPError as e: ok, tok = False, 0; e.read()
    except Exception: ok, tok = False, 0
    return ok, (time.perf_counter() - t0) * 1000, tok


class Gpu:
    """Samples nvidia-smi every `period` s while a level runs: mean/peak utilisation, mean/peak power, peak memory."""
    Q = "utilization.gpu,power.draw,memory.used,temperature.gpu,clocks.sm"
    def __init__(self, period=0.25): self.period, self.rows, self.stop = period, [], threading.Event()
    def _run(self):
        while not self.stop.is_set():
            try:
                out = subprocess.run(["nvidia-smi", f"--query-gpu={self.Q}", "--format=csv,noheader,nounits", "-i", "0"], capture_output=True, text=True, timeout=5).stdout
                self.rows.append([float(x) for x in out.strip().split(",")])
            except Exception: pass
            self.stop.wait(self.period)
    def __enter__(self): self.t = threading.Thread(target=self._run, daemon=True); self.t.start(); return self
    def __exit__(self, *e): self.stop.set(); self.t.join()
    def summary(self):
        if not self.rows: return "gpu n/a"
        c = list(zip(*self.rows)); m = lambda i: statistics.mean(c[i])
        return f"util {m(0):.0f}% (peak {max(c[0]):.0f}%)  power {m(1):.0f} W (peak {max(c[1]):.0f})  mem peak {max(c[2]) / 1024:.1f} GiB  temp {max(c[3]):.0f}C  sm clock {m(4):.0f} MHz"


def level(a, workers, total):
    rng = random.Random(a.seed + workers)
    reqs = [make_request(rng, a.words, a.noul, a.choice, a.score) for _ in range(total)]
    def one(r):
        time.sleep(random.uniform(0, a.jitter) / 1000)       # jitter: each request waits a random 0..jitter ms, so workers drift apart
        return post(a.url, a.key, r[0], a.timeout)
    with Gpu() as gpu:
        t0 = time.perf_counter()
        with ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(one, reqs))
        wall = time.perf_counter() - t0
    lat = sorted(ms for ok, ms, _ in res if ok); fails = sum(not ok for ok, _, _ in res)
    q = a.noul + a.choice + a.score
    p = lambda f: lat[min(len(lat) - 1, int(f * len(lat)))] if lat else float("nan")
    print(f"{workers:>5} {total:>5} {fails:>5} {len(lat) / wall:>7.2f} {len(lat) * q / wall:>8.1f} {sum(t for _, _, t in res) / wall:>9.0f} "
          f"{statistics.mean(lat) if lat else float('nan'):>8.0f} {p(.5):>7.0f} {p(.95):>7.0f}", flush=True)
    print(f"        {gpu.summary()}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8018"); ap.add_argument("--key", default="")
    ap.add_argument("-c", "--concurrency", default="1,2,4,8,16", help="comma list of worker counts")
    ap.add_argument("-n", "--requests", type=int, default=0, help="requests per level (default: 3 x workers, at least 12)")
    ap.add_argument("--words", default="60,200,600,1500", type=lambda s: [int(x) for x in s.split(",")], help="state sizes in words, cycled at random")
    ap.add_argument("--noul", type=int, default=10); ap.add_argument("--choice", type=int, default=2); ap.add_argument("--score", type=int, default=2)
    ap.add_argument("--jitter", type=float, default=150, help="max random delay in ms before each request (0 = none)")
    ap.add_argument("--timeout", type=float, default=300); ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    post(a.url, a.key, make_request(random.Random(0), [50], 2, 1, 1)[0], a.timeout)       # warm-up, not counted
    print(f"{a.url}  {a.noul} noul + {a.choice} choice + {a.score} score per request; state sizes {a.words} words")
    print(f"{'conc':>5} {'reqs':>5} {'fail':>5} {'req/s':>7} {'quest/s':>8} {'in tok/s':>9} {'mean ms':>8} {'p50 ms':>7} {'p95 ms':>7}")
    for w in [int(x) for x in a.concurrency.split(",")]:
        level(a, w, a.requests or max(12, 3 * w))


if __name__ == "__main__":
    main()
