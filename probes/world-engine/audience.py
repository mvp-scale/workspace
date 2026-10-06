"""Audience service v0: a classifier-shaped request/response over the current world state and the population.
Request  = {state: <the item>, questions: {id: {type: noul|choice|rank, ...}}, as_of: 'now'}
Response = per question, a typed answer at five levels (world, country, region, segment, person), with the snapshot it was computed from.
Only ONE decision is registered in v0: take-up (would this person take the item up). Other question wordings are not yet separate decisions."""
import sys, json, hashlib, time, email.utils
import numpy as np
import engine as E
import rules as RU
L = "/workspace/probes/world-engine/ledger"; RULES = RU.R        # the active ruleset folder (WE_RULES)
def build_world(seed=0):
    ev = {e["evidence_id"]: e for e in map(json.loads, open(f"{L}/evidence.jsonl"))}; ms = [json.loads(l) for l in open(f"{L}/measurements.jsonl")]; cl = json.load(open(f"{L}/clusters.json")); groups = {}
    for m in ms: groups.setdefault(cl[m["evidence_id"]], []).append(m)
    events = []
    for cid, mem in groups.items():
        use = [m for m in mem if m["gate_ok"]]
        if not use: continue
        best = {}
        for m in use:
            for r in m["readings"]:
                if r["direction"] != "conflict" and (r["dial"] not in best or abs(r["amount"]) > abs(best[r["dial"]]["amount"])): best[r["dial"]] = r
        events.append((email.utils.parsedate_to_datetime(ev[use[0]["evidence_id"]]["published_at"]), cid, use[0]["entry"], len(use), list(best.values())))
    events.sort(key=lambda e: e[0]); w = E.World(seed, True)
    for i, (_, cid, entry, n, rs) in enumerate(events):
        for r in rs: w.add(i, entry, r["dial"], r["amount"], cid)
        w.add(i, "COUNTRY:usa", "news_overload", 0.01 * n, cid)
    w.run(len(events) + 20); return w
