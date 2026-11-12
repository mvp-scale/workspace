"""T104: Area head trained on pseudo-labels that independent publishers agree on (plan L1807). Label of an article = the depth-1 Area most of its supported triples were assigned to (T99-A assignments), kept when it holds MINTRI or more supported triples and at least AGREE of them agree. The head reads headline plus description (bge-small vector) and the reader's topic one-hot, as in T84; the labelling teacher saw the triple sentences of several publishers, the student sees one headline. Scored once on the MN-DS human level-2 labels (fresh, fresh2), paired against the embedding mapping with the same reader constraint (alias fixed). MN-DS is scoring only. Learning curve at the sizes in SIZES (labelled articles used for fitting).
    PILOT=<n> uses n articles in total (a slice for the forecast).  T73DIR=<folder> SIZES=5000,15000,0 /workspace/models/embed-zs/.venv/bin/python -u t104_area_head.py -> <folder>/t104_area_head.json  (SIZES 0 = all)"""
import os, sys, json, random, time, collections
os.environ.setdefault("MODEL", "BAAI/bge-small-en-v1.5"); os.environ.setdefault("TERM", "def"); os.environ.setdefault("NP", "0")
exec(open("t81_arm.py").read().split("h2 = [G")[0])
h2 = [G[i]["l2"].lower() for i in ids]; inv = np.array([x in set(D1) for x in h2]); tag = np.array([src[i] for i in ids]); T0 = time.time()
PILOT = int(os.environ.get("PILOT", 0)); MINTRI = int(os.environ.get("MINTRI", 3)); AGREE = float(os.environ.get("AGREE", 0.6)); SIZES = [int(x) for x in os.environ.get("SIZES", "5000,15000,0").split(",")]
S99 = "runs/pulse/t99"; SUP = json.load(open(S99 + "/t76_supported_triples.json")); AS = json.load(open(S99 + "/t79_assign.json")); d1 = [x.lower() for x in AS["depth1_label"]]; asg = AS["assign_constrained"]
per = collections.defaultdict(list)
for s, a in zip(SUP, asg): per[s["article"]].append(d1[a])
nmi = {n: i for i, n in enumerate(names)}; lab_art = {}; seen_total = 0
for u, v in per.items():
    c = collections.Counter(v).most_common(1)[0]; seen_total += 1
    if len(v) >= MINTRI and c[1] / len(v) >= AGREE and c[0] in nmi: lab_art[u] = nmi[c[0]]
txt_pool = {}
for k, l in enumerate(open("runs/pulse/t98/queue.jsonl")):
    if k in lab_art: txt_pool[k] = json.loads(l)["text"]
pid = sorted(u for u in lab_art if u in txt_pool); random.Random(20261111).shuffle(pid)
if PILOT: pid = pid[:PILOT]
print("articles with supported triples", seen_total, "labelled", len(lab_art), "used", len(pid), "elapsed", round(time.time() - T0), flush=True)
TOP = sorted(M); ti = {t: i for i, t in enumerate(TOP)}
P = m.encode([pre_q + txt_pool[u] for u in pid], batch_size=64, normalize_embeddings=True, convert_to_numpy=True); print("pool encoded", round(time.time() - T0), flush=True)
topic = [(lambda r: r["answer"][0] if r["answer"] else None)(e.read(txt_pool[u])["topic_top2"]) for u in pid]
def feats(Xv, tops):
    oh = np.zeros((len(Xv), len(TOP)), dtype=np.float32)
    for r, t in enumerate(tops):
        if t in ti: oh[r, ti[t]] = 1
    return torch.tensor(np.hstack([Xv, oh]), dtype=torch.float32)
Xp = feats(P, topic); yp = torch.tensor([lab_art[u] for u in pid]); nd = int(0.1 * len(pid)); dev = np.arange(nd); fit_all = np.arange(nd, len(pid))
Xm = feats(m.encode([pre_q + txt[i] for i in ids], batch_size=32, normalize_embeddings=True, convert_to_numpy=True), [(lambda r: r["answer"][0] if r["answer"] else None)(e.read(txt[i])["topic_top2"]) for i in ids])
def train(fit):
    torch.manual_seed(7); net = torch.nn.Sequential(torch.nn.Linear(Xp.shape[1], 512), torch.nn.ReLU(), torch.nn.Dropout(0.2), torch.nn.Linear(512, len(names))); opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-2)
    curve = []; best = (-1, None, 0); bad = 0
    for ep in range(1, 41):
        net.train(); perm = np.random.RandomState(ep).permutation(fit)
        for b in range(0, len(perm), 128):
            ix = perm[b:b + 128]; opt.zero_grad(); torch.nn.functional.cross_entropy(net(Xp[ix]), yp[ix]).backward(); opt.step()
        net.eval()
        with torch.no_grad(): da = float((net(Xp[dev]).argmax(1) == yp[dev]).float().mean())
        curve.append({"epoch": ep, "dev": round(da, 4)})
        if da > best[0] + 0.002: best = (da, {k: v.clone() for k, v in net.state_dict().items()}, ep); bad = 0
        else:
            bad += 1
            if bad >= 3: break
    net.load_state_dict(best[1]); net.eval(); return net, best, curve
out = {"articles_with_supported_triples": seen_total, "labelled": len(lab_art), "used": len(pid), "min_triples": MINTRI, "agree": AGREE, "dev_articles": int(nd), "sizes": {}}
for sz in SIZES:
    fit = fit_all if (sz == 0 or sz >= len(fit_all)) else fit_all[:sz]; net, best, curve = train(fit)
    with torch.no_grad(): HS = net(Xm).numpy()
    HSc = np.where(ASc < -5, -9, HS); r = {"fit": int(len(fit)), "best_epoch": best[2], "dev_agreement": round(best[0], 4), "seconds": round(time.time() - T0)}
    for t in ("fresh", "fresh2"):
        sel = np.where((tag == t) & inv)[0]; hit = lambda S_: np.array([int(names[int(np.argmax(S_[k]))] == h2[k]) for k in sel])
        hh, he, hc = hit(HS), hit(ASc), hit(HSc); rs = np.random.RandomState(0); bs = sorted(float((hh - he)[rs.randint(0, len(sel), len(sel))].mean()) for _ in range(3000)); bc = sorted(float((hc - he)[rs.randint(0, len(sel), len(sel))].mean()) for _ in range(3000))
        r[t] = {"items": int(len(sel)), "head": round(float(hh.mean()), 4), "head_limited_to_domain": round(float(hc.mean()), 4), "embedding": round(float(he.mean()), 4), "paired_head_minus_embedding": round(float((hh - he).mean()), 4), "ci95": [round(bs[75], 4), round(bs[2924], 4)], "paired_limited_minus_embedding": round(float((hc - he).mean()), 4), "ci95_limited": [round(bc[75], 4), round(bc[2924], 4)]}
    out["sizes"][str(sz)] = r; print("size", sz, json.dumps(r), flush=True)
out["fresh2_embedding"] = out["sizes"][str(SIZES[-1])]["fresh2"]["embedding"]; out["fresh2_head_limited_largest"] = out["sizes"][str(SIZES[-1])]["fresh2"]["head_limited_to_domain"]; out["fresh2_paired_limited_minus_embedding_largest"] = out["sizes"][str(SIZES[-1])]["fresh2"]["paired_limited_minus_embedding"]
json.dump(out, open(OUT + "/t104_area_head.json", "w"), indent=1)
