"""structure_pack: place a word our ontology does not know on an IPTC Media Topics node, by exact label, a WordNet synonym, or one WordNet hop up; the IPTC tree gives the rest of the path.
Lean pack on disk (/workspace/data/ontology_src): IPTC Media Topics JSON-LD (CC BY 4.0), Princeton WordNet 3.0 nouns. CPU only. Same logic as t156/t157 (sorted candidates, so two runs agree); results are Inferred, not Observed.
    from structure_pack import Pack; p = Pack(nlp); p.terms(doc); p.place(term); p.path(node); p.place_chain(name); p.link_place(name, dom, explicit, EX)
2026-11-18 gap census (ledger L2710): retired IPTC topics are left out of the index (15% of placements landed on them), names are left out of terms (they belong to name typing),
and place names get WordNet's 'is a' and 'part of' chain (agrees with the GeoNames country on 97.5% where both answer)."""
import os, re, json, collections
SRC = "/workspace/data/ontology_src"
PRI = {"exact": 0, "side": 1, "up": 2}
class Pack:
    def __init__(self, nlp, senses=3, retired=False):
        self.nlp = nlp; self.senses = senses; self._n = {}; self._p = {}
        cs = json.load(open(SRC + "/iptc/medtop.json"))["conceptSet"]
        self.node = {c["qcode"]: c for c in cs}; u2q = {c["uri"]: c["qcode"] for c in cs}
        self.par = {c["qcode"]: (u2q.get(c["broader"][0]) if c.get("broader") else None) for c in cs}
        self.L1 = {self.lab(q): q for q in self.node if not self.par.get(q)}
        self.idx = collections.defaultdict(set)
        self.retired = {q for q, c in self.node.items() if c.get("retired")}
        for q in self.node:
            if not retired and any(x in self.retired for x in self.chain(q)): continue
            full = self.lab(q); self.idx[self.norm(full)].add(q)
            parts = [x.strip() for x in re.split(r",| and ", full) if x.strip()]
            if len(parts) > 1:
                for x in parts: self.idx[self.norm(x)].add(q)
        d = SRC + "/wordnet/wordnet/"; self.syn = {}; self.lem = collections.defaultdict(list); self.inst = {}; self.holo = {}; self.cap = set()   # cap: capitalised WordNet words whose synset is not an instance (Hollywood = the film industry): a name that is also a GeoNames place is then a metonym
        for l in open(d + "data.noun"):
            if l.startswith(" "): continue
            h, _ = l.split("|", 1); f = h.split(); wc = int(f[3], 16)
            words = [f[4 + 2 * i].lower().replace("_", " ") for i in range(wc)]; pc = int(f[4 + 2 * wc]); ptr = f[5 + 2 * wc:]
            self.syn[f[0]] = (words, [ptr[4 * i + 1] for i in range(pc) if ptr[4 * i] in ("@", "@i")])
            self.inst[f[0]] = [ptr[4 * i + 1] for i in range(pc) if ptr[4 * i] == "@i"]
            if not self.inst[f[0]]: self.cap.update(f[4 + 2 * i].replace("_", " ").lower() for i in range(wc) if f[4 + 2 * i][0].isupper())
            self.holo[f[0]] = [ptr[4 * i + 1] for i in range(pc) if ptr[4 * i] == "#p"]
        for l in open(d + "index.noun"):
            if l.startswith(" "): continue
            f = l.split(); self.lem[f[0].replace("_", " ")] = f[6 + int(f[3]):]
    def lab(self, q): return self.node[q]["prefLabel"]["en-GB"].lower()
    def norm(self, s):
        if s not in self._n: self._n[s] = " ".join(t.lemma_.lower() for t in self.nlp(s) if t.is_alpha)
        return self._n[s]
    def chain(self, q):
        out = []
        while q: out.append(q); q = self.par.get(q)
        return out[::-1]
    def path(self, q): return " > ".join(self.lab(x) for x in self.chain(q))
    def terms(self, doc, names=False):
        s = {t.lemma_.lower() for t in doc if t.pos_ == "NOUN" and t.is_alpha and len(t.lemma_) > 2}
        for ch in doc.noun_chunks:
            w = [t for t in ch if t.pos_ in ("NOUN", "PROPN", "ADJ") and t.is_alpha]
            if 2 <= len(w) <= 3 and (names or not any(t.pos_ == "PROPN" for t in w)): s.add(" ".join(t.lemma_.lower() for t in w))
        return sorted(s)
    def place(self, term):
        """-> [(hop, node, via)] sorted by hop priority, one per (hop, node)."""
        if term in self._p: return self._p[term]
        r = [("exact", q, term) for q in sorted(self.idx.get(term, ()))]
        for o in self.lem.get(term, [])[:self.senses]:
            words, hy = self.syn[o]
            for w in words:
                if w != term: r += [("side", q, f"{term} = {w}") for q in sorted(self.idx.get(self.norm(w), ()))]
            for h in hy:
                for w in self.syn[h][0]: r += [("up", q, f"{term} -> {w}") for q in sorted(self.idx.get(self.norm(w), ()))]
        seen = set(); out = []
        for x in r:
            if x[:2] not in seen: seen.add(x[:2]); out.append(x)
        self._p[term] = sorted(out, key=lambda y: PRI[y[0]]); return self._p[term]
    def place_chain(self, name, countries=None, prefer=None, kind=None):
        """WordNet for a place name: {'is_a', 'part_of': [...], 'country'} or None. Only senses that are instances (named things).
        countries: {lowercase name: code}; the first chain member found in it gives 'country'. prefer (a country code) and kind ('region' or 'city', from GeoNames)
        pick the sense that matches what GeoNames found ('Delaware' the state, not the river; 'Melbourne' in Australia, not Florida); else the first sense."""
        n = name.strip().lower()
        if n in self.nlp.Defaults.stop_words: return None
        offs = [o for o in (self.lem.get(n) or self.lem.get(re.sub(r"^the ", "", n)) or []) if self.inst.get(o)]
        KIND = {"region": ("state", "province", "region", "county", "territory", "country", "area"), "city": ("city", "town", "capital", "port", "village")}
        outs = []
        for o in offs:
            out = {"is_a": self.syn[self.inst[o][0]][0][0], "part_of": [], "country": None}; cur = o
            for _ in range(5):
                if countries and out["country"] is None:
                    ws = [w for w in self.syn[cur][0] if w == n or w not in n] if cur == o else self.syn[cur][0][:1]   # skip 'jersey' inside 'new jersey'
                    for w in ws:
                        if w in countries: out["country"] = countries[w]; break
                if not self.holo.get(cur): break
                cur = self.holo[cur][0]; out["part_of"].append(self.syn[cur][0][0])
            outs.append(out)
        if not outs: return None
        score = lambda x: ((prefer is not None and x["country"] == prefer) * 2 + (kind in KIND and any(k in x["is_a"] for k in KIND[kind])))
        return max(outs, key=score)   # max keeps the first sense on ties
    def lookup_places(self, text, EX):
        """Whole-word, case-sensitive lookup beside the spaCy candidates (L2776-L2779): GeoNames country names, extract.ALIAS, and demonyms (specs/demonyms_wordnet_v0.json, built from WordNet pertainyms by build-demonyms.py). A trailing possessive 's is part of the match.
        Contained-name guard (P3 item 1): a key that sits inside a longer name GeoNames knows (admin1 or city: 'Wales' in 'New South Wales', 'Indian' in 'Indian Wells', 'Jersey' in 'Jersey City') does not fire on its own; the longer name decides, and only when GeoNames gives it one country (else nothing: spaCy + link_place settle it from context).
        Returns [{"text", "country", "how", "span"}], leftmost-longest, no overlaps."""
        if not hasattr(self, "_lk"):
            dm = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs", "demonyms_wordnet_v0.json")))["map"]
            tab = {**{k: (v, "demonym") for k, v in dm.items()}, **{k: (v, "country name") for k, v in EX.ctry.items()}, **{k: (v, "alias") for k, v in EX.ALIAS.items()}}
            self._lk = (tab, re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(tab, key=lambda k: (-len(k), k))) + r")(?:['\u2019]s)?(?![\w])"), self._contained(tab, EX))
        tab, rx, ct = self._lk; out = []; end = 0
        for m in rx.finditer(text):
            k = m.group(1); c, how = tab[k]; s0, e0 = m.start(1), m.end(1)
            if s0 < end: continue   # inside a container already decided
            hit = None
            for C, off, cs in ct.get(k, ()):   # longest container first
                s = s0 - off
                if s >= 0 and text.startswith(C, s) and not (s and re.match(r"\w", text[s - 1])) and not re.match(r"\w", text[s + len(C):s + len(C) + 1]) and not (out and out[-1]["span"][1] > s):
                    hit = (C, s, cs); break
            if hit:
                C, s, cs = hit; end = s + len(C)
                if len(cs) == 1: out.append({"text": C, "country": next(iter(cs)), "how": "contained in place name (GeoNames)", "span": [s, end]})
                continue
            out.append({"text": k, "country": c, "how": how, "span": [s0, e0]})
        return out
    def _contained(self, tab, EX):
        """{key: [(longer GeoNames name, offset of the key in it, {countries}), ...]}, longest name first. Candidates by word n-gram, then an exact whole-word check."""
        W = lambda x: tuple(re.findall(r"\w+", x)); keys = collections.defaultdict(list)
        for k in tab: keys[W(k)].append(k)
        names = collections.defaultdict(set)
        for src in (EX.adm, EX.city):
            for nm, cs in src.items(): names[nm].update(cs)
        ct = collections.defaultdict(list)
        for nm, cs in names.items():
            if nm in tab: continue
            w = W(nm)
            if len(w) < 2: continue
            for i in range(len(w)):
                for j in range(i + 1, min(len(w), i + 4) + 1):
                    for k in keys.get(w[i:j], ()):
                        for m in re.finditer(r"(?<![\w])" + re.escape(k) + r"(?![\w])", nm):
                            if len(nm) > len(k) and (nm, m.start(), frozenset(cs)) not in ct[k]: ct[k].append((nm, m.start(), frozenset(cs)))
        for k in ct: ct[k].sort(key=lambda x: (-len(x[0]), x[0]))
        return dict(ct)
    def link_place(self, name, dom, explicit, EX):
        """GeoNames place linker (extract.place_country) plus three measured fixes: all-caps names looked up again in title case;
        WordNet 'part of' fills a name GeoNames does not know; WordNet picks the region over a same-named city ('Florida' -> US, not the Cuban city)
        only when that country holds a region of that name in GeoNames. A name neither source knows as a place is marked not_place."""
        if not hasattr(self, "_cn"):
            self._cn = {**{k.lower(): v for k, v in EX.ctry.items()}, **{k.lower(): v for k, v in EX.ALIAS.items() if len(k) > 3}}
            self._cn.update({re.sub(r"^the ", "", k): v for k, v in list(self._cn.items()) if k.startswith("the ")})
        c, how = EX.place_country(name, dom, explicit)
        if c is None and name.isupper() and len(name) > 3:
            c, how = EX.place_country(name.title(), dom, explicit); how = how and how + ", case folded"
        wn = self.place_chain(name, self._cn, prefer=c, kind=("region" if how and how.startswith(("region", "country")) else "city" if how and how.startswith("city") else None))
        n = re.sub(r"^the ", "", name.strip(), flags=re.I)
        if c and how and how.startswith("city") and wn and wn["country"] and wn["country"] != c and wn["country"] in EX.adm.get(n, ()):
            c, how = wn["country"], "region over same-named city (WordNet)"
        if c is None and wn and wn["country"]: c, how = wn["country"], "WordNet part of"
        r = {"country": c, "how": how}
        if c and n.lower() in self.cap: r["metonym"] = True   # P3 item 1: 'Hollywood' is the US film industry, not a place an event happened; the country stays, the flag lets a reader discount it
        if wn: r["wordnet"] = wn
        if wn and c and wn["country"] and wn["country"] != c: r["wordnet_other_place"] = True   # WordNet's first meaning is a different place (Melbourne, Florida)
        if c is None and not wn: r["not_place"] = True
        return r
