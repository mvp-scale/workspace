"""T42 information test, gate method on FULL articles (pre-registered L997); copy of topic_gate_mnds.py with the sample and view changed. Original docstring: T42 step 3a (pre-registered L972): the topic answer assembled from gate evidence, scored on the 1600 fresh MN-DS articles against the human labels, with the same lenient scoring and topic-to-IPTC map as the trained head (percat_anchor.py). Primary = the method of pulse_assemble.py (an item votes for a domain only when that domain is among its top two matches over dials and domains, at match score 3.5 or more); variant B = every item votes for its own best domain at 3.5 or more. No theme votes: the items are one to three sentences. Nothing is trained on MN-DS.
    /workspace/models/embed-zs/.venv/bin/python topic_gate_mnds.py   (from projects/world-state)"""
import math
src = "\n".join(open("wide_net.py").read().split("\n")[:65]); exec(src)            # setup of wide_net.py: data, split, vocabulary, open layer; no Clef or article work
TAUB = 3.5; print("setup done", flush=True)
def embed_items(ITEMS): return [np.array([emb(wrap(p)) for _, p in it[0]]) if it[0] else np.zeros((0, VM.shape[1])) for it in ITEMS]
ITK = story_items([T[i] for i in cal]); EK = embed_items(ITK); allk = np.concatenate([e for e in EK if len(e)]); Sd, Sdom = sims(allk); mu, sd = Sd.mean(0), Sd.std(0) + 1e-6; dmu, dsd = Sdom.mean(0), Sdom.std(0) + 1e-6; print("background from", len(allk), "calibration items", flush=True)
import sys, random
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1600; CAP = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; gl = {v["l1"] for v in json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json")).values()}
RR = [json.loads(l) for l in open("/workspace/data/anchors/mn_ds/train.jsonl")]
RR = [r for r in RR if r.get("content") and r.get("title") and r["category_level_1"] in gl and len(r["content"]) >= 800]
rng = random.Random(20261105); by = collections.defaultdict(list)
for r in RR: by[r["category_level_1"]].append(r)
SS = []
for c in sorted(by): SS += rng.sample(by[c], 100)
SS = SS[:N] if N >= 1600 else [SS[i] for i in range(0, 1600, 1600 // N)][:N]
items = [{"id": str(i), "l1": r["category_level_1"]} for i, r in enumerate(SS)]; Gd = {it["id"]: {"l1": it["l1"]} for it in items}
views = [re.sub(r"\s+", " ", r["title"] + ". " + r["content"])[:CAP] for r in SS]; t0 = time.time(); ITM = story_items(views); EM = embed_items(ITM); print("full-article items embedded", len(EM), "in", round(time.time() - t0), "s", flush=True)
names = [d["id"] for d in DOM]
def votes_for(e, primary):
    v = collections.defaultdict(float)
    for row in e:
        a, b = sims(row[None]); za = ((a - mu) / sd)[0]; zb = ((b - dmu) / dsd)[0]
        if primary:
            top = sorted([(float(za[d]), "dial", d) for d in np.argsort(-za)[:2]] + [(float(zb[d]), "domain", d) for d in np.argsort(-zb)[:1]], reverse=True)[:2]
            for z, k, d in top:
                if k == "domain" and z >= TAUB: v[names[d]] += z
        else:
            d = int(np.argmax(zb))
            if zb[d] >= TAUB: v[names[d]] += float(zb[d])
    return v
def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den; return [round(c - h, 3), round(c + h, 3)]
res = {"articles": len(items), "threshold": TAUB, "map": "specs/topic_to_iptc_v1.json", "gold": "mn_ds gold_T28b l1", "calibration_items_for_background": int(len(allk))}
for nm, primary in (("primary_pulse_assemble_method", True), ("variant_B_each_item_votes_for_its_best_domain", False)):
    hit = {1: 0, 2: 0, 3: 0}; unk = 0
    for it, e in zip(items, EM):
        v = votes_for(e, primary) if len(e) else {}; rank = [n for n, _ in sorted(v.items(), key=lambda kv: -kv[1])]; unk += not rank; g = Gd[it["id"]]["l1"]
        for k in (1, 2, 3): hit[k] += any(g in M.get(x, []) for x in rank[:k])
    n = len(items); res[nm] = {f"top{k}_lenient_rate": round(hit[k] / n, 3) for k in (1, 2, 3)} | {f"top{k}_lenient_ci95": wilson(hit[k], n) for k in (1, 2, 3)} | {"unknown_share": round(unk / n, 3)}
tr = json.load(open("runs/pulse/anchor_mnds_fresh_v6b-student.json")); res["trained_head_for_comparison"] = {"top1_lenient_rate": tr["top1_lenient_rate"], "top2_lenient_rate": tr["top2_lenient_rate"], "top2_lenient_ci95": tr["top2_lenient_ci95"], "source": "runs/pulse/anchor_mnds_fresh_v6b-student.json"}
res["view_cap_chars"] = CAP; res["articles_scored"] = len(items); json.dump(res, open("runs/pulse/topic_gate_fulltext.json" if N >= 1600 else "/tmp/claude-0/-workspace/9a1e4c0f-d8b5-4941-bf45-6c192267eff5/scratchpad/topic_gate_fulltext_timing.json", "w"), indent=1); print(json.dumps(res, indent=1))
