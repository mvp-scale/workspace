"""P4 sample: choose the 25,000 items to pay to label. Free CPU only. Writes runs/p5/{sample_ids.txt,manifest.json}.
Rule: all gate-flagged items (minus near-duplicates of the frozen test and the 1,000 pilot items), then random fill in the pool's source mix."""
import hashlib, json, pathlib, random, collections, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "kit/live"))
from heartbeat import beat, finish
H = pathlib.Path(__file__).resolve().parent; N = 25000
beat("p5-sample", where="[CPU]", task="T5", state="running", progress="drawing the 25,000-item sample", why="This list decides which items we pay to label, so it must be rich in rare conditions and clean of test copies", success="Zero overlap with the frozen test and the near-duplicate list; at least 1.5x the rare cases of a random draw", next="Cards T05/T06 label this list; you see the item count and cap before any spend", need="Nothing")
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
pool = [r["id"] for r in J(H / "data/pool_train.jsonl")]; src = lambda i: i.split(":")[0]
flag = [i for i in open(H / "runs/p4/gate_flagged_ids.txt").read().split() if i]
bad = set(open(H / "runs/p4/exclude_near_dups_of_test.txt").read().split()); pilot = {r["id"] for r in J(H / "data/pilot1000.jsonl")}
test = {r.get("id") or r.get("item_id") for r in J(H / "data/pilot300.jsonl")}
poolset = set(pool); take = [i for i in dict.fromkeys(flag) if i in poolset and i not in bad and i not in pilot and i not in test]
rnd = random.Random(20261031); chosen = set(take); rest = [i for i in pool if i not in chosen and i not in bad and i not in pilot and i not in test]
need = N - len(take); mix = collections.Counter(src(i) for i in rest); by = collections.defaultdict(list)
for i in rest: by[src(i)].append(i)
fill = []
for k, c in mix.items(): rnd.shuffle(by[k]); fill += by[k][: round(need * c / len(rest))]
fill = fill[:need]; sample = take + fill
(H / "runs/p5/sample_ids.txt").write_text("\n".join(sample) + "\n")
sh = hashlib.sha256(("\n".join(sample) + "\n").encode()).hexdigest()[:16]
m = {"items": len(sample), "flagged": len(take), "random_fill": len(fill), "sha8x2": sh, "overlap_pilot300": len(set(sample) & test), "overlap_near_dups": len(set(sample) & bad), "overlap_pilot1000": len(set(sample) & pilot),
     "source_share_sample": {k: round(v / len(sample), 3) for k, v in collections.Counter(src(i) for i in sample).items()}, "source_share_pool": {k: round(v / len(pool), 3) for k, v in collections.Counter(src(i) for i in pool).items()},
     "expected_with_condition": round(len(take) * 0.61 + len(fill) * 0.129), "expected_random_25k": round(N * 0.129)}
m["expected_ratio"] = round(m["expected_with_condition"] / m["expected_random_25k"], 2)
(H / "runs/p5/manifest.json").write_text(json.dumps(m, indent=1)); finish("p5-sample", "done", last=f"{len(sample)} items, ratio {m['expected_ratio']}x"); print(json.dumps(m, indent=1))
