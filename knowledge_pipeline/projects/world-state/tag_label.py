"""B1 step 1 (ledger L389): label full news articles with propose-and-verify. spaCy proposes 12 candidates (leaf ranks), local Clef (port 8018) verifies with the tag_pilot questions. Resumable: appends to runs/tag_head/labels.jsonl, one line per article. Only tag phrases and scores are written, never article text.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python tag_label.py [--n 1500]"""
import os, sys, re, json, time, random, sqlite3, math, urllib.request, concurrent.futures as cf, collections, numpy as np
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
import spacy
from sentence_transformers import SentenceTransformer
N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 1500
OUT = "runs/tag_head/labels.jsonl"
nlp = spacy.load("en_core_web_sm"); enc = SentenceTransformer("MongoDB/mdbr-leaf-mt", device="cpu"); enc.max_seq_length = 512
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
rows = db.execute("select id, title, body from items where length(coalesce(body,'')) > 3500 and length(body) < 14000").fetchall(); random.Random(11).shuffle(rows)
seen = set(); arts = []
for i, t, b in rows:
    k = re.sub(r"\W+", " ", (t or "").lower())[:60]
    if k in seen or not t: continue
    seen.add(k); arts.append((i, t.strip(), re.sub(r"\s+", " ", b).strip()))
    if len(arts) == N: break
done = set(json.loads(l)["id"] for l in open(OUT)) if os.path.exists(OUT) else set()
todo = [a for a in arts if f"q:{a[0]}" not in done]; print("articles", len(arts), "done", len(done), "todo", len(todo), flush=True)
BAD = {"DATE", "TIME", "CARDINAL", "ORDINAL", "PERCENT", "MONEY", "QUANTITY"}; DET = {"the", "a", "an", "this", "that", "these", "those", "his", "her", "its", "their", "our", "my", "your", "some", "any", "each", "every"}
def norm(s):
    w = [x for x in re.sub(r"[^\w\s\-&.']", " ", s.lower()).split() if x]
    while w and w[0] in DET: w = w[1:]
    return " ".join(w).strip(" .-'")
def propose(text, K):
    d = nlp(text); c = collections.Counter(); low = text.lower()
    for ch in d.noun_chunks:
        if ch.root.pos_ in ("PRON", "NUM") or ch.root.ent_type_ in BAD: continue
        s = norm(ch.text)
        if len(s) >= 3 and not s.isdigit() and not all(x in nlp.Defaults.stop_words for x in s.split()): c[s] += 1
    for e in d.ents:
        if e.label_ in BAD: continue
        s = norm(e.text)
        if len(s) >= 3 and not s.isdigit(): c[s] += 1
    cands = [s for s in c if len(s) <= 40]
    if not cands: return [], []
    E = enc.encode(cands + [text[:2000]], batch_size=64, normalize_embeddings=True, show_progress_bar=False); sims = E[:-1] @ E[-1]
    sc = [0.5 * float(sims[k]) + 0.5 * min(1.0, math.log1p(low.count(s)) / math.log(6)) for k, s in enumerate(cands)]
    o = np.argsort(sc)[::-1][:K]; return [cands[k] for k in o], [round(sc[k], 4) for k in o]
Q = {"s1": "Is '{c}' one of the main subjects of this article, not just a passing mention?", "s2": "Would a person searching for information about '{c}' find this article relevant?", "s3": "Does the article say something specific about '{c}', beyond just naming it?"}
def ask(x):
    qs = {f"{j}|{k}": {"type": "noul", "instructions": Q[k].format(c=c)} for j, c in enumerate(x["cands"]) for k in Q}
    body = {"state": "News article:\n" + x["text"], "questions": qs, "model": "clef-flash-q4km"}
    for attempt in range(3):
        try:
            a = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=900))["answers"]
            return {key: float(v["noul"]) for key, v in a.items()}
        except Exception as e: time.sleep(2)
    return None
t0 = time.time(); errs = 0
for s in range(0, len(todo), 50):
    items = []
    for i, t, b in todo[s:s + 50]:
        text = t + ". " + b[:3500]; c, sc = propose(text, 12); items.append({"id": f"q:{i}", "text": text, "cands": c, "prop": sc})
    with cf.ThreadPoolExecutor(6) as ex: R = list(ex.map(ask, items))
    with open(OUT, "a") as f:
        for x, r in zip(items, R):
            if r is None: errs += 1; continue
            f.write(json.dumps({"id": x["id"], "cands": x["cands"], "prop": x["prop"], "ans": [[r.get(f"{j}|{k}", 0.0) for k in Q] for j in range(len(x["cands"]))]}) + "\n")
    print(f"{s + len(items)}/{len(todo)} {time.time() - t0:.0f}s errors {errs}", flush=True)
