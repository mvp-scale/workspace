"""Evidence for Echo (novelty / same event): MM3 scans on local Clef judge pairs of stories, then Echo's cosine is scored against those judgements.
Pairs: for each sampled story, its most similar earlier story within 7 days (Glance cosine), sampled evenly across four similarity bands so the
test covers easy and hard cases. Each pair is one file (titles + first 120 words of each). MM3 quick scan, 10 pairs per scan, local Clef only.
Concerns (3 angles each, one reversed): same event, same place, same topic; decisions: relation (choice) and overlap (scale).
Truth for "same event": both forward angles yes and the reversed angle no (Clef consensus); pairs where Clef splits are reported, not scored.
Scores: Echo cosine (Glance), Scholar cosine, title word overlap (Jaccard) as the second approach, and Echo + same-country (Locate) as a combination.
Run: python3 newsreader/bitmob/echo_pairs.py   (then the analysis runs in the embed-zs venv, printed at the end)"""
import json, os, re, subprocess, hashlib, shutil, numpy as np, sys
D = "/workspace/data/mm3-train"; F = f"{D}/features"; HOME = f"{D}/echo"; MM3 = "/root/.claude/plugins/cache/mvp-scale/mm3/035c10697964/bin/mm3.mjs"
os.makedirs(f"{HOME}/.mm3", exist_ok=True); shutil.copy("/workspace/.mm3/config.yaml", f"{HOME}/.mm3/config.yaml")
ids = json.load(open(f"{F}/ids.json")); first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}; rows = [first[i] for i in ids]
X = np.load(f"{F}/glance_full.npy"); X /= np.linalg.norm(X, axis=1, keepdims=True); ts = np.load(f"{F}/published_ts.npy")
rng = np.random.default_rng(7); pairs = []
for i in rng.permutation(len(ids)):
    m = np.where((ts < ts[i]) & (ts >= ts[i] - 7 * 86400))[0]
    if len(m): j = m[np.argmax(X[m] @ X[i])]; pairs.append((int(i), int(j), float(X[i] @ X[j])))
bands = [(0, .6), (.6, .75), (.75, .88), (.88, 1.01)]; pick = []
for lo, hi in bands: pick += [p for p in pairs if lo <= p[2] < hi][:40]
print(f"{len(pairs)} candidate pairs; picked {len(pick)} across bands {[sum(lo <= p[2] < hi for p in pick) for lo, hi in bands]}", flush=True)
REQ = """mak:
  goal: "Each pair of stories is clearly the same event or clearly different"
  verb: scan
  depth: quick
  over:
    file: {folder}/*.md
  ask:
    file:
      concerns:
        same-event:
          family: correctness
          pass: no
          1: Do the two stories in {{file}} report the same event?
          2: Are both stories in {{file}} about one and the same incident, announcement or decision?
          3: Are the two stories in {{file}} about different events?
        same-place:
          family: correctness
          pass: no
          4: Do both stories in {{file}} happen in the same country?
          5: Are the two stories in {{file}} set in the same place?
          6: Do the two stories in {{file}} take place in different countries?
        same-topic:
          family: correctness
          pass: no
          7: Are both stories in {{file}} about the same subject?
          8: Do the two stories in {{file}} cover the same topic?
          9: Are the two stories in {{file}} about different subjects?
      decisions:
        relation:
          pass: [none_fits]
          10:
            choice: How are the two stories in {{file}} related?
            options: [same_event, follow_up, same_topic_only, unrelated, none_fits]
        overlap:
          pass: [none]
          11:
            scale: How much of the two stories in {{file}} says the same thing?
            levels: [none, a_little, a_lot, nearly_all]
mdl:
  why: validate
  area: data
  stage: build
  problem: "Teacher labels for Echo: are two news stories the same event"
  teacher: clef-flash-q4km
  tags: ["#echo", "#same-event", "#training-labels"]
"""
env = dict(os.environ, MM3_HOME=HOME, TYPESAFE_BASE_URL="http://127.0.0.1:8018", TYPESAFE_API_KEY="local", JEV_MODEL="clef-flash-q4km", JEV_TIMEOUT_MS="120000")
out = []
for b in range(0, len(pick), 10):
    folder = f"p{b // 10:03d}"; shutil.rmtree(f"{HOME}/{folder}", ignore_errors=True); os.makedirs(f"{HOME}/{folder}"); names = {}
    for k, (i, j, s) in enumerate(pick[b:b + 10]):
        A, B_ = rows[i], rows[j]; nm = f"pair-{k:02d}.md"; names[f"{folder}/{nm}"] = (i, j, s)
        open(f"{HOME}/{folder}/{nm}", "w").write(f"# Story 1: {A['title']}\n\n{' '.join(A['text'].split()[:120])}\n\n# Story 2: {B_['title']}\n\n{' '.join(B_['text'].split()[:120])}\n")
    open(f"{HOME}/{folder}.yaml", "w").write(REQ.format(folder=folder))
    p = subprocess.run(["node", MM3, "scan", f"{folder}.yaml"], cwd=HOME, env=env, capture_output=True, text=True, timeout=900)
    run = [json.loads(l) for l in open(f"{HOME}/.mm3/log.jsonl")][-1]
    if run.get("verb") != "scan": print("scan failed", folder, p.stdout[-300:], p.stderr[-300:]); continue
    A_ = run["answers"]
    for f, (i, j, s) in names.items():
        a = {n: A_[f"{f}#{n}"]["p"] for n in range(1, 10) if f"{f}#{n}" in A_}
        if len(a) == 9: out.append({"i": i, "j": j, "glance_cos": s, "a": a, "relation": A_.get(f"{f}#10", {}).get("dist"), "run": run["id"]})
    shutil.rmtree(f"{HOME}/{folder}", ignore_errors=True); os.remove(f"{HOME}/{folder}.yaml")
    print(f"{folder}: {len(out)} pairs labelled", flush=True)
for f in ("log.jsonl", "index.db"):
    if os.path.exists(f"{HOME}/.mm3/{f}"): os.remove(f"{HOME}/.mm3/{f}")
json.dump(out, open(f"{D}/echo-pairs.json", "w"), indent=1); print("saved", len(out), "pairs")
