"""Compact views of ONE article, built from the article's own sentences: gist, opening+coverage, keyphrases, theme openers, core triples. Functions only (the same rules as article_techniques.py, gist.py and spo_chains.py).
    import article_views as V; V.views(text, nlp, embed) -> dict of view texts"""
import re, numpy as np
import spo_chains as S
DET = r"^(the|a|an|its|their|his|her|our|your|my|this|that|these|those|some|any|many|more|most|other|such|several|both|each|every|all)\s+"
BAD = set("it he she they we you i who which what that this there here one ones thing things way lot kind part time year years day days week weeks people percent".split())
def split(text):
    cut = [m.end() for m in re.finditer(r"[.!?][\"”’)]?(?=\s+[A-Z0-9“\"‘'(])", text)]; s = []; a = 0
    for e in cut + [len(text)]:
        if text[a:e].strip(): s.append(text[a:e].strip())
        a = e
    out = []
    for x in s:
        if out and len(x.split()) < 6: out[-1] += " " + x
        else: out.append(x)
    return out
unit = lambda v: v / np.linalg.norm(v)
def count_in(text, phrase): return len(re.findall(r"(?<![A-Za-z])" + re.escape(phrase) + r"(?![A-Za-z])", text, re.I))
def candidates(nlp, text):
    d = nlp(text); seen = {}
    for c in d.noun_chunks:
        t = re.sub(DET, "", re.sub(r"\s+", " ", c.text.strip()), flags=re.I); t = re.sub(DET, "", t, flags=re.I); t = re.sub(r"[’']s$", "", t).strip(" ,.;:-"); w = t.split()
        if "/" in t or re.fullmatch(r"[\d\W]+", t): continue
        if 1 <= len(w) <= 4 and len(t) > 2 and t.lower() not in BAD and not all(x.lower() in BAD for x in w) and re.search(r"[A-Za-z]", t): seen.setdefault(t.lower(), t)
    for e in d.ents:
        if e.label_ in ("PERSON", "ORG", "GPE", "LOC", "EVENT", "NORP", "PRODUCT", "LAW", "FAC", "WORK_OF_ART"):
            t = re.sub(r"\s+", " ", e.text.strip())
            if 1 <= len(t.split()) <= 5 and t.lower() not in BAD: seen.setdefault(t.lower(), t)
    return [c for c in seen.values() if count_in(text, c) > 0]
def mmr(CE, doc, k=8, lam=0.6):
    sim = CE @ doc; chosen = []
    while len(chosen) < min(k, len(CE)):
        best = None; bs = -9
        for j in range(len(CE)):
            if j in chosen: continue
            red = max([float(CE[j] @ CE[c]) for c in chosen], default=0.0); s = lam * float(sim[j]) - (1 - lam) * red
            if s > bs: bs = s; best = j
        chosen.append(best)
    return chosen
def segment(E, w=3, alpha=0.5, minlen=3):
    n = len(E); sims = []
    for g in range(1, n):
        L = E[max(0, g - w):g].mean(axis=0); R = E[g:g + w].mean(axis=0); sims.append(float(unit(L) @ unit(R)))
    if len(sims) < 2: return []
    depth = []
    for k, s in enumerate(sims):
        l = k
        while l > 0 and sims[l - 1] >= sims[l]: l -= 1
        r = k
        while r < len(sims) - 1 and sims[r + 1] >= sims[r]: r += 1
        depth.append((sims[l] - s) + (sims[r] - s))
    thr = float(np.mean(depth) + alpha * np.std(depth)); cand = sorted([k for k, d in enumerate(depth) if d >= thr and (k == 0 or sims[k] <= sims[k - 1]) and (k == len(sims) - 1 or sims[k] <= sims[k + 1])], key=lambda k: -depth[k]); bounds = []
    for k in cand:
        g = k + 1
        if g >= minlen and n - g >= minlen and all(abs(g - b) >= minlen for b in bounds): bounds.append(g)
    return sorted(bounds)
def coverage_pick(E, W, forced_first, k=4, budget=120):
    n = len(E); M = np.maximum(np.rint(E @ E.T * 1000).astype(int), 0); cov = lambda S_: sum(max([M[i][j] for j in S_], default=0) for i in range(n)); sel = [0] if forced_first else []; used = lambda S_: sum(W[j] for j in S_)
    while len(sel) < k:
        cands = [j for j in range(n) if j not in sel and used(sel) + W[j] <= budget]; best = None
        for j in cands:
            if best is None or cov(sel + [best]) - cov(sel) < cov(sel + [j]) - cov(sel): best = j
        if best is None or not cov(sel + [best]) - cov(sel) > 0: break
        sel.append(best)
    return sel
def views(text, nlp, embed, max_chars=12000):
    text = re.sub(r"[ \t]+", " ", text)[:max_chars]; sents = split(re.sub(r"\s*\n\s*", " ", text))[:120]
    if len(sents) < 4: return None
    E = embed(sents); W = [len(s.split()) for s in sents]; words = " ".join(sents).split(); chunks = [" ".join(words[a:a + 250]) for a in range(0, len(words), 250)][:8]; doc = unit(embed(chunks).mean(axis=0))
    gist = coverage_pick(E, W, False); opening = coverage_pick(E, W, True)
    cands = candidates(nlp, " ".join(sents)); keys = []
    if cands: CE = embed(cands); keys = [cands[j] for j in mmr(CE, doc, 8)]
    bounds = segment(E); edges = [0] + bounds; openers = [sents[i] for i in edges][:6]
    T = S.extract(nlp, sents[:60]); S.merge_aliases(T); cores = []
    for t in T:
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and not t.get("appositive"): cores.append(f"{t['s']} {'not ' if t['neg'] else ''}{t['p']} {t['o']}.")
        if len(cores) >= 8: break
    return {"gist": " ".join(sents[j] for j in sorted(gist)), "opening_plus_coverage": " ".join(sents[j] for j in sorted(opening)), "keyphrases": "; ".join(keys), "theme_openers": " ".join(openers), "core_triples": " ".join(cores),
            "combined": " ".join([sents[0], "; ".join(keys[:6]) + "."] + [o for o in openers[1:5]])}
