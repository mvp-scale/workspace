"""Agreement view (owner request 2026-11-05): how certainty grows as independent views agree, and what is left for a bigger model.
Views per (story, condition kind) on the test half of the grouped split used in g3_spec.py: cue rule (G1-style keyword evidence), sparse G3a (set B, calibrated, F1 threshold), encoder G3b (same recipe). Truth for scoring is Sonnet agreement, not outside truth.
Also per article: the same views plus Clef's own reading. Writes demo/mockups/gates/data.json -> agreement.
    /workspace/models/embed-zs/.venv/bin/python agreement.py   (from projects/world-state)"""
import json, re, time, numpy as np, scipy.sparse as sp, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupShuffleSplit
from joblib import Parallel, delayed
import importlib.util, ast
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
src = open("kind_cascade.py").read(); a = src.index("RULES = {"); b = src.index("KINDS = list(RULES)"); ns = {}; exec(src[a:b], {"re": re, "json": json}, ns); RULES = ns["RULES"]
DATA = "/workspace/demo/mockups/gates/data.json"; D = json.load(open(DATA)); KINDS = [l["kind"] for l in D["ladder"]]
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = r
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]; E1 = np.load("runs/pulse/kind_cascade_emb.npz")["E1"]
Y = np.array([[int(k in S[i]["kinds"]) for k in KINDS] for i in ids])
grp = {}; gid = np.array([grp.setdefault(re.sub(r"\W+", "", t.lower())[:60], len(grp)) for t in T])
tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=0).split(T, groups=gid)); rs = np.random.RandomState(1); va = rs.permutation(va); cal, te = va[: len(va) // 2], va[len(va) // 2:]
hw = HashingVectorizer(analyzer="word", ngram_range=(1, 2), n_features=2 ** 19, alternate_sign=False, norm=None); hc = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=2 ** 19, alternate_sign=False, norm=None)
H = sp.hstack([hw.transform(T), hc.transform(T)]).tocsr(); tfB = TfidfTransformer(sublinear_tf=True).fit(H[tr]); XB = tfB.transform(H).tocsr()
def f1_at(p, y, t): pr = p >= t; return 2 * int((pr & (y == 1)).sum()) / max(int(pr.sum()) + int(y.sum()), 1)
def fit(M, j, ker):
    m = LogisticRegression(solver="liblinear", C=10.0 if ker == "s" else 3.0, class_weight="balanced").fit(M[tr], Y[tr, j]); pc = m.predict_proba(M[cal])[:, 1]; iso = IsotonicRegression(out_of_bounds="clip").fit(pc, Y[cal, j]); cc = iso.predict(pc)
    cands = np.unique(np.quantile(cc, np.linspace(0.5, 0.999, 60))); tf1 = max(cands, key=lambda t: f1_at(cc, Y[cal, j], t)) if len(cands) else 0.5
    return m, iso, float(tf1), iso.predict(m.predict_proba(M[te])[:, 1])
SPm = Parallel(n_jobs=16)(delayed(fit)(XB, j, "s") for j in range(len(KINDS))); ENm = Parallel(n_jobs=16)(delayed(fit)(E1, j, "e") for j in range(len(KINDS))); print("fitted", flush=True)
votes = np.zeros((len(te), len(KINDS), 3), bool)
for j, k in enumerate(KINDS):
    rx = re.compile(RULES[k], re.I); votes[:, j, 0] = [bool(rx.search(T[i])) for i in te]; votes[:, j, 1] = SPm[j][3] >= SPm[j][2]; votes[:, j, 2] = ENm[j][3] >= ENm[j][2]
y = Y[te]; n = votes.sum(2); tot_pos = int(y.sum()); lad = []
for k_ in range(4):
    m = n == k_; lad.append({"views_agreeing": k_, "pairs": int(m.sum()), "positives": int(y[m].sum()), "precision": round(float(y[m].mean()), 3) if m.sum() else None, "share_of_all_positives": round(float(y[m].sum() / tot_pos), 3)})
pair = {"rule_and_sparse": (votes[..., 0] & votes[..., 1]), "sparse_and_encoder": (votes[..., 1] & votes[..., 2]), "rule_and_encoder": (votes[..., 0] & votes[..., 2])}
pairs = {k: {"pairs": int(v.sum()), "precision": round(float(y[v].mean()), 3) if v.sum() else None} for k, v in pair.items()}
single = {nm: {"fires": int(votes[..., i].sum()), "precision": round(float(y[votes[..., i]].mean()), 3) if votes[..., i].sum() else None, "share_of_positives_caught": round(float(y[votes[..., i]].sum() / tot_pos), 3)} for i, nm in enumerate(["cue_rule", "sparse_G3a", "encoder_G3b"])}
anyv = n >= 1; head = {"positives_total": tot_pos, "caught_by_any_cheap_view": round(float(y[anyv].sum() / tot_pos), 3), "caught_by_no_cheap_view": round(float(y[~anyv].sum() / tot_pos), 3), "caught_by_all_three": round(float(y[n == 3].sum() / tot_pos), 3)}
D["agreement"] = {"views": ["cue rule (G1 keyword evidence)", "sparse (G3a)", "encoder (G3b)"], "truth": "Sonnet agreement, not outside truth", "test_pairs": int(y.size), "ladder": lad, "pairs": pairs, "single": single, "headroom": head}
print(json.dumps(D["agreement"], indent=1)[:1800], flush=True)
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding(); so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t): e = tk.encode(re.sub(r"\s+", " ", t)[:1200]); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
for art in D["articles"]:
    c = art["contract"]; view = re.sub(r"\s+", " ", c["title"] + ". " + c["body"])[:600]; xb = tfB.transform(sp.hstack([hw.transform([view]), hc.transform([view])]).tocsr()); e = emb(view)[None]; clef = {d.split()[0]: d.split()[1] for d in art["clef_dials"]}; rows = []
    for j, k in enumerate(KINDS):
        rule = bool(re.search(RULES[k], view, re.I)); ps = float(SPm[j][1].predict([SPm[j][0].predict_proba(xb)[0, 1]])[0]); pe = float(ENm[j][1].predict([ENm[j][0].predict_proba(e)[0, 1]])[0])
        row = {"kind": k, "cue_rule": rule, "sparse_p": round(ps, 3), "sparse_yes": ps >= SPm[j][2], "encoder_p": round(pe, 3), "encoder_yes": pe >= ENm[j][2], "clef": clef.get(k)}
        row["cheap_votes"] = int(rule) + int(row["sparse_yes"]) + int(row["encoder_yes"])
        if row["cheap_votes"] or row["clef"]: rows.append(row)
    art["agreement_rows"] = sorted(rows, key=lambda r: -(r["cheap_votes"] + (1 if r["clef"] else 0)))
    print(art["id"], [(r["kind"], r["cheap_votes"], r["clef"]) for r in art["agreement_rows"]], flush=True)
json.dump(D, open(DATA, "w")); print("saved", flush=True)
