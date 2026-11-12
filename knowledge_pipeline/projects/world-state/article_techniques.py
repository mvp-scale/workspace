"""Technique showcase on the 9 articles of article_topics.json (one article at a time on the page):
 1 keyphrases (KeyBERT / EmbedRank style): noun phrases and named entities from the article, ranked by similarity to the article embedding, diversified with MMR
 2 themes along the article (TextTiling with embeddings): similarity of neighbouring sentence blocks, depth of each dip, boundaries above mean + 0.5 std, at least 3 sentences per segment
 3 opening sentence kept + 3 chosen by coverage within 120 words
 4 support / contradiction (NLI cross-encoder): premise = each sentence, hypothesis = the headline
 plus the existing extractors for the same article (amounts, dates, places, names) read from extract.jsonl.
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python article_techniques.py -> runs/harvest/article_techniques.json"""
import os, re, json, warnings, collections
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np, spacy, torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
A = json.load(open("runs/harvest/article_topics.json"))["articles"]; N = 5000
R = {}; X = {}
for i, l in zip(range(N), open("runs/harvest/sample.jsonl")): R[i] = json.loads(l)
for i, l in zip(range(N), open("runs/harvest/extract.jsonl")): X[i] = json.loads(l)
nlp = spacy.load("en_core_web_sm"); m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
NLI = "cross-encoder/nli-deberta-v3-xsmall"; tok = AutoTokenizer.from_pretrained(NLI); nli = AutoModelForSequenceClassification.from_pretrained(NLI).eval(); LABELS = [nli.config.id2label[i].lower() for i in range(len(nli.config.id2label))]
NLI2 = "cross-encoder/nli-deberta-v3-base"; tok2 = AutoTokenizer.from_pretrained(NLI2); nli2 = AutoModelForSequenceClassification.from_pretrained(NLI2).eval(); LABELS2 = [nli2.config.id2label[i].lower() for i in range(len(nli2.config.id2label))]
def nli_base(prem, hyp):
    b = tok2(prem, [hyp] * len(prem), return_tensors="pt", truncation=True, padding=True, max_length=256)
    with torch.no_grad(): p = torch.softmax(nli2(**b).logits, dim=-1).numpy()
    return [{LABELS2[c]: round(float(q[c]), 3) for c in range(len(LABELS2))} for q in p]
DET = r"^(the|a|an|its|their|his|her|our|your|my|this|that|these|those|some|any|many|more|most|other|such|several|both|each|every|all)\s+"
BAD = set("it he she they we you i who which what that this there here one ones thing things way lot kind part time year years day days week weeks people percent".split())
def unit(v): return v / np.linalg.norm(v)
def count_in(text, phrase): return len(re.findall(r"(?<![A-Za-z])" + re.escape(phrase) + r"(?![A-Za-z])", text, re.I))
def candidates(text):
    d = nlp(text); seen = {}; 
    for c in d.noun_chunks:
        t = re.sub(DET, "", re.sub(r"\s+", " ", c.text.strip()), flags=re.I); t = re.sub(DET, "", t, flags=re.I); w = t.split()
        t = re.sub(r"[’']s$", "", t).strip(" ,.;:-"); w = t.split()
        if "/" in t or re.fullmatch(r"[\d\W]+", t): continue
        if 1 <= len(w) <= 4 and len(t) > 2 and t.lower() not in BAD and not all(x.lower() in BAD for x in w) and re.search(r"[A-Za-z]", t): seen.setdefault(t.lower(), t)
    for e in d.ents:
        if e.label_ in ("PERSON", "ORG", "GPE", "LOC", "EVENT", "NORP", "PRODUCT", "LAW", "FAC", "WORK_OF_ART"):
            t = re.sub(r"\s+", " ", e.text.strip()); 
            if 1 <= len(t.split()) <= 5 and t.lower() not in BAD: seen.setdefault(t.lower(), t)
    return [c for c in seen.values() if count_in(text, c) > 0]  # every candidate is word for word in the article
def mmr(cands, CE, doc, k=8, lam=0.6):
    sim = CE @ doc; chosen = []
    while len(chosen) < min(k, len(cands)):
        best = None; bs = -9
        for j in range(len(cands)):
            if j in chosen: continue
            red = max([float(CE[j] @ CE[c]) for c in chosen], default=0.0); s = lam * float(sim[j]) - (1 - lam) * red
            if s > bs: bs = s; best = j
        chosen.append(best)
    return chosen
