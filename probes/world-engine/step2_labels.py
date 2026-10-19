"""Step 2 of the Fable method (ledger S-0002): majority vote over Clef's three wordings per engine attribute; every vote kept; no label model.
Inputs: data/newsreader/labels/clef-q4km.jsonl (wordings 0 and 1) and clef-q4km-w3.jsonl (wording 2 = the attribute's definition).
Vote: a wording says yes when its probability >= 0.65 (the engine's ATTR_MIN). Attribute = majority of 3. Key present = any attribute present.
Conflict = both directions of a condition present (the engine's consistency rule).
Writes data/step2/labels.jsonl (per story: probabilities, votes, MV, key labels, agreement, conflicts) and data/step2/report.json.
Run: cd /workspace/probes/world-engine && WORLD_GPU=0 /workspace/kev/.venv/bin/python step2_labels.py"""
import os, sys, json, time
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
import numpy as np
sys.path.insert(0, "/workspace/probes/persona"); sys.path.insert(0, "/workspace/probes/world-engine")
import sensitivity as SN
C = SN.C; OUT = "/workspace/data/step2"; VOTE = C.ATTR_MIN
def main():
    os.makedirs(OUT, exist_ok=True); t0 = time.time()
    W3 = {r["id"]: r["P3"] for r in map(json.loads, open(SN.LABELS.replace(".jsonl", "-w3.jsonl")))}
    recs = [json.loads(l) for l in open(SN.LABELS)]; stories = SN.load_stories()
    keys = ["|".join(k) for k in SN.KEYS]; rows = []
    yes_w = {k: [set(), set(), set()] for k in keys}; mv_pos = {k: set() for k in keys}; cur_pos = {k: set() for k in keys}; unanimous = {k: 0 for k in keys}
    mv_stories = []
    for r, st in zip(recs, stories):
        P = {**r["P"], **W3[r["id"]]}; attrs = {}; key_mv = {}; key_agree = {}
        for (d, dirn), lst in C.ATTRS.items():
            k = f"{d}|{dirn}"; any_mv = False; best = 0.0; votes_k = []
            for i, a in enumerate(lst):
                ps = [P[f"a|{d}|{dirn}|{i}|{w}"] for w in (0, 1, 2)]; vs = [p >= VOTE for p in ps]; mv = sum(vs) >= 2
                attrs[f"{k}|{i}"] = {"p": [round(x, 4) for x in ps], "votes": vs, "mv": mv}; votes_k.append(vs)
                for w in range(3):
                    if vs[w]: yes_w[k][w].add(r["id"])
                if mv: any_mv = True; best = max(best, float(np.mean(ps)))
            key_mv[k] = any_mv
            if any_mv:
                mv_pos[k].add(r["id"]); n_yes = max(sum(v) for v in votes_k); key_agree[k] = f"{n_yes}/3"
                if n_yes == 3: unanimous[k] += 1
            if (d, dirn) in st["keys"]: cur_pos[k].add(r["id"])
        conflicts = sorted({d for (d, dirn) in C.ATTRS if key_mv.get(f"{d}|up") and key_mv.get(f"{d}|down")})
        rows.append({"id": r["id"], "attributes": attrs, "keys": [k for k, v in key_mv.items() if v], "agreement": key_agree, "conflicts": conflicts})
        mvk = {}
        for k, v in key_mv.items():
            if v:
                d, dirn = k.split("|"); idx = [i for i in range(len(C.ATTRS[(d, dirn)])) if attrs[f"{k}|{i}"]["mv"]]
                mvk[(d, dirn)] = round(max(float(np.mean(attrs[f"{k}|{i}"]["p"])) for i in idx), 3)       # strength = mean probability of its strongest MV attribute
        mv_stories.append({"keys": mvk, "w": st["w"]})
    with open(f"{OUT}/labels.jsonl", "w") as f:
        for x in rows: f.write(json.dumps(x) + "\n")
    occ = [k for k in keys if mv_pos[k] or cur_pos[k]]
    def jac(a, b): return len(a & b) / len(a | b) if a | b else None
    per = {k: {"mv_pos": len(mv_pos[k]), "current_pos": len(cur_pos[k]), "changed": len(mv_pos[k] ^ cur_pos[k]), "unanimous_share": (unanimous[k] / len(mv_pos[k])) if mv_pos[k] else None,
               "jaccard": [jac(yes_w[k][i], yes_w[k][j]) for i, j in ((0, 1), (0, 2), (1, 2))]} for k in keys}
    changed = sum(per[k]["changed"] for k in keys); curtot = sum(per[k]["current_pos"] for k in keys)
    jmed = [float(np.median([x for x in per[k]["jaccard"] if x is not None])) for k in occ if any(x is not None for x in per[k]["jaccard"])]
    # drift of an MV-label replay vs the current engine rule, against Step 1 tolerance (d)
    SN.build(); clean = SN.replay(SN.clean_readings(stories)); mvout = SN.replay([(SN.readings_of(s["keys"]), s["w"]) for s in mv_stories])
    s3 = np.load("/workspace/data/step1/self3.npz"); band = np.load("/workspace/data/step1/noise.npz")["band"]; ws = [s3["w0"], s3["w1"], s3["w2"]]
    told = np.maximum(np.median([np.abs(ws[i] - ws[j]) for i, j in ((0, 1), (0, 2), (1, 2))], axis=0), band)
    rep = {"stories": len(rows), "keys": len(keys), "votes_kept": "3 per attribute, with probabilities", "key_positives_current": curtot, "key_positives_mv": sum(per[k]["mv_pos"] for k in keys),
           "key_labels_changed": changed, "changed_share_of_current_positives": changed / max(1, curtot), "stories_with_conflict": sum(bool(x["conflicts"]) for x in rows),
           "conflicts_total": sum(len(x["conflicts"]) for x in rows), "median_key_jaccard": float(np.median(jmed)), "unanimous_share_median": float(np.median([per[k]["unanimous_share"] for k in occ if per[k]["unanimous_share"] is not None])),
           "mv_replay_ratio_d": float(np.max(np.abs(mvout - clean) / told)), "mv_replay_rel_median": float(np.median(np.abs(mvout - clean) / np.maximum(np.abs(clean), 1e-9))), "per_key": per,
           "seconds": round(time.time() - t0)}
    json.dump(rep, open(f"{OUT}/report.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_key"}, indent=1))
if __name__ == "__main__": main()
