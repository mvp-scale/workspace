"""Bake-off option B: one narrow question per condition (all 38 answered separately, passing mention = none). usage: bakeoff_b.py <n_items> <outname>"""
import json, pathlib, random, subprocess, sys, glob, copy
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; PY = H.parent / ".venv/bin/python"; KIT = H.parents[1] / "kit/teacher/claude_batch.py"
n, name = int(sys.argv[1]), sys.argv[2]; out = H / "runs/bakeoff" / name; out.mkdir(parents=True, exist_ok=True)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
base = json.load(open(H / "specs/world_state_v2_frozen_haiku.json")); defs = [l for l in base["guideline"] if " | up = " in l and not l.startswith("CONDITIONS")]
ids38 = [l.split(":")[0] for l in defs]; assert len(ids38) == 38, len(ids38)
intro = ["You read one news item (headline and description) and answer 38 separate questions, one per condition below.",
 "For EACH condition answer 'none', 'up' or 'down'. Answer 'up' or 'down' only if the item's own main reported event changes that condition in a way people would notice.",
 "A passing mention, background, a forecast of something that has not happened, or a condition only implied by general knowledge is 'none'. Most conditions will be 'none' for most items.",
 "Judge each condition on its own, ignoring the other 37. Do not pick a best one: several can be up or down, or all can be none.", "", "CONDITIONS (id: meaning | up = ... | down = ...)"]
spec = copy.deepcopy(base); spec.update(name=f"cond_B_{name}", prompt_version="cond-B-v0", layers=["CONDITIONS"], max_tokens=700, guideline=intro + defs, examples=[])
spec["output_schema"] = {"type": "object", "additionalProperties": False, "required": ids38, "properties": {k: {"type": "string", "enum": ["none", "up", "down"]} for k in ids38}}
H_, S_ = {}, {}
for f in glob.glob(str(H / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H_[r["item_id"]] = r["label"]
for f in glob.glob(str(H / "runs/p7b/*/labels.jsonl")):
    for r in J(f): S_[r["item_id"]] = r["label"]
cs = lambda L: {c["condition"] for c in L["conditions"]}; v = sorted(i for i in S_ if i in H_)
agree = [i for i in v if cs(H_[i]) & cs(S_[i])]; dis = [i for i in v if (cs(H_[i]) != cs(S_[i])) and not (cs(H_[i]) & cs(S_[i]))]; none = [i for i in v if not cs(H_[i]) and not cs(S_[i])]
rnd = random.Random(20261101); [rnd.shuffle(x) for x in (agree, dis, none)]; k = n // 3; pick = agree[:k] + dis[:k] + none[:n - 2 * k]
pool = {r["id"]: r for r in J(H / "data/pool_train.jsonl")}; (out / "items.jsonl").write_text("".join(json.dumps(pool[i]) + "\n" for i in pick)); (out / "ids.json").write_text(json.dumps({"agree": agree[:k], "disagree": dis[:k], "none": none[:n - 2 * k]}))
for fam, model in (("haiku", "claude-haiku-5-5"), ("sonnet", "claude-sonnet-5-5")):
    s = copy.deepcopy(spec); s["model"] = model; s["name"] += f"_{fam}"; (out / f"spec_{fam}.json").write_text(json.dumps(s))
beat(f"bakeoff-B-{name}", where="[CPU]+[API]", task="T8", state="running", progress=f"option B on {len(pick)} items, Haiku and Sonnet", cap=8.0, why="Tests whether asking one narrow question per condition beats the 38-way pick", success="Haiku-Sonnet exact condition overlap above today's 0.477 on the same items (predicted 0.60-0.70)", next="Score against option A on the same items; then options C, D, H", need="Nothing")
ps = [subprocess.Popen([str(PY), str(KIT), "--spec", str(out / f"spec_{fam}.json"), "--items", str(out / "items.jsonl"), "--out", str(out / fam), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "8"], stdout=open(out / f"{fam}.log", "w"), stderr=subprocess.STDOUT) for fam in ("haiku", "sonnet")]
[p.wait() for p in ps]
B = {f: {r["item_id"]: {k: x for k, x in r["label"].items() if x != "none"} for r in J(out / f / "labels.jsonl")} for f in ("haiku", "sonnet")}
def ov(a, b, ids, key=lambda x: x):
    r = []
    for i in ids:
        x, y = key(a.get(i)), key(b.get(i))
        if x is None or y is None or not (x or y): continue
        r.append(len(x & y) / len(x | y))
    return round(sum(r) / max(len(r), 1), 3), len(r)
bs = lambda d: set(d) if d is not None else None; ac = lambda d: cs(d) if d is not None else None
ids = [i for i in pick if i in B["haiku"] and i in B["sonnet"]]
res = {"items": len(pick), "both_answered": len(ids), "spend": {f: round(sum(json.loads(l).get("usd", 0) for l in open(out / f / "spend.jsonl")), 3) for f in ("haiku", "sonnet")},
 "B_haiku_vs_sonnet": ov({i: B["haiku"][i] for i in ids}, {i: B["sonnet"][i] for i in ids}, ids, bs), "A_haiku_vs_sonnet_same_items": ov({i: H_[i] for i in ids}, {i: S_[i] for i in ids}, ids, ac),
 "B_haiku_vs_A_haiku": ov({i: B["haiku"][i] for i in ids}, {i: H_[i] for i in ids}, ids, lambda d: bs(d) if not isinstance(d, dict) or "topic" not in d else cs(d)), "B_rate_with_condition": {f: round(sum(1 for i in ids if B[f][i]) / max(len(ids), 1), 3) for f in B}, "A_rate_with_condition": {"haiku": round(sum(1 for i in ids if cs(H_[i])) / max(len(ids), 1), 3), "sonnet": round(sum(1 for i in ids if cs(S_[i])) / max(len(ids), 1), 3)}}
(out / "yield.json").write_text(json.dumps(res, indent=1)); finish(f"bakeoff-B-{name}", "done", spent=round(sum(res["spend"].values()), 2), last=f"B {res['B_haiku_vs_sonnet'][0]} vs A {res['A_haiku_vs_sonnet_same_items'][0]}"); print(json.dumps(res, indent=1))
