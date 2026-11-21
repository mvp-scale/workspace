"""pack_view: what the simulation bench shows in section 8, for any article.
(1) IPTC + WordNet placement of the article's words (structure_pack), filtered by the pipeline's own Domain answer; (2) the WordNet family of words that sit in no claim (synonyms, parents, related forms, what a verb entails or causes).
Add-only, CPU, provenance Inferred. Used by simulation/server.py run_article under the key 'pack'."""
import collections, re
WORD = re.compile(r"[a-z]+")
from structure_pack import Pack, SRC
STOP = set("that with this from have after over will says about into they their what when been more than were your could would also just amid under between while there which these those other some many much such very than then them being doing made make said say new one two".split())
def l1_code(name):
    """Pipeline Domain name -> IPTC top-level code, through the versioned table (mnds_codes; covers the two IPTC renames)."""
    from mnds_codes import table
    return table()["l1"].get((name or "").lower())
class Family:
    def __init__(self):
        d = SRC + "/wordnet/wordnet/"; self.syn = {}; self.lem = {}; self.gloss = {}; self._dep = {}
        for pos, fn in (("n", "noun"), ("v", "verb")):
            for l in open(d + "data." + fn):
                if l.startswith(" "): continue
                h, gl = l.split("|", 1); f = h.split(); wc = int(f[3], 16); self.gloss[(pos, f[0])] = {w for w in WORD.findall(gl.lower()) if len(w) > 3 and w not in STOP}
                words = [f[4 + 2 * i].lower().replace("_", " ") for i in range(wc)]; pc = int(f[4 + 2 * wc]); ptr = f[5 + 2 * wc:]; ps = collections.defaultdict(list)
                for i in range(pc):
                    sym, off, p, st = ptr[4 * i:4 * i + 4]; ps[sym].append((off, p, st))
                self.syn[(pos, f[0])] = (words, ps)
            for l in open(d + "index." + fn):
                if l.startswith(" "): continue
                f = l.split(); self.lem[(pos, f[0].replace("_", " "))] = f[6 + int(f[3]):]
    def _w(self, pos, off, st=None):
        s = self.syn.get((pos, off))
        if not s: return None
        i = int(st[2:], 16) if st and len(st) == 4 and st[2:] != "00" else 0
        return s[0][i - 1] if 0 < i <= len(s[0]) else s[0][0]
    def of(self, word, pos):
        offs = self.lem.get((pos, word))
        if not offs: return None
        words, ps = self.syn[(pos, offs[0])]; out = {"word": word, "pos": "noun" if pos == "n" else "verb"}
        out["synonyms"] = [w for w in words if w != word][:4]
        par = []; cur = (pos, offs[0])
        for _ in range(3):
            nxt = self.syn[cur][1].get("@") or self.syn[cur][1].get("@i")
            if not nxt: break
            par.append(self._w(nxt[0][1], nxt[0][0])); cur = (nxt[0][1], nxt[0][0])
        out["parents"] = [p for p in par if p]
        out["related_forms"] = [x for x in (self._w(p, o, st) for o, p, st in ps.get("+", [])[:4]) if x and x != word]
        out["entails"] = [x for x in (self._w(p, o) for o, p, st in ps.get("*", [])[:3]) if x]
        out["causes"] = [x for x in (self._w(p, o) for o, p, st in ps.get(">", [])[:3]) if x]
        return out if any(out[k] for k in ("synonyms", "parents", "related_forms", "entails", "causes")) else None
    def senses(self, word, pos, n=3):
        """First n senses: synonyms, siblings (same parent), parents (3 steps up) and topic domain (';c', direct or from a parent up to 3 steps)."""
        out = []
        for k, off in enumerate((self.lem.get((pos, word)) or [])[:n]):
            words, ps = self.syn[(pos, off)]; par = []; cur = (pos, off); dom = None
            up1 = ps.get("@") or ps.get("@i") or []
            sib = []
            if up1:
                for o, p, st in self.syn[(up1[0][1], up1[0][0])][1].get("~", [])[:12]:
                    w = self._w(p, o)
                    if w and w != word and w not in words: sib.append(w)
            for d in range(4):
                if dom is None and self.syn[cur][1].get(";c"): o, p, st = self.syn[cur][1][";c"][0]; dom = (self._w(p, o), d)
                nxt = self.syn[cur][1].get("@") or self.syn[cur][1].get("@i")
                if not nxt or d == 3: break
                cur = (nxt[0][1], nxt[0][0]); par.append(self._w(*cur[::-1]) if False else self.syn[cur][0][0])
            out.append({"sense": k + 1, "synonyms": [w for w in words if w != word][:4], "siblings": sib[:4], "parents": par, "domain": dom[0] if dom else None, "domain_steps_up": dom[1] if dom else None})
        return out
    def depth(self, key):
        """Steps from this meaning to the top of WordNet (entity) on the shortest parent path."""
        if key not in self._dep:
            self._dep[key] = 0; up = (self.syn[key][1].get("@") or []) + (self.syn[key][1].get("@i") or [])
            self._dep[key] = 1 + min(self.depth((p, o)) for o, p, st in up) if up else 0
        return self._dep[key]
    def choose(self, word, pos, ctx, n=8):
        """Meaning chosen by definition overlap with the article's words (gloss + synonyms + parent words); switches from the first (most common) meaning only when it overlaps by 1 more word."""
        offs = (self.lem.get((pos, word)) or [])[:n]
        if not offs: return None, 0
        def sc(off):
            k = (pos, off); bag = set(self.gloss[k]) | set(self.syn[k][0])
            for o, p, st in (self.syn[k][1].get("@") or [])[:2]: bag |= self.gloss[(p, o)] | set(self.syn[(p, o)][0])
            bag.discard(word); return len(bag & ctx)
        s = [sc(o) for o in offs]; i = max(range(len(offs)), key=lambda j: (s[j], -j))
        if s[i] < s[0] + 1: i = 0
        return (pos, offs[i]), i + 1
    def ups(self, key, k=4, min_depth=5):
        """Parents up to k steps (all parent links), kept only when the parent sits at least min_depth steps below the top, so 'entity', 'act', 'object' never form a group."""
        out = {}; fr = [(key, 0)]
        while fr:
            c, d = fr.pop(0)
            if d and c not in out and self.depth(c) >= min_depth: out[c] = d
            if d < k: fr += [((p, o), d + 1) for o, p, st in (self.syn[c][1].get("@") or []) + (self.syn[c][1].get("@i") or [])]
        return out
    def starts(self, word, pos, ctx):
        """Where a word starts its climb: its chosen noun meaning; a verb starts from its derived event nouns (sue -> lawsuit, litigation), because WordNet's verb parents are shallow."""
        key, sense = self.choose(word, pos, ctx)
        if not key: return [], 0, []
        if pos == "n": return [key], sense, []
        der = [(p, o) for o, p, st in self.syn[key][1].get("+", []) if p == "n"]
        return der[:3], sense, sorted({self.syn[d][0][0] for d in der[:3]})
    def name(self, key): return self.syn[key][0][0]
