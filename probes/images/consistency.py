"""Consistency test: ask the same fact several ways and see whether the answers agree.

    /workspace/kev/.venv/bin/python consistency.py run [task_id ...]      # ask Winnow, write results
    /workspace/kev/.venv/bin/python consistency.py report                 # print the table from stored results

Why: one yes/no per image cannot tell a real answer from a coin flip. A model that guesses is right on one
phrasing half the time, but rarely right on four phrasings of the same fact, so "right on every angle" is a
stricter, harder-to-fluke score.

Variants per item (all ask about the SAME fact; the expected answer for each is derived, never judged by eye):
  yes/no items  base | opposite wording (expected flips) | paraphrase | as a pick-one yes,no | pick-one no,yes
  pick-one items base | options reversed | "is the answer X?" for the true option (yes) and two wrong ones (no)
Default: each variant is its own request. `--batched` puts all variants of an image in one request, which is
faster but changes answers (seen: t26 base 19/25 alone, 11/25 inside a 5-question request).
Results: /workspace/data/image-lab/runs/winnow-consistency/<task>.jsonl, one row per item with every variant.
"""
import json, math, random, re, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from run_winnow import data_url

HERE = Path(__file__).parent
RUNS = Path("/workspace/data/image-lab/runs")
OUT = RUNS / "winnow-consistency"  # one variant per request (set by --batched to winnow-consistency-batched)
ENDPOINT, MODEL = "http://127.0.0.1:8091", "Winnow-12B"

# (opposite wording, paraphrase) per yes/no question. "Opposite" means the right answer flips.
WORDINGS = {
    "Is there a handwritten signature on this page?": ("Is this page free of any handwritten signature?", "Does this page carry a signature written by hand?"),
    "Has the form been signed?": ("Is the form still unsigned?", "Is there a signature on the form?"),
    "Is the box for accepting the terms ticked?": ("Is the terms box left empty?", "Has the terms checkbox been checked?"),
    "Is the full name field filled in?": ("Is the full name field empty?", "Has someone written a name in the name field?"),
    "Are two or more checkboxes ticked?": ("Are fewer than two checkboxes ticked?", "Do at least two checkboxes have a tick?"),
    "Is this vehicle visibly damaged?": ("Is this vehicle free of visible damage?", "Does the car show visible damage?"),
    "Is there a crack in this concrete?": ("Is this concrete free of cracks?", "Can you see a crack in the concrete surface?"),
    "Is this cardboard box defective?": ("Is this cardboard box in good condition?", "Does this cardboard box have a defect?"),
    "Is this fruit rotten?": ("Is this fruit fresh?", "Has this fruit gone bad?"),
    "Is there a person in this image who is NOT wearing a hard hat?": ("Is everyone in this image wearing a hard hat?", "Can you see anyone without a hard hat on?"),
    "Does this X-ray show a fracture?": ("Is this X-ray free of any fracture?", "Is a broken bone visible on this X-ray?"),
    "Does this chest X-ray show pneumonia or another abnormality?": ("Does this chest X-ray look normal?", "Is there evidence of pneumonia or another abnormality on this chest X-ray?"),
    "Is there a cavity (caries) visible on this dental X-ray?": ("Is this dental X-ray free of any cavity?", "Can you see tooth decay (caries) on this dental X-ray?"),
    "Does this lymph-node tissue patch contain tumour (metastasis)?": ("Is this lymph-node tissue patch free of tumour?", "Is there metastatic tumour in this lymph-node patch?"),
    "Is there fire or smoke in this frame?": ("Is this frame free of fire and smoke?", "Does the picture show fire or smoke?"),
    "Is there a spill or other dirt on this floor?": ("Is this floor free of spills and dirt?", "Can you see a spill or dirt on the floor?"),
}
ICON = re.compile(r"^(.*)Is that target an icon\?$", re.S)


def wordings(q):
    if q in WORDINGS:
        return WORDINGS[q]
    m = ICON.match(q)
    if m:  # the screenshot task: the instruction text differs per item, only the last sentence is asked about
        return m.group(1) + "Is that target a text label rather than an icon?", m.group(1) + "Does the instruction refer to an icon element?"
    raise KeyError(q)


