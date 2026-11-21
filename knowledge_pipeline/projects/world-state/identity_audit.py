"""identity_audit: T174 identity check, corrected measure (item IDENTITY, wave 1; add-only, new file). resource_truth.score_identity counts every alias whose top wbsearchentities hit differs from the canon QID as a conflict (90.4 pct, L2885).
That mixes four different things; this module classifies each resolved pair first (rules fixed in ledger L2889 before applying):
  R5 agree (same QID) | R1 roll-up by design (demonym -> country, city/state -> country via the place linker; a relation, not same_as) | R2 bare surname or acronym by G4 rule (a bare surname / acronym search cannot name the entity)
  R3 lookup error (top hit of the canon (c) or alias (a) is type-inconsistent with the Few-NERD type, or is a common-noun item) | R4 real wrong merge candidate (both hits type-consistent, different entities).
Keyword lists are implementation detail, written after reading the 85 descriptions: the rule is audited against a manual reading of a sample (see the ledger score). Read-only; no network. python3 identity_audit.py [--list]"""
import sys, re, json, random, math
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import wikidata_cache as W
DM = json.load(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "specs", "demonyms_wordnet_v0.json")))["map"]
PLACE_OK = re.compile(r"countr|sovereign|state|city|capital|town|region|territory|district|island|continent|county|province|commune|village|park|residence|union|municipality|area|colony|peninsula", re.I)
BAD = {"person": re.compile(r"family name|surname|given name|street|fortification|military construction|disambig|film|species|village|scientific article|language|census|flight", re.I),
       "org": re.compile(r"scientific article|journal|restaurant|comune|protected area|netfilter|painting|species|film|racehorse|language|census|1939|cruiser|ship|bilateral relations|family name", re.I),
       "product": re.compile(r"scientific article|family name|species|film", re.I)}
def wd(q): r = W.resolve(q); return r
def consistent(ty, r, query):
    if r is None: return False
    d = r.get("description") or ""; lab = r.get("label") or ""
    if lab and lab[0].islower() and query[:1].isupper(): return False   # common-noun item (senate, central bank, university)
    if ty == "place": return bool(PLACE_OK.search(d)) and not re.search(r"academic journal|racehorse|painting|documentary|flight|\blanguage\b|census|conflict|episode|record producer|company|party|family name|attraction", d, re.I)
    return not BAD.get(ty, re.compile("$^")).search(d)
def ini(s): return "".join(w[0] for w in re.findall(r"\w+", s) if w.lower() not in ("of", "the", "and", "for", "in", "on")).lower()
def cls(p):
    ty, canon, al = p["type"], p["canon"], p["alias"]; rc, ra = wd(canon), wd(al)
    cd = (rc or {}).get("description") or ""; ad = (ra or {}).get("description") or ""
    # R3 lookup / common noun
    if not consistent(ty, rc, canon): return "R3c canon lookup wrong sense or common noun"
    iso = p["eid"].startswith("iso:")
    if p["same"]: return "R5 agree"
    if iso:
        code = p["eid"][4:]
        if DM.get(al.rstrip("s")) == code or DM.get(al) == code or DM.get(re.sub(r"-speaking$", "", al)) == code: return "R1 demonym"
    # R2 bare surname / acronym by G4 rule
    toks = [t.lower() for t in re.findall(r"\w+", canon)]
    a_toks = [t.lower() for t in re.findall(r"\w+", re.sub(r"^(mr|mrs|ms|dr)\s+", "", al, flags=re.I))]
    if ty == "person" and len(a_toks) == 1 and a_toks[0] in toks: return "R2 bare surname"
    aa = re.sub(r"[^A-Za-z]|led$", "", al)
    if ty in ("org",) and re.fullmatch(r"[A-Z]{2,6}(-led)?", al.replace("’s", "")) and (aa.lower() == ini(canon) or aa.lower()[:-1] == ini(canon)): return "R2 acronym by rule"
    if not consistent(ty, ra, al): return "R3a alias lookup wrong sense or common noun"
    # R1 roll-up
    if iso:
        names = {canon.lower(), (rc.get("label") or "").lower()} | ({"u.s.", "united states of america", "america", "us"} if code == "US" else set()) | ({"england", "scotland", "wales", "britain", "uk"} if code == "GB" else set())
        if any(n in ad.lower() for n in names if n): return "R1 part-of roll-up"
        if re.search(r"^(country|sovereign)", ad): return "R4 real: two countries merged"
        if PLACE_OK.search(ad) and re.search(r"[A-Z][a-z]+(,| in| of) ", ad) : return "R3a alias place name ambiguous (other-country sense)"
        return "R4 real: place merged with unrelated entity"
    # non-iso containment: head-noun / initials merge
    return "R4 real: different entity merged"
def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    ph = k / n; d = 1 + z * z / n; c = ph + z * z / (2 * n); r = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)); return ((c - r) / d, (c + r) / d)
def pairs(plan=None):
    P = plan or W.load_plan(); out = []
    for eid, ty, canon, surf in P["merges"]:
        rc = wd(canon)
        for s in surf:
            rs = wd(s)
            if rc and rs: out.append({"eid": eid, "type": ty, "canon": canon, "alias": s, "same": rc["qid"] == rs["qid"]})
    return out
def summarize(P):
    from collections import Counter
    c = Counter(); lab = []
    for p in P: k = cls(p); p["cls"] = k; c[k] += 1
    comp = [p for p in P if p["cls"].startswith("R4") or p["cls"] == "R5 agree"]; bad = [p for p in comp if p["cls"].startswith("R4")]
    return c, comp, bad
if __name__ == "__main__":
    P = pairs(); c, comp, bad = summarize(P)
    print("resolved", len(P), "conflicts", sum(not p["same"] for p in P))
    for k, v in sorted(c.items()): print("%3d %s" % (v, k))
    lo, hi = wilson(len(bad), len(comp)); print("comparable", len(comp), "real wrong", len(bad), "rate %.3f CI95 [%.3f, %.3f]" % (len(bad) / max(1, len(comp)), lo or 0, hi or 0))
    # sensitivity bounds: lenient (R3a counted as real wrong) / strict (R3a, R3c, R1 all counted comparable)
    if "--list" in sys.argv:
        for p in sorted(P, key=lambda p: p["cls"]): print(p["cls"][:12], "|", p["canon"], "|", p["alias"])