def count_in(text, phrase): return len(re.findall(r"(?<![A-Za-z])" + re.escape(phrase) + r"(?![A-Za-z])", text, re.I))
def segment(E, w=3, alpha=0.5, minlen=3):
    n = len(E); sims = []
    for g in range(1, n):
        L = E[max(0, g - w):g].mean(axis=0); Rr = E[g:g + w].mean(axis=0); sims.append(float(unit(L) @ unit(Rr)))
    depth = []
    for k, s in enumerate(sims):
        l = k; 
        while l > 0 and sims[l - 1] >= sims[l]: l -= 1
        r = k
        while r < len(sims) - 1 and sims[r + 1] >= sims[r]: r += 1
        depth.append((sims[l] - s) + (sims[r] - s))
    mu, sd = float(np.mean(depth)), float(np.std(depth)); thr = mu + alpha * sd; cand = sorted([k for k, d in enumerate(depth) if d >= thr and (k == 0 or sims[k] <= sims[k - 1]) and (k == len(sims) - 1 or sims[k] <= sims[k + 1])], key=lambda k: -depth[k]); bounds = []
    for k in cand:
        g = k + 1  # boundary before sentence g
        if g >= minlen and n - g >= minlen and all(abs(g - b) >= minlen for b in bounds): bounds.append(g)
    return sims, depth, thr, sorted(bounds)
def coverage_pick(E, W, first_forced, k=4, budget=120):
    n = len(E); M = np.maximum(np.rint(E @ E.T * 1000).astype(int), 0); cov = lambda S: sum(max([M[i][j] for j in S], default=0) for i in range(n)); S = [0] if first_forced else []
    used = lambda S: sum(W[j] for j in S)
    while len(S) < k:
        cands = [j for j in range(n) if j not in S and used(S) + W[j] <= budget]; best = None
        for j in cands:
            if best is None or cov(S + [best]) - cov(S) < cov(S + [j]) - cov(S): best = j
        if best is None or not cov(S + [best]) - cov(S) > 0: break
        S.append(best)
    return S, cov(S) / (n * 1000)