LEVELS = {"world": ["COUNTRY:usa"], "country": ["COUNTRY:usa"], "region": [f"REGION:{r}" for r in E.REGIONS], "segment": [f"SEGMENT:{s}" for s in E.SEGMENTS]}   # v0: world and country are roll-ups of the same people
class Service:
    def __init__(self, n=50000, seed=0):
        self.w = build_world(seed); self.pop = E.Population(n); self.aud = E.Audience(); self.eff = self.pop.effective(self.w); self.G = self.pop.groups(); self.n = n; self.seed = seed
        import offline as O
        D = json.load(open("/workspace/data/persona-lab/offline.json")); self.ref_names = list(D["direct"]); self.ref_iv = np.array([[D["idea"][k][q] for q in O.IDEA_Q] for k in self.ref_names])
        self.ref = {k: self.aud.probability(self.pop, self.eff, self.ref_iv[i]) for i, k in enumerate(self.ref_names)}
        d = np.linalg.norm(self.ref_iv[:, None] - self.ref_iv[None], axis=2); np.fill_diagonal(d, 9); self.nn = np.sort(d.min(1))
    def snapshot(self):
        rules = hashlib.sha1(b"".join(open(f"{RULES}/{f}.csv", "rb").read() for f in ("dials", "elements", "grid", "decisions", "decision_weights") + (("dial_ties",) if RU.exists("dial_ties") else ()))).hexdigest()[:10]
        return {"world_tick": self.w.tick, "world_digest": self.w.digest(), "people": self.n, "population_seed": 1, "run_seed": self.seed, "rules_hash": rules, "classifier": "Winnow-12B", "decision_model": f"take-up ridge fitted on {len(self.ref_names)} ideas x 400 people", "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    def level_answer(self, p, refs):
        out = {}
        for lvl, nodes in LEVELS.items():
            vals = {n: float(p[self.G[n]].mean()) for n in nodes}; rv = np.array([[float(r[self.G[n]].mean()) for n in nodes] for r in refs.values()])
            out[lvl] = {"by_node": {n.split(":")[1]: round(v, 4) for n, v in vals.items()}, "worst": round(min(vals.values()), 4), "best": round(max(vals.values()), 4),
                        "percentile_among_known_ideas": round(float((rv.min(1) <= min(vals.values())).mean() * 0 + (rv.mean(1) <= np.mean(list(vals.values()))).mean()), 3)}
        sy = float((p >= .5).mean()); rsy = np.array([float((r >= .5).mean()) for r in refs.values()])
        out["person"] = {"share_yes": round(sy, 4), "p10": round(float(np.quantile(p, .1)), 4), "p90": round(float(np.quantile(p, .9)), 4), "percentile_among_known_ideas": round(float((rsy <= sy).mean()), 3)}
        out["levels_above_typical"] = int(sum(out[l]["percentile_among_known_ideas"] >= 0.5 for l in ("world", "country", "region", "segment", "person"))); return out
    def item(self, text):
        iv = self.aud.demands(text); d = float(np.linalg.norm(self.ref_iv - iv, axis=1).min()); return iv, {"nearest_known_idea_distance": round(d, 3), "typical_distance": round(float(np.median(self.nn)), 3), "extrapolation_flag": bool(d > np.quantile(self.nn, .9))}
    def ask(self, req):
        resp = {"snapshot": self.snapshot(), "answers": {}}; probs = {}
        iv, info = self.item(req["state"]); resp["item"] = {"readings": {k: round(float(v), 3) for k, v in zip(__import__("offline").IDEA_Q, iv)}, **info}; p0 = self.aud.probability(self.pop, self.eff, iv); probs["state"] = p0
        for qid, q in req["questions"].items():
            t = q["type"]
            if t == "noul":
                a = self.level_answer(p0, self.ref); neutral = self.aud.probability(self.pop, self.pop.base, iv)
                a["world_effect"] = {"country_mean_now": round(float(p0.mean()), 4), "country_mean_neutral_world": round(float(neutral.mean()), 4), "difference": round(float(p0.mean() - neutral.mean()), 4)}
                a["type"] = "noul"; a["noul"] = round(float(p0.mean()), 4); resp["answers"][qid] = a
            elif t in ("choice", "rank"):
                names = list(q["options" if t == "choice" else "items"]); P = {}
                for n, text in q["options" if t == "choice" else "items"].items(): ivx, _ = self.item(text); P[n] = self.aud.probability(self.pop, self.eff, ivx)
                if t == "choice":
                    u = np.column_stack([np.log(np.clip(P[n], .01, .99) / (1 - np.clip(P[n], .01, .99))) for n in names] + [np.full(self.n, np.log(.1 / .9))]); pr = np.exp(u - u.max(1, keepdims=True)); pr /= pr.sum(1, keepdims=True)
                    ans = {"type": "choice", "choice": (names + ["none"])[int(pr.mean(0).argmax())], "probabilities": {n: round(float(pr[:, i].mean()), 4) for i, n in enumerate(names + ["none"])}, "by_level": {lvl: {nd.split(':')[1]: {n: round(float(pr[self.G[nd], i].mean()), 3) for i, n in enumerate(names + ['none'])} for nd in nodes} for lvl, nodes in LEVELS.items() if lvl in ("region", "segment")}, "note": "the 'none' option has a fixed placeholder weight"}
                else:
                    order = sorted(names, key=lambda n: -P[n].mean()); per = {lvl: {nd.split(':')[1]: sorted(names, key=lambda n: -float(P[n][self.G[nd]].mean())) for nd in nodes} for lvl, nodes in LEVELS.items() if lvl in ("region", "segment")}
                    wins = {f"{a}>{b}": round(float((P[a] > P[b]).mean()), 3) for i, a in enumerate(order) for b in order[i + 1:]}
                    ans = {"type": "rank", "ranking": order, "mean_take_up": {n: round(float(P[n].mean()), 4) for n in names}, "pairwise_share_preferring": wins, "by_level": per, "same_order_at_every_region_and_segment": all(o == order for lv in per.values() for o in lv.values())}
                resp["answers"][qid] = ans
            else: resp["answers"][qid] = {"error": f"question type {t} not registered in v0"}
        return resp
if __name__ == "__main__":
    import offline as O
    S = Service(50000); req = {"state": O.PRODUCTS["nl_p1a1s1"], "as_of": "now", "questions": {"take_up": {"type": "noul", "instructions": "Would this person take the item up in the next month?"},
        "which_version": {"type": "choice", "options": {"free_sms": O.PRODUCTS["nl_p0a0s0"], "paid_app": O.PRODUCTS["nl_p1a1s1"], "free_app": O.PRODUCTS["nl_p0a1s0"]}},
        "rank_candidates": {"type": "rank", "items": {"nightfall": O.PRODUCTS["nightfall"], "gardenway": O.PRODUCTS["gardenway"], "neighbour_loop_free_sms": O.PRODUCTS["nl_p0a0s0"]}}}}
    t0 = time.time(); r = S.ask(req); r["elapsed_s"] = round(time.time() - t0, 2); json.dump(r, open(f"{L}/audience_example_response.json", "w"), indent=1); print(json.dumps(r, indent=1)[:6500])
