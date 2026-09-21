#!/usr/bin/env python3
"""Build /workspace/probes/v2/darkpatterns.jsonl from Mathur et al. (CSCW 2019) release. Seed 20260921.

Sources (downloaded, never committed):
  1. https://github.com/aruneshmathur/dark-patterns  -> data/final-dark-patterns/dark-patterns.csv  (labelled positives)
  2. https://darkpatterns.cs.princeton.edu/data/dark-patterns-output.tar.lz4 -> segments_second_pass.csv
     (crawl text segments from the clusters the authors reviewed; negatives = segments NOT in the labelled list)
Needs `lz4` python package (pip install lz4; or set PYLIB to a dir containing it).
"""
import csv, json, os, random, re, subprocess, sys, tarfile, urllib.request
sys.path.insert(0, os.environ.get("PYLIB", "/workspace/data/sources/darkpatterns/pylib"))
import pandas as pd
import lz4.frame

SEED = 20260921
N_PER_CLASS = 11  # Sneaking has only 11 usable strings; all classes capped equal
RAW = "/workspace/data/sources/darkpatterns"
OUT = "/workspace/probes/v2/darkpatterns.jsonl"
REPO_URL = "https://github.com/aruneshmathur/dark-patterns"
TAR_URL = "https://darkpatterns.cs.princeton.edu/data/dark-patterns-output.tar.lz4"
LICENSE = "GPL-3.0 (repository LICENSE)"

def norm(s): return " ".join(str(s).split())

def fetch():
    if not os.path.isdir(f"{RAW}/repo"):
        subprocess.check_call(["git", "clone", "-q", "--depth", "1", REPO_URL, f"{RAW}/repo"])
    tar = f"{RAW}/dp-output.tar.lz4"
    if not os.path.exists(tar):
        urllib.request.urlretrieve(TAR_URL, tar)
    seg = f"{RAW}/out/dark-patterns-output/segments_second_pass.csv"
    if not os.path.exists(seg):
        t = tarfile.open(fileobj=lz4.frame.open(tar), mode="r|")
        for m in t:
            if m.name.endswith("segments_second_pass.csv"):
                t.extract(m, f"{RAW}/out"); break
    return f"{RAW}/repo/data/final-dark-patterns/dark-patterns.csv", seg

CLASS = {"Scarcity": "scarcity", "Urgency": "urgency", "Social Proof": "social_proof",
         "Misdirection": "misdirection", "Obstruction": "obstruction", "Sneaking": "sneaking"}
# Forced Action dropped: only 4 usable strings in source (<8).

CRITERIA = {  # paraphrased from Mathur et al. 2019, Table 1 / Section 3
 "scarcity": "Signals that a product is likely to become unavailable (low stock, high demand), which raises its desirability.",
 "urgency": "Imposes a deadline on a sale or deal (countdown, limited-time offer), pushing the shopper to decide faster.",
 "social_proof": "Influences the shopper by describing what other users have done or experienced (recent purchases, viewers, testimonials).",
 "misdirection": "Uses language, visuals or emotion to steer the shopper toward or away from a particular choice (e.g. guilt-tripping opt-outs, pressure, trick wording).",
 "obstruction": "Makes a process, such as cancelling or leaving a service, harder than it needs to be in order to dissuade the action.",
 "sneaking": "Misrepresents what the user is doing or delays/hides information that would likely make them object (hidden costs, hidden subscriptions, items added by default).",
 "not_dark_pattern": "Ordinary page text with no such manipulative intent.",
}
INSTR = ("The text below is a short segment of on-screen text from a shopping website. "
         "Decide which dark-pattern category it belongs to, or whether it is not a dark pattern. Give a probability for each option.")

# Negative safety filter: drop segments carrying obvious dark-pattern cues, since unlabelled
# segments were never individually reviewed.
CUES = re.compile(r"hurry|left|only \d|sold|bought|purchased|viewing|viewed|ends|expire|limited|offer|deal|sale|cancel|"
                  r"no thanks|subscri|member|vip|free|%|stock|available|last chance|countdown|day[s]? |hour|"
                  r"\d\d:\d\d|shipping|save|discount|join|trial|renew|terms|agree|popular|selling|people|customers|"
                  r"just|recently|urgent|now|today|rated|review", re.I)

def main():
    dp_csv, seg_csv = fetch()
    rng = random.Random(SEED)
    d = pd.read_csv(dp_csv).dropna(subset=["Pattern String"]).copy()
    d["t"] = d["Pattern String"].map(norm)
    d = d[d.t.str.len().between(6, 600)].drop_duplicates("t")
    d = d[d["Pattern Category"].isin(CLASS)]
    rows, used = [], set()
    for cat, lab in CLASS.items():
        sub = d[d["Pattern Category"] == cat].sort_values("t").reset_index(drop=True)
        idx = sorted(rng.sample(range(len(sub)), N_PER_CLASS))
        for i in idx:
            r = sub.iloc[i]
            rows.append((lab, r.t, r["Website Page"], f"category={cat}; type={r['Pattern Type']}"))
    # negatives
    csv.field_size_limit(sys.maxsize)
    s = pd.read_csv(seg_csv, engine="python")
    s["t"] = s.inner_text.map(norm)
    pos_all = set(pd.read_csv(dp_csv)["Pattern String"].dropna().map(norm))
    pos_clusters = set(s[s.t.isin(pos_all)].cluster_id)
    n = s[~s.t.isin(pos_all) & ~s.cluster_id.isin(pos_clusters)]
    n = n[n.t.str.len().between(25, 300) & (n.t.str.split().str.len() >= 5)]
    n = n[n.t.map(lambda x: sum(c.isalpha() for c in x) / len(x) > 0.75) & ~n.t.str.contains(CUES)]
    n = n.drop_duplicates("t").drop_duplicates("hostname").sort_values(["cluster_id", "hostname"]).reset_index(drop=True)
    for i in sorted(rng.sample(range(len(n)), N_PER_CLASS)):
        r = n.iloc[i]
        rows.append(("not_dark_pattern", r.t, r.site_url, f"unlabelled crawl segment, cluster_id={r.cluster_id}, host={r.hostname}"))
    rng.shuffle(rows)
    labels = list(CRITERIA)
    with open(OUT, "w") as f:
        for k, (lab, t, url, note) in enumerate(rows):
            f.write(json.dumps({
                "id": f"darkpatterns-{k:03d}", "family": "darkpatterns", "state": t,
                "question": {"type": "choice", "instructions": INSTR, "criteria": CRITERIA},
                "labels": labels, "expected": lab, "split": "public", "group": None,
                "provenance": {"exclude_reason": None, "source": "Mathur et al. 2019 (Dark Patterns at Scale)",
                               "url": url if url.startswith("http") else REPO_URL, "license": LICENSE,
                               "retrieved": "2026-09-21", "source_id": REPO_URL, "notes": note}},
                ensure_ascii=False) + "\n")
    print(len(rows), "rows;", len(n), "negative candidates")

if __name__ == "__main__":
    main()