out = []
for a in A:
    idx = a["idx"]; title = a["title"]; sents = a["sentences"]; n = len(sents); rawbody = R[idx]["text"]; body = " ".join(sents)
    E = enc(sents); W = [len(s.split()) for s in sents]; words = body.split(); chunks = [" ".join(words[b:b + 250]) for b in range(0, len(words), 250)]; doc = unit(enc(chunks).mean(axis=0))
    # 1 keyphrases
    cands = candidates(title + ". " + body); CE = enc(cands); pick = mmr(cands, CE, doc, 8); sent_of = lambda ph: next((i for i, s in enumerate(sents) if re.search(r"(?<![A-Za-z])" + re.escape(ph) + r"(?![A-Za-z])", s, re.I)), None)
    keys = [{"phrase": cands[j], "similarity": round(float(CE[j] @ doc), 3), "times": count_in(title + ". " + body, cands[j]), "first_sentence": (sent_of(cands[j]) + 1) if sent_of(cands[j]) is not None else None, "in_title": bool(re.search(re.escape(cands[j]), title, re.I))} for j in pick]
    # 2 themes along the article
    sims, depth, thr, bounds = segment(E); edges = [0] + bounds + [n]; segs = []
    for s0, s1 in zip(edges[:-1], edges[1:]):
        cen = unit(E[s0:s1].mean(axis=0)); txt = " ".join(sents[s0:s1]); cs = [j for j in range(len(cands)) if count_in(txt, cands[j]) > 0]
        top = []
        if cs: sub = CE[cs]; ch = mmr([cands[j] for j in cs], sub, cen, 3); top = [{"phrase": cands[cs[c]], "times": count_in(txt, cands[cs[c]])} for c in ch]
        segs.append({"first": s0 + 1, "last": s1, "sentences": s1 - s0, "words": sum(W[s0:s1]), "opening_sentence": sents[s0], "phrases": top, "centre": cen.tolist()})
    S2 = [[round(float(np.array(x["centre"]) @ np.array(y["centre"])), 3) for y in segs] for x in segs]
    for s in segs: s.pop("centre")
    # 3 opening + coverage
    hy, hcov = coverage_pick(E, W, True); gy, gcov = coverage_pick(E, W, False)
    # 4 NLI against the headline
    rows = []
    for i in range(0, n, 16):
        b = tok(sents[i:i + 16], [title] * len(sents[i:i + 16]), return_tensors="pt", truncation=True, padding=True, max_length=256)
        with torch.no_grad(): p = torch.softmax(nli(**b).logits, dim=-1).numpy()
        for q in p: rows.append({LABELS[c]: round(float(q[c]), 3) for c in range(len(LABELS))})
    for i, r in enumerate(rows): r["piece"] = i + 1
    tvec = enc([title])[0]; relsim = E @ tvec; order = list(np.argsort(-relsim)); related = [int(j) for j in order[:8]]
    for j, r in enumerate(rows): r["related_to_headline"] = round(float(relsim[j]), 3)
    ent = sorted(rows, key=lambda r: -r["entailment"])[:3]; con = sorted(rows, key=lambda r: -r["contradiction"])[:3]
    base = nli_base([sents[j] for j in related], title)
    rel_rows = [dict(rows[j], text=sents[j], base=base[k]) for k, j in enumerate(related)]
    # existing extractors for the same article
    xr = X[idx]; txt = xr["text"]; names = collections.Counter(e[0] for e in xr["entities"]["items"] if e[1] in ("PERSON", "ORG")); places = collections.Counter((p["text"], p["country"]) for p in xr["places"]["items"])
    ex = {"amounts": xr["facts"]["amounts"], "dates": xr["facts"]["dates"], "places": [{"text": t, "country": c, "times": k} for (t, c), k in places.most_common(8)], "names": [{"text": t, "times": k} for t, k in names.most_common(8)], "years": [txt[s:e] for k_, s, e, v in xr["more_spans"]["items"] if k_ == "year"][:6], "tools": {"facts": xr["facts"]["tool"], "places": xr["places"]["tool"], "entities": xr["entities"]["tool"], "spans": xr["more_spans"]["tool"]}}
    out.append({"idx": idx, "title": title, "domain": a["domain"], "raw": rawbody, "sentences": sents, "words": len(words), "keyphrases": keys, "candidates": len(cands),
                "themes": {"similarity_between_neighbours": [round(s, 3) for s in sims], "depth": [round(d, 3) for d in depth], "threshold": round(thr, 3), "boundaries_before_sentence": [b + 1 for b in bounds], "segments": segs, "segment_similarity": S2},
                "opening_plus_coverage": {"pieces": [p + 1 for p in hy], "coverage": round(hcov, 3), "text": [sents[p] for p in sorted(hy)], "gist_only_pieces": [p + 1 for p in gy], "gist_only_coverage": round(gcov, 3)},
                "nli": {"model": NLI, "model_larger": NLI2, "labels": LABELS, "claim": title, "rows": rows, "top_entail": ent, "top_contradict": con, "most_related_8": rel_rows, "all_sentences_contradiction_over_half": sum(1 for r in rows if r["contradiction"] > 0.5), "all_sentences_entailment_over_half": sum(1 for r in rows if r["entailment"] > 0.5), "related_contradiction_over_half": sum(1 for r in rel_rows if r["contradiction"] > 0.5), "related_entailment_over_half": sum(1 for r in rel_rows if r["entailment"] > 0.5), "base_related_contradiction_over_half": sum(1 for r in rel_rows if r["base"]["contradiction"] > 0.5), "base_related_entailment_over_half": sum(1 for r in rel_rows if r["base"]["entailment"] > 0.5), "agree_label_small_vs_base": sum(1 for r in rel_rows if max(LABELS, key=lambda l: r[l]) == max(LABELS2, key=lambda l: r["base"][l]))}, "extractors": ex})
    print(f"{title[:42]:42} cands {len(cands):4} | keys {[k['phrase'] for k in keys][:4]} | segments {len(segs)} | NLI max entail {ent[0]['entailment']:.2f} (piece {ent[0]['piece']}) max contra {con[0]['contradiction']:.2f} | all: entail>0.5 {sum(1 for r in rows if r['entailment']>0.5)} contra>0.5 {sum(1 for r in rows if r['contradiction']>0.5)} | small: entail {sum(1 for r in rel_rows if r['entailment']>0.5)} contra {sum(1 for r in rel_rows if r['contradiction']>0.5)} neutral {sum(1 for r in rel_rows if r['neutral']>0.5)} | base: entail {sum(1 for r in rel_rows if r['base']['entailment']>0.5)} contra {sum(1 for r in rel_rows if r['base']['contradiction']>0.5)}", flush=True)
json.dump({"v": "article-techniques-v0", "model": "BAAI/bge-small-en-v1.5 (CPU)", "nli_model": NLI, "articles": out}, open("runs/harvest/article_techniques.json", "w"), indent=1)