class Landing:
    """Embedding landing on IPTC (owner 2026-11-19): each active Media Topic becomes one node card (label + definition + parent path, optionally + Wikidata label and aliases through its exactMatch link) embedded once with bge-small.
    An article, or one of its sentences, lands on the nearest card at any depth; the tree then gives the path up, the siblings and the Wikidata link. Provenance: Inferred."""
    def __init__(self, pack, alias=True, model="BAAI/bge-small-en-v1.5", emb=None):
        import json, hashlib, numpy as np
        self.P = pack; self.np = np
        if emb is None:   # own encoder (simulation bench); the trace passes its shared one, already at max_seq_length 256, so no caller switches the length per call
            from sentence_transformers import SentenceTransformer
            emb = SentenceTransformer(model, device="cpu"); emb.max_seq_length = 256
        self.emb = emb
        wd = json.load(open(SRC + "/wikidata/iptc_wd_slice.json")) if alias else {}
        self.kids = collections.defaultdict(list); self.ids = []; cards = []
        for k in sorted(pack.node):   # qcode order, so the card order and cards_sha never depend on dict order
            ch = pack.chain(k)
            if any(q in pack.retired for q in ch): continue   # retired nodes never become cards, so land() cannot return one
            if pack.par.get(k): self.kids[pack.par[k]].append(k)
            n = pack.node[k]; q = [u.rsplit("/", 1)[1] for u in n.get("exactMatch", []) if "wikidata" in u]; self.ids.append(k)
            extra = [x for qq in q for x in ([wd[qq]["label"]] + wd[qq].get("aliases", []) if qq in wd else [])]
            cards.append(n["prefLabel"]["en-GB"] + ": " + n.get("definition", {}).get("en-GB", "") + (" Also: " + ", ".join(dict.fromkeys(extra)) + "." if extra else "") + " Under: " + " > ".join(pack.lab(c) for c in ch[:-1]))
        self.cards = cards; self.cards_sha = hashlib.sha256("\n".join(cards).encode()).hexdigest(); self.E = self.emb.encode(cards, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
    def node(self, k, score=None, sents=None):
        n = self.P.node[k]; ch = self.P.chain(k); par = self.P.par.get(k)
        return {"qcode": k, "label": self.P.lab(k), "layer": len(ch), "path": [self.P.lab(c) for c in ch], "path_codes": list(ch), "definition": n.get("definition", {}).get("en-GB", ""),
                "siblings": [self.P.lab(c) for c in self.kids.get(par, []) if c != k][:6] if par else [], "children": [self.P.lab(c) for c in self.kids.get(k, [])][:6],
                "wikidata": [u for u in n.get("exactMatch", []) if "wikidata" in u][:1], "iptc_url": "http://cv.iptc.org/newscodes/mediatopic/" + k.split(":")[1], "score": score, "sentences": sents or []}
    def encode(self, doc, text, max_sents=25, vote=True):
        """The embedding half of land(): article cosines over the cards, and each sentence's nearest card (index, cosine). Cacheable, so the calibrator and the trace share one path. vote=False leaves the sentences un-landed (si, sv empty) for encode_sents to fill."""
        np = self.np; v = self.emb.encode([text[:2000]], normalize_embeddings=True)[0]; sc = self.E @ v
        enc = {"sc": sc, "ss": [s.text.strip() for s in doc.sents if len(s.text.strip()) > 40][:max_sents], "si": [], "sv": []}
        return self.encode_sents(enc) if vote else enc
    def encode_sents(self, enc):
        """The costly half (most of the stage's time): land each sentence on its nearest card. Fills enc in place."""
        if enc["ss"]:
            S = self.emb.encode(enc["ss"], batch_size=32, normalize_embeddings=True) @ self.E.T; enc["si"] = S.argmax(1).tolist(); enc["sv"] = S.max(1).tolist()
        return enc
    def assemble(self, enc, k=5, share=None, damp_k=0.5):
        """The ranking half. share (per-card landing share, aligned to self.ids) switches hub damping on: cards are ranked by cosine - damp_k * share; scores shown stay raw cosines (landing-v1, specs/landing_calibration_v1.json)."""
        np = self.np; sc = enc["sc"]; rk = sc if share is None else sc - damp_k * share; top = np.argsort(-rk)[:k]; ss = enc["ss"]; by = collections.defaultdict(list)
        for s, j, v in zip(ss, enc["si"], enc["sv"]): by[self.ids[j]].append((round(float(v), 3), s))
        art = [self.node(self.ids[int(j)], round(float(sc[j]), 3)) for j in top]
        sent = sorted((self.node(q, max(x[0] for x in L), [x[1][:160] for x in L[:3]]) | {"n_sentences": len(L)} for q, L in by.items()), key=lambda r: (-r["n_sentences"], -r["score"]))
        tops = collections.Counter(r["path"][0] for r in sent for _ in range(r["n_sentences"])); by_code = collections.Counter(r["path_codes"][0] for r in sent for _ in range(r["n_sentences"]))
        return {"article": art, "sentences": sent[:12], "sentence_top_vote": tops.most_common(3), "vote_by_code": sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0]))[:3], "vote_all": dict(by_code), "n_sentences": len(ss), "n_cards": len(self.ids),
                "rank_scores": [round(float(rk[j]), 4) for j in top[:2]], "damped": bool(share is not None and int(np.argmax(sc)) != int(top[0])), "voted": bool(enc["si"])}
    def land(self, doc, text, k=5, max_sents=25, share=None, damp_k=0.5, gate=False, keep=None):
        """gate=True (landing-v1, build spec 2.6 / L1): the sentence vote runs only when the 3 best cards disagree on the level-1 code (l1_agree3 < 3); otherwise the sentences are counted but not landed (result voted False, vote empty)."""
        if not gate:
            enc = self.encode(doc, text, max_sents)
            if keep is not None: keep["sc"] = enc["sc"]   # keep: optional dict that receives the raw card cosines (the re-ranker's input); the result itself is unchanged
            return self.assemble(enc, k, share, damp_k)
        enc = self.encode(doc, text, max_sents, vote=False); r = self.assemble(enc, k, share, damp_k); a = r["article"]
        if keep is not None: keep["sc"] = enc["sc"]
        if enc["ss"] and sum(1 for x in a[:3] if x["path_codes"][0] == a[0]["path_codes"][0]) < 3: r = self.assemble(self.encode_sents(enc), k, share, damp_k)
        return r