def variants(item):
    """[(name, question, expected)] with expected in yes/no for noul variants and a label for pick-one variants."""
    q, exp = item["question"]["instructions"], item["expected"]
    if item["question"]["type"] == "noul":
        opp, para = wordings(q)
        crit = item["question"].get("criteria") or {}
        flipped = {"true": crit.get("false", ""), "false": crit.get("true", "")} if crit else None
        noul = lambda text, c: {"type": "noul", "instructions": text, **({"criteria": c} if c else {})}
        pick = lambda order: {"type": "choice", "instructions": q, "criteria": {k: None for k in order}}
        return [("base", noul(q, crit or None), exp), ("opposite", noul(opp, flipped), "no" if exp == "yes" else "yes"),
                ("paraphrase", noul(para, crit or None), exp), ("pick yes,no", pick(["yes", "no"]), exp), ("pick no,yes", pick(["no", "yes"]), exp)]
    labels = item["labels"]
    crit = item["question"]["criteria"]  # keep each option's own description, exactly as the base item sends it
    rng = random.Random(item["id"])
    wrong = [l for l in labels if l != exp]
    rng.shuffle(wrong)
    out = [("base", item["question"], exp),
           ("reversed", {"type": "choice", "instructions": q, "criteria": {l: crit[l] for l in reversed(labels)}}, exp),
           ("true is it", {"type": "noul", "instructions": f'{q} Is the answer "{exp}"?'}, "yes")]
    out += [(f"wrong is it {i + 1}", {"type": "noul", "instructions": f'{q} Is the answer "{w}"?'}, "no") for i, w in enumerate(wrong[:2])]
    return out


def ask(item):
    vs = variants(item)
    imgs = [data_url(p) for p in item["images"]]
    def post(qs):
        body = {"model": MODEL, "state": item["state"], "winnow": {"images": imgs}, "questions": qs}
        req = urllib.request.Request(ENDPOINT + "/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)["answers"]
    if BATCHED:
        ans = post({f"v{i}": q for i, (_, q, _) in enumerate(vs)})
    else:  # default: one question per request, because questions sharing a request were seen to change each other's answers
        ans = {}
        for i, (_, q, _) in enumerate(vs):
            ans[f"v{i}"] = post({"q": q})["q"]
    row = {"id": item["id"], "variants": []}
    for i, (name, q, exp) in enumerate(vs):
        a = ans[f"v{i}"]
        if q["type"] == "noul":
            p = float(a["noul"]); pred = "yes" if p >= 0.5 else "no"
        else:
            pred = a["choice"]; p = float(a["probabilities"].get(exp, 0))
        row["variants"].append({"name": name, "expected": exp, "predicted": pred, "correct": pred == exp, "p": round(p, 4)})
    return row


def run(tasks):
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ([HERE / f"{t}.jsonl" for t in tasks] if tasks else sorted(HERE.glob("t[0-9][0-9]_*.jsonl"))):
        items = [json.loads(l) for l in f.read_text().split("\n") if l.strip()]
        rows, t0 = [], time.time()
        for it in items:
            try:
                rows.append(ask(it))
            except Exception as e:  # a failed item is recorded, never scored as wrong
                rows.append({"id": it["id"], "error": f"{type(e).__name__}: {e}"[:200]})
        (OUT / f"{f.stem}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        print(f"{f.stem}: done in {time.time() - t0:.0f}s", flush=True)


def wilson(k, n, z=1.96):
    if not n: return 0.0, 1.0
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d


def report():
    print(f"{'task':28s} {'base':>6s} {'all angles':>10s} {'(chance)':>8s} {'mixed':>6s} {'angles':>6s}  weakest angle")
    for f in sorted(OUT.glob("t*.jsonl")):
        rows = [r for r in map(json.loads, f.read_text().split("\n")[:-1]) if "variants" in r]
        if not rows: continue
        n, k = len(rows), len(rows[0]["variants"])
        base = sum(r["variants"][0]["correct"] for r in rows)
        allc = sum(all(v["correct"] for v in r["variants"]) for r in rows)
        mixed = sum(0 < sum(v["correct"] for v in r["variants"]) < k for r in rows)
        # what a pure guesser would score on "right on every angle": each yes/no angle is a coin, a pick-one base is 1/options
        nopt = len(json.loads((HERE / f"{f.stem}.jsonl").read_text().split("\n")[0])["labels"])
        guess = (1 / nopt if rows[0]["variants"][0]["expected"] not in ("yes", "no") else 0.5) * 0.5 ** (k - 1)
        weak = min(range(k), key=lambda i: sum(r["variants"][i]["correct"] for r in rows))
        wn = rows[0]["variants"][weak]["name"]; wa = sum(r["variants"][weak]["correct"] for r in rows)
        print(f"{f.stem:28s} {base:>3d}/{n:<2d} {allc:>6d}/{n:<3d} {guess * 100:>7.1f}% {mixed:>6d} {k:>6d}  {wn} ({wa}/{n})")


BATCHED = "--batched" in sys.argv
if BATCHED:
    OUT = RUNS / "winnow-consistency-batched"
if "--dir" in sys.argv:
    OUT = RUNS / sys.argv[sys.argv.index("--dir") + 1]

if __name__ == "__main__":
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--dir"]
    cmd = args[0] if args else "report"
    run(args[1:]) if cmd == "run" else report()
