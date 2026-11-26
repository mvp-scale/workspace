"""check-developments-ecb: round B (playbook 00.1, ledger prediction T158-B1 = L3018). Scores the developments_v0 grouping against ECB+ document groups (gold = ECB+ sub-topic of the document: topic + ecb / ecbplus from the doc id).
Data: local ECB+ parquet (HF ahmeshaf/ecb_plus_mentions, Apache-2.0); a document = the sentences that carry mentions (about 2 sentences), NOT a full article. Fixture: simulation/fixtures/knowledge/ecbplus-docs.json (written by --make-fixture).
Method: developments_v0._group + _agglo at PARAMS frozen (no edit to developments_v0). The scorer builds the minimal knowledge dict _group needs: title = the lowest-numbered mention sentence, evidence = all mention sentences, entities = surface text of HUM (person) and LOC (place) mentions; published = "" so every gap is 0 and decay = 1.
Baselines: headline-only (same code, no evidence, no entities) at the frozen thr and at its own train-tuned thr; single link on the full similarity. Re-tune: thr chosen on the train split only; gap = test F1 at tuned thr - test F1 at frozen thr.
    /workspace/models/embed-zs/.venv/bin/python simulation/check-developments-ecb.py [--make-fixture <train.parquet> <test.parquet>] [--json]
Bar (L3018): (a) test pooled pairwise F1 of developments_v0 at frozen thr >= headline-only F1 at frozen thr + 0.05; (b) gap <= 0.05. CPU only, no network, no model, no hosted call."""
import os, sys, json, copy, time, collections
os.environ.setdefault("CUDA_VISIBLE_DEVICES", ""); os.environ["WORLD_GPU"] = "0"
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state")
FIX = os.path.join(HERE, "fixtures", "knowledge", "ecbplus-docs.json")
PQ = "/tmp/claude-0/-workspace/3ed8559b-0aa2-49c4-a429-a0452a913be2/scratchpad/ecbplus"
SWEEP = [0.01, 0.02, 0.04, 0.06, 0.08, 0.12, 0.16, 0.24]
args = sys.argv[1:]

def make_fixture(train_pq, test_pq):
    import pyarrow.parquet as pq
    out = {"source": "ECB+ train and test splits, HF ahmeshaf/ecb_plus_mentions parquet; one document = its mention sentences; gold = sub-topic (topic + ecb|ecbplus) from the doc id", "license": "ECB+ via HF ahmeshaf/ecb_plus_mentions, Apache-2.0", "docs": []}
    for split, path in (("train", train_pq), ("test", test_pq)):
        docs = collections.OrderedDict()
        for r in pq.read_table(path).to_pylist():
            d = docs.setdefault(r["doc_id"], {"id": r["doc_id"], "split": split, "topic": r["doc_id"].split("_")[0], "sub": r["doc_id"].split("_")[0] + ("-plus" if "ecbplus" in r["doc_id"] else "-ecb"), "sents": {}, "ents": []})
            d["sents"][int(r["sentence_id"])] = r["sentence"]
            if r["men_type"] == "ent" and r["mention_text"]:
                pre = (r["gold_cluster"] or "")[:3]
                if pre in ("HUM", "LOC"): d["ents"].append(("person:" if pre == "HUM" else "place:") + r["mention_text"].lower())
        for d in docs.values():
            ks = sorted(d["sents"]); d["title"] = d["sents"][ks[0]]; d["sentences"] = [d["sents"][k] for k in ks]; del d["sents"]; d["ents"] = sorted(set(d["ents"])); out["docs"].append(d)
    json.dump(out, open(FIX, "w"), ensure_ascii=False); print("wrote", FIX, len(out["docs"]), "docs")

if "--make-fixture" in args:
    i = args.index("--make-fixture"); make_fixture(args[i + 1], args[i + 2]); sys.exit(0)
if not os.path.exists(FIX): make_fixture(PQ + "/train.parquet", PQ + "/test.parquet")
sys.path.insert(0, WS); os.chdir(WS)
import developments_v0 as DV
F = json.load(open(FIX)); T0 = time.time()

def window(docs, with_evidence):
    arts = [{"id": d["id"], "i": i, "title": d["title"], "published": ""} for i, d in enumerate(docs)]
    edges = {}
    if with_evidence:
        for d in docs:
            edges["s|" + d["id"]] = {"subject": None, "object": None, "fragments": [{"art": d["id"], "sent": s} for s in d["sentences"]]}
            for k, e in enumerate(d["ents"]): edges["e%d|%s" % (k, d["id"])] = {"subject": e, "object": None, "fragments": [{"art": d["id"], "sent": ""}]}
    return {"K": {"edges": edges}}, arts