class PackView:
    def __init__(self, nlp):
        self.nlp = nlp; self.pack = Pack(nlp); self.fam = Family(); self.X = None; self.landing = Landing(self.pack, alias=False)   # L2718: Wikidata aliases cost 2.2 points
    def geo(self):
        """GeoNames tables for extract.place_country, without extract.init (that also loads a second parser and the harvest files)."""
        if self.X is None:
            import extract as X; X.ctry = {}; X.city = collections.defaultdict(dict); X.adm = collections.defaultdict(set); gd = "/workspace/data/geo/"
            for l in open(gd + "countryInfo.txt", encoding="utf-8"):
                if l[0] != "#": f = l.rstrip("\n").split("\t"); X.ctry[f[4]] = f[0]
            for l in open(gd + "cities15000.txt", encoding="utf-8"):
                f = l.split("\t")
                for nm in (f[1], f[2]): X.city[nm][f[8]] = max(X.city[nm].get(f[8], 0), int(f[14] or 0))
            for l in open(gd + "admin1CodesASCII.txt", encoding="utf-8"):
                f = l.rstrip("\n").split("\t"); X.adm[f[1]].add(f[0].split(".")[0]); X.adm[f[2]].add(f[0].split(".")[0])
            self.X = X
        return self.X
    def cascade(self, doc, places, top=40):
        """Word cascade (owner 2026-11-19): each extracted word goes sideways (synonyms, siblings), then up (parents), and joins a group:
        its WordNet topic domain, its IPTC topic path (layer = depth in the tree), or, for a place, its country and region chain.
        Sense: a group is seeded when 2 or more words have it on their first meaning; a word may switch to a later meaning (up to the 8th) only to join a seeded group, else it keeps the first. Groups are those with 2 or more members.
        Measured (ledger L2713): as an article-topic vote the topic domains score 14.7% on MN-DS, so this is shown as evidence per article, not as a topic answer."""
        cnt = collections.Counter(); order = {}
        for t in doc:
            if t.pos_ in ("NOUN", "VERB") and t.is_alpha and len(t.lemma_) > 2 and t.lemma_.lower() not in STOP:
                k = (t.lemma_.lower(), "n" if t.pos_ == "NOUN" else "v"); cnt[k] += 1; order.setdefault(k, len(order))
        keys = [k for k, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], order[kv[0]]))][:top]
        S = {k: self.fam.senses(*k, n=8) for k in keys}; pool = collections.Counter(L[0]["domain"] for L in S.values() if L and L[0]["domain"])   # groups seeded by words on their usual (first) meaning
        rows = []; G = collections.defaultdict(set)
        for (w, p) in keys:
            L = S[(w, p)]
            if not L: continue
            sh = [x for x in L if x["domain"] and pool[x["domain"]] >= 2]   # a meaning that joins a seeded group; the largest group wins, else the first meaning
            best = max(sh, key=lambda x: (pool[x["domain"]], -x["sense"])) if sh else L[0]
            iptc = []
            if p == "n":
                c = self.pack.place(w)
                if c: iptc = [self.pack.lab(q) for q in self.pack.chain(c[0][1])]
            rows.append({"word": w, "pos": "noun" if p == "n" else "verb", "mentions": cnt[(w, p)], "sense": best["sense"], "sideways": best["synonyms"] + best["siblings"], "up": best["parents"], "group": best["domain"], "iptc": iptc})
            if best["domain"]: G[("WordNet topic domain", "group", best["domain"])].add(w)
            for i, n in enumerate(iptc): G[("IPTC topic", i + 1, n)].add(w)
        ctx = {t.lemma_.lower() for t in doc if t.is_alpha and len(t.text) > 3}; M = collections.defaultdict(dict); ev = {}; sw = 0
        for (w, p) in keys:
            st, sense, der = self.fam.starts(w, p, ctx); sw += sense > 1
            if der: ev[w] = der
            for s0 in st:
                for a, d in self.fam.ups(s0).items(): M[a][w] = min(d, M[a].get(w, 9))
        meet = []
        for a, mem in M.items():
            if len(mem) >= 2: meet.append({"tree": "WordNet meeting point", "layer": self.fam.depth(a), "group": self.fam.name(a), "members": sorted(mem), "steps_up": max(mem.values())})
        bm = {}
        for g in meet:   # same members: keep the deepest (most specific) shared parent
            k = tuple(g["members"])
            if k not in bm or g["layer"] > bm[k]["layer"]: bm[k] = g
        meet = sorted(bm.values(), key=lambda g: (-len(g["members"]) * g["layer"], g["group"]))
        for r in rows:
            r["event_nouns"] = ev.get(r["word"], [])
        for pl in places:
            if pl["not_place"] or not pl["part_of"] or pl.get("wordnet_other_place"): continue
            chain = list(reversed(pl["part_of"]))
            for i, n in enumerate(chain): G[("place", i + 1, n)].add(pl["name"])
        groups = [{"tree": t, "layer": l, "group": n, "members": sorted(v)} for (t, l, n), v in G.items() if len(v) >= 2]
        best_layer = {}
        for g in groups:   # keep the deepest layer per member set, so 'united states > north america' with the same members shows once
            key = (g["tree"], tuple(g["members"]))
            if key not in best_layer or str(g["layer"]) > str(best_layer[key]["layer"]): best_layer[key] = g
        groups = sorted(best_layer.values(), key=lambda g: (-len(g["members"]), g["tree"]))
        return {"words": rows, "groups": groups[:25], "meet": meet[:25], "sense_switched": sw, "n_words": len(keys), "names_without_climb": sorted({e.text.strip() for e in doc.ents if e.label_ in ("PERSON", "ORG")})[:20]}
    def places(self, doc):
        """Place names (spaCy GPE, LOC, FAC): GeoNames country plus WordNet 'is a' and 'part of' (structure_pack.link_place)."""
        X = self.geo(); cnt = collections.Counter(e.text.strip() for e in doc.ents if e.label_ in ("GPE", "LOC", "FAC"))
        explicit = {X.ALIAS.get(n) or X.ctry.get(n) for n in cnt} - {None}; out = []
        for n, k in cnt.most_common(30):
            r = self.pack.link_place(n, "", explicit, X); w = r.get("wordnet") or {}
            out.append({"name": n, "mentions": k, "country": r["country"], "how": r["how"], "is_a": w.get("is_a"), "part_of": w.get("part_of", []), "not_place": bool(r.get("not_place")), "wordnet_other_place": bool(r.get("wordnet_other_place"))})
        return out
    def view(self, text, domain_name, acts):
        doc = self.nlp(text[:12000]); guess = (domain_name or "").lower(); gcode = l1_code(guess); lifts = []; unplaced = []; hops = collections.Counter(); seen = set()
        for w in self.pack.terms(doc):
            c = self.pack.place(w)
            if not c: unplaced.append(w); continue
            f = [x for x in c if self.pack.chain(x[1])[0] == gcode]; x = (f or c)[0]; hops[x[0]] += 1   # compare IPTC codes, never label names (plan v2 step 1)
            lifts.append({"word": w, "how": x[0], "via": x[2], "path": self.pack.path(x[1]), "in_topic": bool(f)})
        lifts.sort(key=lambda r: (not r["in_topic"], r["how"] != "exact"))
        used = set()
        for a in acts or []:
            for s in (a.get("subject"), a.get("verb"), a.get("object")):
                for t in self.nlp.make_doc(str(s or "")): used.add(t.text.lower()); used.add(t.lemma_.lower())
        cnt = collections.Counter(); order = {}
        for t in doc:
            if t.pos_ in ("NOUN", "VERB") and t.is_alpha and len(t.lemma_) >= 4 and t.lemma_.lower() not in STOP and t.lemma_.lower() not in used and t.text.lower() not in used:
                k = (t.lemma_.lower(), "n" if t.pos_ == "NOUN" else "v"); cnt[k] += 1; order.setdefault(k, len(order))
        sing = []
        for (w, p), _ in sorted(cnt.items(), key=lambda kv: (-kv[1], order[kv[0]])):
            fm = self.fam.of(w, p)
            if fm: fm["mentions"] = cnt[(w, p)]; sing.append(fm)
            if len(sing) >= 10: break
        places = self.places(doc)
        return {"cascade": self.cascade(doc, places), "landing": self.landing.land(doc, text), "places": places, "guess": guess or None, "n_terms": len(lifts) + len(unplaced), "n_placed": len(lifts), "in_topic": sum(1 for r in lifts if r["in_topic"]), "hops": dict(hops), "lifts": lifts[:40], "unplaced": unplaced[:40], "singletons": sing}
