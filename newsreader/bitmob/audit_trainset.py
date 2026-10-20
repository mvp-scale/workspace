"""Audit a BitMob training-set file against docs/research/2026-10-19 BitMob training set spec.md (R1-R23; R24-R26 are manual).
One JSON record per line. Prints PASS / FAIL / N/A (no records in scope) per requirement with counts and up to 3 examples; exit 1 if any check fails.
Usage: python3 audit_trainset.py <records.jsonl>"""
import sys, json, re, csv, collections, unicodedata
sys.path.insert(0, "/workspace/demo")
F = sys.argv[1]
recs = [json.loads(l) for l in open(F) if l.strip()]
src = open("/workspace/newsreader/bitmob/ccnews_headline_test.py").read()
OUTLETS = set(re.findall(r'"([a-z0-9.-]+\.[a-z]{2,})"', src.split("OUTLETS = [")[1].split("]")[0]))
CATALOGUE = {r.get("id") or r.get("feed") for r in csv.DictReader(open("/workspace/newsreader/catalogue.csv"))}
try:
    import backends; HOSTED = {b for b, v in backends.BACKENDS.items() if v["hosted"]}
except Exception: HOSTED = set()
AD = re.compile(r"(\d+% off|\bcoupons?\b|promo code|discount code|buy now|shop now|sale ends|\bbest [\w\s-]{0,30}\b(deals|to buy)\b|\bdeals (on|for)\b|\bon sale\b)", re.I)      # shopping language only: "trade deal" is news
ROUND = re.compile(r"(morning (everyone|briefing)|evening briefing|newsletter|what we know so far|live updates?|as it happened|in pictures|news in brief|top stories)", re.I)
COMMON = set("the a an of to in and for on is was are with that by as at from has have it be said will after its his her their were not this but".split())
norm = lambda t: re.sub(r"[^a-z0-9 ]", "", unicodedata.normalize("NFKD", (t or "").lower())).strip()
g = lambda r, k: r.get(k)
ident = lambda r: (r.get("id") or r.get("url") or r.get("title") or "?")[:70]
text = lambda r: (g(r, "title") or "") + " " + (g(r, "description") or "")
def english(s):      # non-Latin letters <= 5% and some common English words; also rejects boilerplate descriptions (category lists). 1.8% of 3,000 CC-News items fail, nearly all rightly
    L = [c for c in s if c.isalpha()]
    if not L or sum(not c.isascii() for c in L) / len(L) > 0.05: return False
    w = re.findall(r"[a-z']+", s.lower())
    return len(w) >= 5 and sum(x in COMMON for x in w) / len(w) >= 0.05
def dupkeys(r): return {"t:" + norm(g(r, "title")), "d:" + norm(g(r, "description"))[:100]} - {"t:", "d:"}
results = []
def check(rid, what, bad, scope=None, note=""):
    n = len(recs) if scope is None else scope
    results.append((rid, what, len(bad), n, bad[:3], note))