def sim_matrix(docs, with_evidence):
    """the similarity matrix developments_v0._group builds (captured from its _agglo call; thr is irrelevant to it)"""
    D, arts = window(docs, with_evidence); cap = {}; orig = DV._agglo
    def spy(n, S, thr): cap["S"] = S; return orig(n, S, thr)
    DV._agglo = spy
    try: DV._group(D, arts, dict(DV.PARAMS))
    finally: DV._agglo = orig
    return cap["S"]

def avg(S, thr): return DV._agglo(len(S), S, thr)
def single(S, thr):
    n = len(S); par = list(range(n))
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for i in range(n):
        for j in range(i):
            if S[i][j] >= thr: par[f(i)] = f(j)
    g = collections.defaultdict(list)
    for i in range(n): g[f(i)].append(i)
    return sorted(g.values())

def prf(groups, docs, within=False):
    lab = {}
    for c, g in enumerate(groups):
        for i in g: lab[i] = c
    tp = fp = fn = 0
    for i in range(len(docs)):
        for j in range(i):
            if within and docs[i]["topic"] != docs[j]["topic"]: continue
            p = lab[i] == lab[j]; t = docs[i]["sub"] == docs[j]["sub"]
            tp += p and t; fp += p and not t; fn += (not p) and t
    P = tp / (tp + fp) if tp + fp else 0.0; R = tp / (tp + fn) if tp + fn else 0.0
    return {"p": round(P, 4), "r": round(R, 4), "f1": round(2 * P * R / (P + R), 4) if P + R else 0.0}
def purity(groups, docs): return round(sum(max(collections.Counter(docs[i]["sub"] for i in g).values()) for g in groups) / len(docs), 4)

R = {"split": {}}; split = {s: [d for d in F["docs"] if d["split"] == s] for s in ("train", "test")}
for s, d in split.items(): R["split"][s] = {"docs": len(d), "topics": len({x["topic"] for x in d}), "subtopics": len({x["sub"] for x in d})}
S = {(s, w): sim_matrix(split[s], w) for s in split for w in (True, False)}
print("similarity matrices built %.0f s" % (time.time() - T0), flush=True)
def score(s, w, thr, link=avg):
    g = link(S[(s, w)], thr); d = split[s]; return {"clusters": len(g), "pooled": prf(g, d), "within_topic": prf(g, d, True), "purity": purity(g, d)}
FZ = DV.PARAMS["thr"]
R["frozen_thr"] = FZ
R["test_developments_frozen"] = score("test", True, FZ); R["test_headline_frozen"] = score("test", False, FZ); R["test_single_link_frozen"] = score("test", True, FZ, single)
sw = {}
for w in (True, False):
    sw[w] = {thr: score("train", w, thr)["pooled"]["f1"] for thr in SWEEP}
    print("train sweep %s: %s %.0f s" % ("developments" if w else "headline", sw[w], time.time() - T0), flush=True)
best = {w: max(SWEEP, key=lambda t: (sw[w][t], -t)) for w in sw}
R["train_sweep"] = {("developments" if w else "headline"): sw[w] for w in sw}; R["tuned_thr"] = {("developments" if w else "headline"): best[w] for w in sw}
R["test_developments_tuned"] = score("test", True, best[True]); R["test_headline_tuned"] = score("test", False, best[False])
f = lambda k, m="pooled": R[k][m]["f1"]
diff = round(f("test_developments_frozen") - f("test_headline_frozen"), 4); gap = round(f("test_developments_tuned") - f("test_developments_frozen"), 4)
R["bar"] = {"a_diff_vs_headline_at_frozen_thr": diff, "a_pass": diff >= 0.05, "b_gap": gap, "b_pass": abs(gap) <= 0.05, "within_topic_diff": round(f("test_developments_frozen", "within_topic") - f("test_headline_frozen", "within_topic"), 4), "seconds": round(time.time() - T0)}
if "--json" in args: print(json.dumps(R, indent=1))
else:
    for k in ("split", "test_developments_frozen", "test_headline_frozen", "test_single_link_frozen", "test_developments_tuned", "test_headline_tuned", "tuned_thr", "bar"): print(k, json.dumps(R[k]))
    print("%s (a) frozen-thr F1 difference %+0.4f (bar >= +0.05); %s (b) gap %+0.4f (bar |gap| <= 0.05)" % ("PASS" if R["bar"]["a_pass"] else "FAIL", diff, "PASS" if R["bar"]["b_pass"] else "FAIL", gap))
sys.exit(0 if R["bar"]["a_pass"] and R["bar"]["b_pass"] else 1)
