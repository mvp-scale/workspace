"""CPU candidates first (teacher v3 pattern, pipeline/kaggle/teacher/cpu_candidates_v3.py): cheap proposers find
candidate spans; the teacher only labels each candidate id (verify / type / reject) and adds what none covers. Prompts
reference ids, so replies are short, offsets come from the text (never from the model) and recall is auditable.

Proposer plug-in: any object with .name, .layer and .propose(text) -> iterable of (start, end, hints dict).
Built in: RegexProposer, DictionaryProposer, SpacyProposer (spaCy imported lazily; optional).
Spec block: "candidates": [{"type": "regex", "layer": "EVENT", "patterns": ["\\\\b\\\\w+ed\\\\b"]},
                           {"type": "dictionary", "layer": "ENTITY", "terms": ["ministry"], "hints": {"t": "ORG"}},
                           {"type": "spacy", "layer": "ENTITY", "model": "en_core_web_sm", "ents": ["PERSON", "ORG"]}]

    python candidates.py --spec SPEC --items items.jsonl --out cands.jsonl
Output rows {id, text_sha256, candidates: [{id, layer, start, end, text, src, hints}]}. Candidates quote item text:
keep the file private like the items (publisher text never leaves the project).
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class RegexProposer:
    def __init__(self, layer, patterns, name="regex", flags="", hints=None, group=0):
        self.layer, self.name, self.hints, self.group = layer, name, hints or {}, group
        f = re.IGNORECASE if "i" in flags else 0
        self.rx = [re.compile(p, f) for p in patterns]

    def propose(self, text):
        for rx in self.rx:
            for m in rx.finditer(text):
                if m.end(self.group) > m.start(self.group):
                    yield m.start(self.group), m.end(self.group), dict(self.hints)


class DictionaryProposer:
    """Whole-word, longest-first term matches."""

    def __init__(self, layer, terms, name="dict", case=False, hints=None):
        self.layer, self.name, self.hints = layer, name, hints or {}
        alt = "|".join(re.escape(t) for t in sorted(set(terms), key=len, reverse=True))
        self.rx = re.compile(rf"(?<!\w)(?:{alt})(?!\w)", 0 if case else re.IGNORECASE) if terms else None

    def propose(self, text):
        if self.rx:
            for m in self.rx.finditer(text):
                yield m.start(), m.end(), dict(self.hints)


class SpacyProposer:
    """spaCy NER entities (ents) and/or tokens by POS (pos) and/or noun chunks. Needs spaCy + the model installed."""

    def __init__(self, layer, model="en_core_web_sm", ents=None, pos=None, noun_chunks=False, name="spacy"):
        self.layer, self.name, self.model = layer, name, model
        self.ents, self.pos, self.chunks, self._nlp = ents, pos, noun_chunks, None

    def propose(self, text):
        if self._nlp is None:
            import spacy  # optional dependency
            self._nlp = spacy.load(self.model)
        doc = self._nlp(text)
        if self.ents is not None:
            for e in doc.ents:
                if not self.ents or e.label_ in self.ents:
                    yield e.start_char, e.end_char, {"ner": e.label_}
        if self.pos:
            for t in doc:
                if t.pos_ in self.pos:
                    yield t.idx, t.idx + len(t.text), {"pos": t.pos_}
        if self.chunks:
            for c in doc.noun_chunks:
                yield c.start_char, c.end_char, {"np": 1}


KINDS = {"regex": RegexProposer, "dictionary": DictionaryProposer, "spacy": SpacyProposer}


def from_config(cfg):
    out = []
    for c in cfg:
        c = dict(c)
        kind = c.pop("type")
        if kind not in KINDS:
            raise ValueError(f"unknown proposer type {kind!r} (have {sorted(KINDS)})")
        out.append(KINDS[kind](**c))
    return out


def propose(text, proposers):
    """Run every proposer, merge identical (layer, start, end) spans (src = voters, hints merged), ids c1..cN in
    text order."""
    by = {}
    for p in proposers:
        for s, e, h in p.propose(text):
            k = (p.layer, s, e)
            c = by.setdefault(k, {"layer": p.layer, "start": s, "end": e, "text": text[s:e], "src": [], "hints": {}})
            if p.name not in c["src"]:
                c["src"].append(p.name)
            c["hints"].update(h or {})
    out = sorted(by.values(), key=lambda c: (c["start"], -c["end"], c["layer"]))
    for i, c in enumerate(out, 1):
        c["id"] = f"c{i}"
    return out


def render(cands):
    """Prompt lines: id [LAYER] "text" (hints). The model answers by id."""
    lines = []
    for c in cands:
        h = ", ".join(f"{k}={v}" for k, v in sorted((c.get("hints") or {}).items()))
        lines.append(f'{c["id"]} [{c["layer"]}] {json.dumps(c["text"], ensure_ascii=False)}' + (f" ({h})" if h else ""))
    return "\n".join(lines)


def verify_schema(cands, labels, max_add=10):
    """Reply schema: one code for EVERY candidate id (enum of its layer's codes) + additions. Closed objects."""
    layers = sorted(labels)
    union = sorted({x for v in labels.values() for x in v})
    return {"type": "object", "additionalProperties": False, "required": ["d", "add"], "properties": {
        "d": {"type": "object", "additionalProperties": False, "required": [c["id"] for c in cands],
              "properties": {c["id"]: {"type": "string", "enum": list(labels[c["layer"]])} for c in cands}},
        "add": {"type": "array", "maxItems": max_add, "items": {
            "type": "object", "additionalProperties": False, "required": ["layer", "text", "label"],
            "properties": {"layer": {"type": "string", "enum": layers}, "text": {"type": "string"},
                           "label": {"type": "string", "enum": union}}}}}}


def locate(text, t, taken=(), case=True):
    """First occurrence of t in text not already taken (exact, then case-insensitive). -> (start, end) or None."""
    if not t:
        return None
    hay, needle = (text, t) if case else (text.lower(), t.lower())
    i = hay.find(needle)
    while i >= 0:
        if (i, i + len(t)) not in taken:
            return i, i + len(t)
        i = hay.find(needle, i + 1)
    return locate(text, t, taken, False) if case else None


def assemble(text, cands, reply, reject=("X", "N")):
    """Verify reply + candidates -> {"spans": [...]} with offsets from the text; adds located in the text.
    -> (label, stats). Unlocatable adds are dropped and counted."""
    dec, spans, taken = reply.get("d", {}), [], set()
    for c in cands:
        code = dec.get(c["id"])
        if code is None or code in reject:
            continue
        spans.append({"layer": c["layer"], "start": c["start"], "end": c["end"], "text": c["text"], "label": code,
                      "src": "cand"})
        taken.add((c["start"], c["end"]))
    lost = 0
    for a in reply.get("add", []):
        if a.get("label") in reject:
            continue
        pos = locate(text, a.get("text", ""), taken)
        if pos is None:
            lost += 1
            continue
        taken.add(pos)
        spans.append({"layer": a["layer"], "start": pos[0], "end": pos[1], "text": text[pos[0]:pos[1]],
                      "label": a["label"], "src": "add"})
    spans.sort(key=lambda s: (s["start"], s["end"]))
    return {"spans": spans}, {"n_cands": len(cands), "n_keep": sum(s["src"] == "cand" for s in spans),
                              "n_add": sum(s["src"] == "add" for s in spans), "add_unlocated": lost}


def locate_spans(text, reply):
    """Generate mode: reply spans without offsets get start/end from the text (unlocatable ones dropped)."""
    out, taken, lost = [], set(), 0
    for s in reply.get("spans", []):
        if "start" in s and "end" in s:
            out.append(s)
            continue
        pos = locate(text, s.get("text", ""), taken)
        if pos is None:
            lost += 1
            continue
        taken.add(pos)
        out.append({**s, "start": pos[0], "end": pos[1], "text": text[pos[0]:pos[1]], "src": "gen"})
    return {**reply, "spans": out}, {"unlocated": lost}


def main(argv=None):
    import task_spec
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--items", required=True, help="JSONL {id, text}")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    spec = task_spec.load(a.spec)
    P = from_config(spec.candidates)
    if not P:
        raise SystemExit("spec has no candidates block")
    n = nc = 0
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.items, encoding="utf-8") as f, open(out, "w", encoding="utf-8") as w:
        for line in f:
            if not line.strip():
                continue
            it = json.loads(line)
            C = propose(it["text"], P)
            w.write(json.dumps({"id": it["id"], "text_sha256": hashlib.sha256(it["text"].encode("utf-8")).hexdigest(),
                                "candidates": C}, ensure_ascii=False) + "\n")
            n, nc = n + 1, nc + len(C)
    print(f"{n} items, {nc} candidates ({nc / max(n, 1):.1f}/item) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