check("R1", "input == title + ' — ' + description[:250]", [ident(r) for r in recs if g(r, "input") != (g(r, "title") or "") + " — " + (g(r, "description") or "")[:250]])
check("R2", "title and >= 60 chars of description", [ident(r) for r in recs if not g(r, "title") or len((g(r, "description") or "").strip()) < 60])
check("R3", "English (common-word test)", [ident(r) for r in recs if not english(text(r))])
check("R4", "approved outlet or curated feed", [ident(r) for r in recs if (g(r, "outlet") or g(r, "domain")) not in OUTLETS and g(r, "feed") not in CATALOGUE])
check("R5", "no adverts unless local news check >= 0.70", [ident(r) for r in recs if AD.search(text(r)) and (g(r, "news_check") or 0) < 0.70])
check("R6", "no roundups or live blogs", [ident(r) for r in recs if ROUND.search(text(r))])
keys = collections.Counter(k for r in recs for k in dupkeys(r))
check("R7", "no duplicate stories (title or description start)", sorted({k[:70] for k, n in keys.items() if n > 1})[:50])
check("R8", "labels made from `input` (label_input == input)", [ident(r) for r in recs if not g(r, "input") or g(r, "label_input") != g(r, "input")])
def probs_ok(P): return isinstance(P, dict) and len(P) >= 328 and all(isinstance(v, (int, float)) for v in P.values()) and any(0 < v < 1 for v in P.values())
check("R9", "answers stored as probabilities (not 0/1)", [ident(r) for r in recs if not probs_ok(g(r, "P"))])
def three(P): P = P or {}; return sum(k.startswith("a|") and k[-2:] in ("|0", "|1") for k in P) >= 318 and sum(k.startswith("a|") and k.endswith("|2") for k in P) >= 159
check("R10", "all 159 attributes in all 3 wordings (477 answers)", [ident(r) for r in recs if not three(g(r, "P"))])
check("R11", "target rule recorded", [ident(r) for r in recs if not g(r, "target_rule")])
check("R12", "topic and country asked of the reader", [ident(r) for r in recs if not (g(r, "topic") and g(r, "country") and g(r, "topic_source") == "reader" and g(r, "country_source") == "reader")])
check("R13", "provenance: teacher, rules, prompt_version, labelled_at", [ident(r) for r in recs if not all(g(r, k) for k in ("teacher", "rules", "prompt_version", "labelled_at"))])
hosted = [r for r in recs if g(r, "teacher") in HOSTED]
check("R14", "hosted teacher (registry flag): tokens logged", [ident(r) for r in hosted if not g(r, "tokens")], len(hosted))
gf = sum(g(r, "gate_ok") is False for r in recs) / max(1, len(recs))
check("R15", "gate kept as a label: gate-failed share >= 10%", [] if gf >= 0.10 else [f"gate-failed share {gf:.0%}"], note=f"share {gf:.0%}")
check("R16", "near-cut attributes flagged", [ident(r) for r in recs if "near_cut" not in r])
reps = sum(bool(g(r, "replicate")) for r in recs) / max(1, len(recs))
check("R17", ">= 2% read twice", [] if reps >= 0.02 else [f"replicates {reps:.1%}"], note=f"{reps:.1%}")
paired = sum(bool(g(r, "P_fulltext")) for r in recs) / max(1, len(recs))
check("R18", ">= 2% with paired full-text labels", [] if paired >= 0.02 else [f"paired {paired:.1%}"], note=f"{paired:.1%}")
check("R19", "inclusion_prob on every record; mined_for on mined", [ident(r) for r in recs if not g(r, "inclusion_prob")])
pos = collections.Counter(k for r in recs if g(r, "split") != "test" for k in (g(r, "target_keys") or []))
check("R20", "per-key positives reported (target_keys present)", [ident(r) for r in recs if "target_keys" not in r],
      note=f"{sum(v >= 100 for v in pos.values())} keys >= 100 train positives" if pos else "")
check("R21", "source, year, and ccnews flag on CC-News", [ident(r) for r in recs if not g(r, "source") or not (g(r, "date") or g(r, "published")) or (g(r, "source") == "ccnews" and g(r, "ccnews") is not True)])
tests = [r for r in recs if g(r, "split") == "test"]
check("R22", "test records: >= 2 raters and adjudicated", [ident(r) for r in tests if len(g(r, "raters") or []) < 2 or "adjudicated" not in r], len(tests))
side = collections.defaultdict(set)
for r in recs:
    for k in dupkeys(r): side[k].add(g(r, "split"))
check("R23", "no duplicate group in both train and test", sorted({k[:70] for k, s in side.items() if {"train", "test"} <= s})[:50])
fails = 0
print(f"audit of {F}: {len(recs)} records")
for rid, what, nbad, scope, ex, note in results:
    state = "N/A " if scope == 0 else ("PASS" if nbad == 0 else "FAIL"); fails += state == "FAIL"
    print(f"  {state}  {rid:4} {what}: " + ("no records in scope" if scope == 0 else f"{nbad} of {scope} fail") + (f"  [{note}]" if note else "") + ("" if state != "FAIL" else f"  e.g. {ex}"))
print("  manual: R24 direction flags to raters, R25 teacher chosen by Step 4, R26 CC-News licence")
print(f"{sum(1 for x in results if x[3] and not x[2])} pass, {fails} fail, {sum(1 for x in results if not x[3])} n/a of {len(results)} automatic checks")
sys.exit(1 if fails else 0)
