"""Learn boilerplate lines by repetition: a line (10 to 200 chars) seen in at least 5 articles of one domain is page furniture. Reads runs/harvest/sample.jsonl (20000 articles); writes runs/harvest/boilerplate.json {domain: [lines]} per-domain only."""
import json, collections, re
norm = lambda l: re.sub(r"\s+", " ", l).strip()
dl = collections.defaultdict(collections.Counter); gl = collections.defaultdict(set); R = [json.loads(l) for l in open("runs/harvest/sample.jsonl")]
for r in R:
    seen = {norm(l) for l in (r["text"] or "").split("\n")}
    for l in seen:
        if 10 <= len(l) <= 200: dl[r["domain"]][l] += 1; gl[l].add(r["domain"])
dom = {d: sorted(l for l, c in cnt.items() if c >= 5) for d, cnt in dl.items()}; dom = {d: v for d, v in dom.items() if v}
glob_ = []  # lines seen in many publishers are syndicated story text, not furniture
touched = chars = tot = 0
for r in R:
    ls = [norm(l) for l in (r["text"] or "").split("\n")]; D_ = set(dom.get(r["domain"], [])); hit = [l for l in ls if l in D_]; tot += len(r["text"] or "")
    if hit: touched += 1; chars += sum(len(l) for l in hit)
json.dump({"domains": dom, "global": glob_, "articles": len(R), "articles_touched": touched, "share_touched": round(touched / len(R), 4), "share_chars_removed": round(chars / max(tot, 1), 4), "lines": sum(len(v) for v in dom.values())}, open("runs/harvest/boilerplate.json", "w"), indent=1)
print(len(dom), "domains with lines;", len(glob_), "global lines; touched", touched, "of", len(R), "chars removed share", round(chars / tot, 4)); print(glob_[:12])
