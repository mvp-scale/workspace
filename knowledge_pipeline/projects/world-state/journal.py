"""journal: the per-article graph record's duplicate logic (build spec step 3, live-trace-v2 journal-v0). Pure functions, no model, no file access.
story_keys(title, body)  -> {"title": sha1|None, "prefix": sha1|None}   title key needs >= 5 words; prefix key = sha1 of the first 300 normalised body characters, needs >= 100
classify(idx, keys, source, seq) -> {"kind", "of_seq", "publishers", "keys"}   kind: first | copy | republished | generic_title | no_key; idx comes from new_index() and is updated in place (it is the run's whole state)
replay(items) -> [classify result per item]   items = (seq, title, body, source) in seq order; used offline (census, funnel view) to get what the runner would have written
MIRROR_RULE (ON since 2026-11-19, owner yes L2744; was off): an extra rule beyond the spec (2.3): one body start under 3 different titles from one source is boilerplate (nature.com "Thank you for visiting"), so its prefix key is disabled. Measured on trace-demo: republished 37 off, 6 on (journal_census.py). Owner approved it; runs record journal.py's sha in run.json, so a run says which version made it.
A story is the group of items that share a key; its root is the first item. An item that matches two stories attaches to the earlier root and never merges them, so the lines alone can rebuild every count (verify_trace.py does)."""
import re, hashlib
MIN_TITLE_WORDS = 5; PREFIX_CHARS = 300; MIN_BODY = 100; GENERIC_PREFIXES = 3; MIRROR_RULE = True; KINDS = ("first", "copy", "republished", "generic_title", "no_key"); ROOT_KINDS = ("first", "generic_title", "no_key")
def norm(s): return re.sub(r"\s+", " ", (s or "").lower()).strip()
def sha1(s): return hashlib.sha1(s.encode()).hexdigest()
def story_keys(title, body):
    t = norm(title); b = norm(body)
    return {"title": sha1(t) if len(t.split()) >= MIN_TITLE_WORDS else None, "prefix": sha1(b[:PREFIX_CHARS]) if len(b) >= MIN_BODY else None}
def new_index(): return {"t": {}, "p": {}, "story": {}, "tp": {}, "pt": {}, "generic": set(), "generic_p": set()}   # t, p: key -> root seq; story: root seq -> set of sources; tp: (source, title key) -> prefix keys; pt: (source, prefix key) -> title keys; generic, generic_p: title keys that are column names, prefix keys that are page boilerplate
def classify(idx, keys, source, seq):
    t, p = keys.get("title"), keys.get("prefix")
    if t and p:   # the same title from one source over 3 different bodies is a column name ("business daily"), not a story key (c1)
        s = idx["tp"].setdefault((source, t), set()); s.add(p)
        if len(s) >= GENERIC_PREFIXES: idx["generic"].add(t)
        if MIRROR_RULE:   # candidate rule, not in the spec, off until the owner decides (see docstring)
            r = idx["pt"].setdefault((source, p), set()); r.add(t)
            if len(r) >= GENERIC_PREFIXES: idx["generic_p"].add(p)
    title_off = t is None or t in idx["generic"]; t = None if title_off else t; p = None if p in idx["generic_p"] else p
    hits = [idx[k][v] for k, v in (("t", t), ("p", p)) if v and v in idx[k]]
    if hits:
        root = min(hits); S = idx["story"][root]; kind = "republished" if source in S else "copy"; S.add(source)
        if t: idx["t"].setdefault(t, root)
        if p: idx["p"].setdefault(p, root)
        return {"kind": kind, "of_seq": root, "publishers": len(S), "keys": {"title": t, "prefix": p}}
    if t is None and p is None: kind = "no_key"
    else:
        kind = "generic_title" if title_off else "first"; idx["story"][seq] = {source}
        if t: idx["t"][t] = seq
        if p: idx["p"][p] = seq
    return {"kind": kind, "of_seq": None, "publishers": 1, "keys": {"title": t, "prefix": p}}
def replay(items):
    idx = new_index(); return [classify(idx, story_keys(ti, bo), so, sq) for sq, ti, bo, so in items]
# --- durable journal (plan step 1, add-only; nothing above changed) ---
# classify() keeps the index in memory for one run. Durable keeps it across runs: an append-only JSONL log (one line per item: story key, run_id, label_version), reloaded by replaying classify() over the raw keys in log order, so a fresh process rebuilds the same index.
# An item that is already in the log (same item_id) is never counted again: re-adding it, in the same run or another, returns its first result and writes nothing. day_table() sums the log by day and counts each story once (copies are listed apart).
import os, json
class Durable:
    """Durable(path): path is a .jsonl file (e.g. runs/journal/journal.jsonl). add() classifies, appends and returns classify()'s dict (plus item_id and replayed=True when the item was already logged)."""
    def __init__(self, path):
        self.path = path; self.idx = new_index(); self.seen = {}; self.rows = []
        if os.path.exists(path):
            for l in open(path, encoding="utf-8"):
                if not l.strip(): continue
                r = json.loads(l)
                if r["item_id"] in self.seen: continue
                d = classify(self.idx, r["raw_keys"], r["source"], r["gseq"]); self.seen[r["item_id"]] = r; self.rows.append(r)
    def add(self, item_id, keys, source, seq, run_id, label_version, day=None):
        if item_id in self.seen:
            r = self.seen[item_id]; return {"kind": r["kind"], "of_seq": r["of_seq"], "publishers": r["publishers"], "keys": r["keys"], "item_id": item_id, "replayed": True}
        g = len(self.rows); d = classify(self.idx, keys, source, g)   # roots are numbered by position in the log (gseq), because run seq restarts at 0 in every run; of_seq in the result is a gseq
        r = {"item_id": item_id, "story": d["keys"].get("title") or d["keys"].get("prefix") or (keys.get("title") or keys.get("prefix")), "run_id": run_id, "label_version": label_version, "seq": seq, "gseq": g, "source": source, "day": day,
             "raw_keys": keys, "kind": d["kind"], "of_seq": d["of_seq"], "publishers": d["publishers"], "keys": d["keys"]}
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f: f.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        self.seen[item_id] = r; self.rows.append(r); return {**d, "item_id": item_id, "replayed": False}
    def day_table(self): return day_table(self.rows)
def day_table(rows):
    """rows (the log lines, one per item) -> {day: {items, stories, copies, republished, generic_title, no_key, runs}}; stories = root items (first, generic_title, no_key), so a syndicated copy never adds a story."""
    out = {}
    for r in rows:
        t = out.setdefault(r.get("day") or "unknown", {"items": 0, "stories": 0, "copies": 0, "republished": 0, "generic_title": 0, "no_key": 0, "runs": []})
        t["items"] += 1; t["stories"] += r["kind"] in ROOT_KINDS
        if r["kind"] in ("copy", "republished", "generic_title", "no_key"): t["copies" if r["kind"] == "copy" else r["kind"]] += 1
        if r["run_id"] not in t["runs"]: t["runs"].append(r["run_id"])
    return dict(sorted(out.items()))
# --- end durable journal ---
