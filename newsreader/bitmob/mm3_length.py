"""MM3 length test: does MM3's reliability cascade (two reviewers, quick depth) plateau earlier than Jev?
Stories: the first N articles of data/trainset/length-long.jsonl whose 3,000-word Jev reading has a condition key; one key per story (the first).
For each story and each length (250, 500, 750, 1,000 words): a story file + an MM3 class request (9 yes/no on that key: present, main point, fact), run by the mm3 CLI.
Writes data/world-engine/mm3/len/results.jsonl (story, key, length, run id, gates, p per question). Resumable.
Usage: python3 newsreader/bitmob/mm3_length.py [N] [CONC] [--prepare-only]   (runs through tools/mm3local: local Clef)"""
import sys, os, re, json, glob, subprocess, concurrent.futures as cf
import pyarrow.parquet as pq, pyarrow as pa
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 100; CONC = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 3
PREP = "--prepare-only" in sys.argv
MM3 = "/root/.claude/plugins/cache/mvp-scale/mm3/035c10697964/bin/mm3.mjs"
D = "/workspace/data/world-engine/mm3/len"; os.makedirs(D, exist_ok=True); OUT = f"{D}/results.jsonl"
NAMES = {c["id"]: c["name"] for c in json.load(open("/workspace/exports/world-engine-labels.json"))["conditions"]}
LONG = [json.loads(l) for l in open("/workspace/data/trainset/length-long.jsonl")]
LONG = [r for r in LONG if r["w3000"]][:N]
want = {r["url"] for r in LONG}
text = {r["url"]: r for r in pa.concat_tables([pq.read_table(f, columns=["url", "title", "text"]) for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet"))]).filter(
    pa.compute.is_in(pa.concat_tables([pq.read_table(f, columns=["url"]) for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet"))])["url"], value_set=pa.array(list(want)))).to_pylist()}
LENGTHS = [250, 500, 750, 1000]
def phrase(key):
    d, dirn = key.split("|"); n = NAMES.get(d, d.replace("_", " ")).lower()
    return n, ("rising" if dirn == "up" else "falling"), ("up" if dirn == "up" else "down")
REQ = """mak:
  goal: The text reports {n} {verb}
  verb: class
  depth: quick
  where: [{path}]
  ask:
    concerns:
      present:
        family: correctness
        pass: yes
        1: Does the text report that {n} is {verb}?
        2: Does the text give a concrete event or figure showing {n} {verb}?
        3: Would a careful analyst say this story moves {n} {dirn}?
      main:
        family: correctness
        pass: yes
        4: Is {n} {verb} a main point of the story rather than background?
        5: Would a headline for this story mention {n} {verb}?
        6: Is {n} {verb} more than a passing mention in the text?
      fact:
        family: correctness
        pass: yes
        7: Is the change in {n} reported as having happened, not as opinion or forecast?
        8: Does the text say who or what is affected by the change in {n}?
        9: Does the text tie the change in {n} to a named place?
    decisions:
      support:
        pass: [strong, moderate]
        10:
          scale: How strongly does the text support {n} {verb}?
          levels: [no support at all, weak, moderate, strong]
      scope:
        pass: [enough]
        11:
          choice: Can this be judged from the text shown?
          options: [enough, partial, missing]
mdl:
  why: validate
  area: data
  problem: Length test - does MM3 find {n} {verb} at {L} words of the article
  touches: [length-test, reader]
"""
jobs = []
for i, r in enumerate(LONG):
    key = r["w3000"][0]; n, verb, dirn = phrase(key); art = text[r["url"]]; words = art["text"].split()
    for L in LENGTHS:
        story = f"{D}/s{i:03}-w{L}.md"; req = f"{D}/s{i:03}-w{L}.yaml"
        if not os.path.exists(story): open(story, "w").write(f"# {art['title']}\n\n{' '.join(words[:L])}\n")
        if not os.path.exists(req): open(req, "w").write(REQ.format(n=n, verb=verb, dirn=dirn, L=L, path=story[len('/workspace/'):]))
        jobs.append((i, r["url"], key, L, req))
print(f"{len(LONG)} stories, {len(jobs)} requests in {D}", flush=True)
if PREP: sys.exit(0)
done = {(j["story"], j["length"]) for j in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
def parse(out):
    rec = {"id": (re.search(r"id: (MM3-\d+)", out) or [None, None])[1]}
    for cat in ("present", "main", "fact"):
        m = re.search(rf"  {cat}: \{{gate: (\w+), (.*?)\}}", out)
        if m: rec[cat] = {"gate": m[1], "p": {k: float(v) for k, v in re.findall(r"(\d+): ([\d.]+)", m[2])}}
    for dec in ("support", "scope"):
        m = re.search(rf"  {dec}: \{{gate: (\w+), \d+: \{{top: ([^,]+), p: ([\d.]+)\}}", out)
        if m: rec[dec] = {"gate": m[1], "top": m[2], "p": float(m[3])}
    m = re.search(r"consensus: (\w+)", out); rec["consensus"] = m[1] if m else None
    return rec
def run(job):
    i, url, key, L, req = job
    if (i, L) in done: return None
    p = subprocess.run(["/workspace/tools/mm3local", "class", req[len('/workspace/'):]], cwd="/workspace", capture_output=True, text=True, timeout=600)
    rec = {"story": i, "url": url, "key": key, "length": L, **parse(p.stdout + p.stderr)}
    if not rec.get("id"): rec["error"] = (p.stdout + p.stderr)[-300:]
    return rec
with cf.ThreadPoolExecutor(CONC) as ex, open(OUT, "a") as f:
    for rec in ex.map(run, jobs):
        if rec: f.write(json.dumps(rec) + "\n"); f.flush(); print(rec["story"], rec["length"], rec.get("id"), rec.get("present", {}).get("gate"), rec.get("error", "")[:120], flush=True)
