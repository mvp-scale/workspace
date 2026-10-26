"""K1: kNN over labelled training stories with the untrained e5-large encoder, scored slot-level like diag_slot_eval.py. Saves embeddings."""
import os, sys, json, numpy as np, torch
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
from transformers import AutoTokenizer, AutoModel
torch.set_num_threads(16)
W = "/workspace/data"; TUNE = f"{W}/kaggle/mh_r6c1/tune"; B = f"{W}/kaggle/mh_b1b/ds"; ENC = "/root/.cache/huggingface/hub/models--intfloat--e5-large-v2/snapshots/f169b11e22de13617baa190a028a32f3493550b6"
tok = AutoTokenizer.from_pretrained(f"{W}/kaggle/mh_t1lg24/out/mh/encoder"); enc = AutoModel.from_pretrained(ENC).eval()
def embed(texts, bs=64):
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), bs):
            b = tok(["query: " + t for t in texts[i:i + bs]], padding=True, truncation=True, max_length=96, return_tensors="pt"); h = enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float()
            e = (h * m).sum(1) / m.sum(1); out.append(torch.nn.functional.normalize(e, dim=-1).numpy())
    return np.concatenate(out)
cache = f"{W}/diag/knn_emb_2026-10-25.npz"
T = [json.loads(l) for l in open(f"{W}/clef-labels/test.jsonl")]; Zt = np.load(f"{TUNE}/targets.npz"); keep = np.where(Zt["w"] >= 4)[0]; tt = json.load(open(f"{TUNE}/texts.json"))
trtx = json.load(open(f"{B}/texts.json")); Ztr = np.load(f"{B}/targets.npz")
if os.path.exists(cache): E = np.load(cache); Etr, Eta, Ete = E["tr"], E["ta"], E["te"]
else:
    Etr = embed(trtx); Eta = embed([tt[i] for i in keep]); Ete = embed([r["state_text"] for r in T]); np.savez(cache, tr=Etr, ta=Eta, te=Ete)
print("embedded", Etr.shape, Eta.shape, Ete.shape, flush=True)
K = json.load(open(f"{W}/kaggle/mh_t1lg24/out/mh/keys.json"))["cond"]; assert K == json.load(open(f"{B}/keys.json"))["cond"]; A = [k.split("|") for k in K]
Ytr = (Ztr["cond"] > 0.5).astype("float32"); YT = Zt["cond"][keep] >= C.ATTR_MIN
g = {}
for j, (d, dr, i) in enumerate(A): g.setdefault((d, dr), []).append(j)
sl = list(g); YTs = np.stack([YT[:, g[s]].any(1) for s in sl], 1)
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
Bm = np.zeros((len(T), len(sl)), bool)
for n, rr in enumerate(T):
    for k in keys(rr["read"]):
        if k in g: Bm[n, sl.index(k)] = True
def knn(Eq, k, temp):
    sim = Eq @ Etr.T; idx = np.argsort(-sim, 1)[:, :k]; s = np.take_along_axis(sim, idx, 1); w = np.exp((s - s.max(1, keepdims=True)) / temp); w /= w.sum(1, keepdims=True)
    return np.einsum("nk,nkj->nj", w, Ytr[idx])
slot = lambda S: np.stack([S[:, g[s]].max(1) for s in sl], 1)
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def report(name, STs, SSs):
    neg = np.sort(STs[~YTs])[::-1]; out = []
    for fpr in (0.0005, 0.001, 0.002, 0.004):
        c = neg[max(int(fpr * len(neg)), 1) - 1]; P = SSs >= c; out.append(f"{fpr:.2%}: {(P & Bm).sum() / Bm.sum():.1%} fa {(P & ~Bm).sum() / (~Bm).sum():.3%}")
    print(name, "|", " | ".join(out), flush=True)
S = np.load(f"{W}/diag/ens3_2026-10-24_scores.npz"); hT, hS = slot(S["T_Q15"]), slot(S["S_Q15"]); report("Q15 head", hT, hS)
for k, temp in ((10, 0.05), (30, 0.05), (30, 0.02)):
    kT, kS = slot(knn(Eta, k, temp)), slot(knn(Ete, k, temp)); report(f"kNN k={k} t={temp}", kT, kS)
    z = lambda a, ref: (a - ref.mean()) / ref.std()
    report(f"head+kNN k={k} t={temp}", z(hT, hT) + z(lg(kT), lg(kT)), z(hS, hT) + z(lg(kS), lg(kT)))
