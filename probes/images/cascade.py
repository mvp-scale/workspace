"""Layered cascade: gate -> characteristics -> consensus (votes, not averages) -> targeted follow-ups -> outcome.
See LAYERED-METHOD.md. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.

    /workspace/kev/.venv/bin/python cascade.py run skin|dental|chest     # ask Winnow, store every answer
    /workspace/kev/.venv/bin/python cascade.py report skin|dental|chest  # score from the stored answers

Every probability is stored, so thresholds and rules can be re-scored without calling the model again.
Thresholds below are fixed in advance and are NOT tuned on the pilot images.
"""
import base64, json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
OUT = Path("/workspace/data/image-lab/runs/winnow-cascade")
ENDPOINT, MODEL = "http://127.0.0.1:8091", "Winnow-12B"

VOTE_YES, VOTE_NO = 0.65, 0.35           # P(yes) at or above / at or below these is a decisive vote
GATE_PASS, GATE_MIN = 0.80, 3            # share of decisive gate votes that must pass, and how many must be decisive
UNCLEAR_FRAC = 0.40                      # this share of layer-1 votes unsure -> UNCLEAR
SUPPORT_BAR, MIN_VOTES, GAP, CONFLICT = 0.70, 5, 0.15, 0.60


def url(path):
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def post(img, state, questions):
    body = {"model": MODEL, "state": state, "winnow": {"images": [img]}, "questions": questions}
    req = urllib.request.Request(ENDPOINT + "/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["answers"]


def noul(q):
    return {"type": "noul", "instructions": q}


def ask_item(spec, item):
    img = url(item["image"]); rec = {"id": item["id"], "expected": item["expected"]}
    # baseline: the original single question, exactly as the lab asks it
    a = post(img, "An image is attached.", {"q": item["question"]})["q"]
    rec["baseline"] = {"yes": float(a["noul"])} if item["question"]["type"] == "noul" else {k: float(v) for k, v in a["probabilities"].items()}
    # stage 1: gate + characteristics, one batched request (questions are evaluated independently)
    qs = {g["id"]: noul(g["q"]) for g in spec["gate"]} | {f["id"]: noul(f["q"]) for f in spec["features"]}
    ans = post(img, spec["state_gate"], qs)
    rec["stage1"] = {k: float(v["noul"]) for k, v in ans.items()}
    # stage 2 only for the two best-supported hypotheses
    top = rank(spec, rec["stage1"], {})
    lead = [c for c, _ in top[:2]]
    ds = [d for d in spec["discriminators"] if set(d["when"]) & set(lead)]
    rec["stage2_for"] = lead
    rec["stage2"] = {}
    if ds:
        ans2 = post(img, spec["state_after_gate"], {d["id"]: noul(d["q"]) for d in ds})
        rec["stage2"] = {k: float(v["noul"]) for k, v in ans2.items()}
    return rec


MEDIAN = {}   # per-question median P(yes) over the batch; used only when --relative is given (needs no labels)
REL_DELTA = 0.10


def vote(p, qid=None):
    if MEDIAN and qid in MEDIAN:
        return "yes" if p >= MEDIAN[qid] + REL_DELTA else "no" if p <= MEDIAN[qid] - REL_DELTA else "unsure"
    return "yes" if p >= VOTE_YES else "no" if p <= VOTE_NO else "unsure"


def tally(spec, probs, items):
    """per class: [votes for, votes against] from the decisive answers of the listed feature specs."""
    t = {c: [0, 0] for c in spec["classes"]}
    for f in items:
        v = vote(probs[f["id"]], f["id"]) if f["id"] in probs else "unsure"
        if v == "unsure": continue
        for c in f["for"]: t[c][0 if v == "yes" else 1] += 1
        for c in f["against"]: t[c][1 if v == "yes" else 0] += 1
    return t


def rank(spec, p1, p2):
    items = spec["features"] + [d for d in spec["discriminators"] if d["id"] in p2]
    t = tally(spec, {**p1, **p2}, items)
    sc = {c: (v[0] / (v[0] + v[1]) if v[0] + v[1] else 0.0, v[0] + v[1], v[0]) for c, v in t.items()}
    return sorted(((c, s) for c, s in sc.items()), key=lambda x: (-x[1][0], -x[1][2]))


def average_pick(spec, p1, p2):
    """the plain-average comparison: mean of aligned probabilities per class"""
    items = spec["features"] + [d for d in spec["discriminators"] if d["id"] in p2]; probs = {**p1, **p2}; best = None
    for c in spec["classes"]:
        al = [probs[f["id"]] if c in f["for"] else 1 - probs[f["id"]] for f in items if (c in f["for"] or c in f["against"]) and f["id"] in probs]
        s = sum(al) / len(al) if al else 0
        if best is None or s > best[1]: best = (c, s)
    return best[0]


def outcome(spec, rec):
    p1, p2 = rec["stage1"], rec["stage2"]
    gv = [(g, vote(p1[g["id"]], g["id"])) for g in spec["gate"]]
    dec = [(g, v) for g, v in gv if v != "unsure"]
    passed = sum(v == g["pass"] for g, v in dec)
    if len(dec) >= GATE_MIN and passed / len(dec) < GATE_PASS:
        return {"code": "NOT_USABLE", "pick": None, "detail": f"{passed}/{len(dec)} gate votes passed"}
    f_votes = [vote(p1[f["id"]], f["id"]) for f in spec["features"]]
    if sum(v == "unsure" for v in f_votes) / len(f_votes) >= UNCLEAR_FRAC:
        pick = rank(spec, p1, p2)[0][0]
        return {"code": "UNCLEAR", "pick": pick, "detail": f"{sum(v == 'unsure' for v in f_votes)}/{len(f_votes)} feature votes unsure"}
    r = rank(spec, p1, p2); (c1, (s1, n1, _)), (c2, (s2, n2, _)) = r[0], r[1]
    if s1 >= CONFLICT and s2 >= CONFLICT:
        return {"code": "CONFLICT", "pick": c1, "detail": f"{c1} {s1:.2f} and {c2} {s2:.2f}"}
    if s1 >= SUPPORT_BAR and n1 >= MIN_VOTES and s1 - s2 >= GAP:
        return {"code": "CONSENSUS", "pick": c1, "detail": f"{c1} support {s1:.2f} over {n1} votes"}
    return {"code": "WEAK", "pick": c1, "detail": f"{c1} support {s1:.2f} over {n1} votes"}


def truth(spec, rec):
    return spec["map"][rec["expected"]] if "map" in spec else rec["expected"]


def base_pick(spec, rec):
    b = rec["baseline"]
    if "yes" in b:
        y = b["yes"] >= 0.5
        return next(c for k, c in spec["map"].items() if (k == "yes") == y)
    return max(b, key=b.get)


def run(name):
    spec = json.load(open(HERE / "cascades" / f"{name}.json")); items = [json.loads(l) for l in open(HERE / "pilots" / f"{spec['pilot']}.jsonl")]
    OUT.mkdir(parents=True, exist_ok=True); t0 = time.time()

    def safe(it):
        try: return ask_item(spec, it)
        except Exception as e: return {"id": it["id"], "error": f"{type(e).__name__}: {e}"[:200]}
    with ThreadPoolExecutor(4) as ex: rows = list(ex.map(safe, items))
    (OUT / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"{name}: {len(rows)} images in {time.time() - t0:.0f}s, {sum('error' in r for r in rows)} errors")


def report(name):
    spec = json.load(open(HERE / "cascades" / f"{name}.json")); rows = [r for r in map(json.loads, open(OUT / f"{name}.jsonl")) if "error" not in r]
    MEDIAN.clear()
    if "--relative" in sys.argv:
        for q in rows[0]["stage1"]:
            v = sorted(r["stage1"][q] for r in rows); MEDIAN[q] = v[len(v) // 2]
        for q in {k for r in rows for k in r["stage2"]}:
            v = sorted(r["stage2"][q] for r in rows if q in r["stage2"]); MEDIAN[q] = v[len(v) // 2]
        print("(votes are relative to each question's own median over the batch; no labels used)")
    n = len(rows); out = {r["id"]: outcome(spec, r) for r in rows}
    acc = lambda f: sum(f(r) == truth(spec, r) for r in rows)
    single = acc(lambda r: base_pick(spec, r))
    avg = acc(lambda r: average_pick(spec, r["stage1"], r["stage2"]))
    forced = sum(out[r["id"]]["pick"] == truth(spec, r) for r in rows if out[r["id"]]["pick"])
    nopick = sum(out[r["id"]]["pick"] is None for r in rows)
    print(f"\n== {name}: {n} images, chance {100 / len(spec['classes']):.0f}% ==")
    print(f"single original question      : {single}/{n} = {single / n * 100:.0f}%")
    print(f"plain average of the layer's answers: {avg}/{n} = {avg / n * 100:.0f}%")
    print(f"cascade, forced best guess    : {forced}/{n} = {forced / n * 100:.0f}% ({nopick} images had no guess: gate failed)")
    cons = [r for r in rows if out[r['id']]['code'] == "CONSENSUS"]; ok = sum(out[r["id"]]["pick"] == truth(spec, r) for r in cons)
    print(f"cascade, CONSENSUS only       : handled {len(cons)}/{n} = {len(cons) / n * 100:.0f}%, right on {ok}/{len(cons)}" + (f" = {ok / len(cons) * 100:.0f}%" if cons else ""))
    # the single question taken the same way: handle the most confident until precision falls under 95%
    conf = sorted(((max(r["baseline"].values()) if "yes" not in r["baseline"] else max(r["baseline"]["yes"], 1 - r["baseline"]["yes"]), base_pick(spec, r) == truth(spec, r)) for r in rows), key=lambda x: -x[0])
    h = max([k for k in range(1, n + 1) if sum(c for _, c in conf[:k]) / k >= 0.95] or [0])
    print(f"single question, most confident first while precision >= 95%: handled {h}/{n} = {h / n * 100:.0f}%")
    print("where the problems sit (outcome: images, right if forced):")
    for code in ("NOT_USABLE", "UNCLEAR", "CONFLICT", "WEAK", "CONSENSUS"):
        g = [r for r in rows if out[r["id"]]["code"] == code]
        if g: print(f"  {code:10s} {len(g):3d}   right {sum(out[r['id']]['pick'] == truth(spec, r) for r in g if out[r['id']]['pick'])}/{sum(out[r['id']]['pick'] is not None for r in g)}")
    if "map" in spec:
        pos = spec["map"]["yes"]; fp = lambda f: sum(f(r) == pos and truth(spec, r) != pos for r in rows)
        print(f"false positives (said {pos}, was not): single {fp(lambda r: base_pick(spec, r))}, cascade-forced {sum(out[r['id']]['pick'] == pos and truth(spec, r) != pos for r in rows)}, consensus-handled {sum(out[r['id']]['pick'] == pos and truth(spec, r) != pos for r in cons)}")
    n1 = len(spec["gate"]) + len(spec["features"]); n2 = sum(len(r["stage2"]) for r in rows) / n
    print(f"questions per image: 1 baseline + {n1} gate/characteristics + {n2:.1f} follow-ups")


def cv(name, folds=5, seed=0):
    """Supervised upper bound: 5-fold cross-validated logistic regression on the stage-1 answers. Tells whether the information is in the answers, whatever the hand mapping says."""
    import numpy as np
    spec = json.load(open(HERE / "cascades" / f"{name}.json")); rows = [r for r in map(json.loads, open(OUT / f"{name}.jsonl")) if "error" not in r]
    ids = [x["id"] for x in spec["gate"] + spec["features"]]; cl = spec["classes"]
    X = np.array([[r["stage1"][i] for i in ids] for r in rows]); X = (X - X.mean(0)) / (X.std(0) + 1e-6)
    y = np.array([cl.index(truth(spec, r)) for r in rows]); rng = np.random.RandomState(seed); idx = rng.permutation(len(rows)); correct = 0
    for k in range(folds):
        te = idx[k::folds]; tr = np.setdiff1d(idx, te); W = np.zeros((X.shape[1], len(cl))); b = np.zeros(len(cl)); Y = np.eye(len(cl))[y[tr]]
        for _ in range(400):
            Z = X[tr] @ W + b; P = np.exp(Z - Z.max(1, keepdims=True)); P /= P.sum(1, keepdims=True)
            G = (P - Y) / len(tr); W -= 0.5 * (X[tr].T @ G + 0.05 * W); b -= 0.5 * G.sum(0)
        correct += int(((X[te] @ W + b).argmax(1) == y[te]).sum())
    print(f"{name}: cross-validated logistic regression on the {len(ids)} stage-1 answers: {correct}/{len(rows)} = {correct / len(rows) * 100:.0f}%  (chance {100 / len(cl):.0f}%)")


if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2]
    {"run": run, "report": report, "cv": cv}[cmd](name)
