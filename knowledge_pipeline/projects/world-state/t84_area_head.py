"""T84: Area v1 candidate. A small head on frozen bge-small vectors, distilled from the IPTC depth-1 term mapping (T81 setup), trained on the Sonnet-labelled pool, scored once on MN-DS human level-2 labels (fresh, fresh2).
Pseudo-label of a pool item = best depth-1 term by cosine, limited to the top-level categories of its Sonnet topic (topic_to_iptc_v1); only the more confident half is used. Input = vector + one-hot topic. At test the topic is the live reader's (v6b-student) top answer.
Dev = 15% of the pool, early stop on dev agreement with the pseudo-labels (patience 3). Prediction at ledger L1595/L1598.
    SMOKE=1 -> 3000 pool items, 5 epochs.  T73DIR=<folder> /workspace/models/embed-zs/.venv/bin/python -u t84_area_head.py -> <folder>/t84_area_head.json"""
import os, sys, json, random, time, collections
os.environ.setdefault("MODEL", "BAAI/bge-small-en-v1.5"); os.environ.setdefault("TERM", "def"); os.environ.setdefault("NP", "0")
exec(open("t81_arm.py").read().split("h2 = [G")[0])   # O, names, ids (MN-DS), txt, src, G, m, ASc, cats, e, M ...
h2 = [G[i]["l2"].lower() for i in ids]; inv = np.array([x in set(D1) for x in h2]); tag = np.array([src[i] for i in ids]); T0 = time.time(); SMOKE = bool(os.environ.get("SMOKE"))
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
ptxt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; ptxt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")}); sealed = {r["item_id"] for r in J("runs/pulse/sealed/labels.jsonl")}
topic = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["item_id"] in ptxt and r["item_id"] not in sealed and r.get("topic") in M and r["item_id"] not in topic: topic[r["item_id"]] = r["topic"]
pid = sorted(topic); random.Random(20261110).shuffle(pid); pid = pid[:3000] if SMOKE else pid
TOP = sorted(M); ti = {t: i for i, t in enumerate(TOP)}; print("pool items", len(pid), "elapsed", round(time.time() - T0), flush=True)
cache = OUT + f"/pool_emb_{len(pid)}.npy"; os.makedirs(OUT, exist_ok=True)
P = np.load(cache) if os.path.exists(cache) else m.encode([pre_q + ptxt[i] for i in pid], batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
if not os.path.exists(cache): np.save(cache, P)
print("pool encoded", round(time.time() - T0), flush=True)
S = P @ T.T; PA = np.stack([S[:, anc_idx[n]].max(1) for n in names], 1)
for k, i in enumerate(pid):
    cs = {c.lower() for c in M[topic[i]]}
    for a, n in enumerate(names):
        if top_of[n] not in cs: PA[k, a] = -9
srt = np.sort(PA, 1); margin = srt[:, -1] - srt[:, -2]; keep = margin >= np.median(margin); y = PA.argmax(1)
def feats(Xv, tops):
    oh = np.zeros((len(Xv), len(TOP)), dtype=np.float32)
    for r, t in enumerate(tops):
        if t in ti: oh[r, ti[t]] = 1
    return torch.tensor(np.hstack([Xv, oh]), dtype=torch.float32)
Xp = feats(P, [topic[i] for i in pid]); yp = torch.tensor(y); nd = int(0.15 * len(pid)); dev = np.arange(nd); fit = np.arange(nd, len(pid)); fit = fit[keep[fit]]; dk = dev[keep[dev]]
torch.manual_seed(7); net = torch.nn.Sequential(torch.nn.Linear(Xp.shape[1], 512), torch.nn.ReLU(), torch.nn.Dropout(0.2), torch.nn.Linear(512, len(names))); opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-2)
curve = []; best = (-1, None, 0); bad = 0; EP = 5 if SMOKE else 40
for ep in range(1, EP + 1):
    net.train(); perm = np.random.RandomState(ep).permutation(fit)
    for b in range(0, len(perm), 128):
        ix = perm[b:b + 128]; opt.zero_grad(); torch.nn.functional.cross_entropy(net(Xp[ix]), yp[ix]).backward(); opt.step()
    net.eval()
    with torch.no_grad(): da = float((net(Xp[dk]).argmax(1) == yp[dk]).float().mean())
    curve.append({"epoch": ep, "dev": round(da, 4)}); print("epoch", ep, "dev", round(da, 4), flush=True)
    if da > best[0] + 0.002: best = (da, {k: v.clone() for k, v in net.state_dict().items()}, ep); bad = 0
    else:
        bad += 1
        if bad >= 3: break
net.load_state_dict(best[1]); net.eval()
tops = [(lambda r: r["answer"][0] if r["answer"] else None)(e.read(txt[i])["topic_top2"]) for i in ids]
with torch.no_grad(): HS = net(feats(m.encode([pre_q + txt[i] for i in ids], batch_size=32, normalize_embeddings=True, convert_to_numpy=True), tops)).numpy()
HSc = np.where(ASc < -5, -9, HS)   # same domain limit the embedding gets
out = {"topic_in_vocab": round(float(np.mean([t in ti for t in tops])), 4), "pool_items": len(pid), "trained_on": int(len(fit)), "best_epoch": best[2], "stop": "early stop" if bad >= 3 else "planned epochs finished", "curve": curve, "seconds": round(time.time() - T0, 1)}
for t in ("fresh", "fresh2"):
    sel = np.where((tag == t) & inv)[0]; hit = lambda S_: np.array([int(names[int(np.argmax(S_[k]))] == h2[k]) for k in sel])
    hh, he, hc = hit(HS), hit(ASc), hit(HSc); rs = np.random.RandomState(0); bs = sorted(float((hh - he)[rs.randint(0, len(sel), len(sel))].mean()) for _ in range(3000))
    out[t] = {"items": int(len(sel)), "head": round(float(hh.mean()), 4), "head_limited_to_domain": round(float(hc.mean()), 4), "paired_limited_minus_embedding": round(float((hc - he).mean()), 4), "embedding": round(float(he.mean()), 4), "paired_head_minus_embedding": round(float((hh - he).mean()), 4), "ci95": [round(bs[75], 4), round(bs[2924], 4)]}
np.savez(OUT + "/t84_scores.npz", HS=HS, ASc=ASc, inv=inv, tag=tag, h2=np.array(h2), sim_max=np.array([S_.max() for S_ in (m.encode([pre_q + txt[i] for i in ids], batch_size=32, normalize_embeddings=True, convert_to_numpy=True) @ T.T)]))   # scores for T85 novelty
json.dump(out, open(OUT + ("/t84_smoke.json" if SMOKE else "/t84_area_head.json"), "w"), indent=1); print(json.dumps(out, indent=1))
