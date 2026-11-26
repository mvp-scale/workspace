"""developments_history: append-only history of developments across cuts (round D, playbook 00.1; spec plan-tactical-strategic.md:162).
append(result, root, window_label) -> paths: for every development of a developments_v0.build() result, one entry is appended to
<root>/history/<id with ':' -> '-'>.json (a JSON list, earlier entries never rewritten). No timestamps: the same result appended to two roots gives byte-identical files.
load(root, dev_id) -> the list of entries (oldest first), [] when none. Pure file IO, no model, no network."""
import os, json

def _fname(dev_id): return dev_id.replace(":", "-") + ".json"

def _path(root, dev_id): return os.path.join(root, "history", _fname(dev_id))

def _owners(d):
    names = set()
    for k in d.get("know") or []: names.update(k.get("owner_names") or [])
    for s in (d.get("expect") or {}).get("statements") or []:
        if s.get("owner"): names.add(s["owner"])
    return sorted(names)

def _entry(d, result, window_label, prev_id):
    know = [{"id": k.get("id"), "quote": k.get("quote"), "certainty_word": k.get("certainty_word"), "owners": k.get("owners"), "articles": k.get("articles")} for k in d.get("know") or []]
    fwd = [{"quote": s.get("quote"), "article_id": s.get("article_id"), "assertion_id": s.get("assertion_id"), "speaker": s.get("speaker"), "owner": s.get("owner"), "new": s.get("new")} for s in (d.get("expect") or {}).get("statements") or []]
    arts = [m.get("id") for m in d.get("members") or []]
    return {"window": window_label, "cut_seq": (result.get("cut") or {}).get("seq"), "articles": arts, "n_articles": len(arts), "owners": _owners(d),
            "certainty_word": d.get("certainty_word"), "thin": bool(d.get("thin")), "assertions": know, "forward": fwd, "prev_id": prev_id}

def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f: f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1))
    os.replace(tmp, path)

def load(root, dev_id):
    p = _path(root, dev_id)
    return json.load(open(p)) if os.path.exists(p) else []

def append(result, root, window_label):
    """one entry per development (non-thin then thin, as the result lists them); returns the history file paths in that order"""
    carry = result.get("carry") or {}     # developments_v0.carry_ids rows [{new_id, prev_id, ...}] when the id rule ran (or a {new: prev} dict); missing -> prev_id null
    if isinstance(carry, list): carry = {c["new_id"]: c["prev_id"] for c in carry}
    out = []
    for d in (result.get("developments") or []) + (result.get("thin") or []):
        entry = _entry(d, result, window_label, carry.get(d["id"]) if isinstance(carry, dict) else None)
        hist = load(root, d["id"]); hist.append(entry)
        _write(_path(root, d["id"]), hist); out.append(_path(root, d["id"]))
    return out
