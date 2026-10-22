"""Open topic phrases from headline + description, CPU only (T-0014): spaCy noun chunks and named entities, no ontology.

Places and people are left out (country has its own rule, D-0015; names say little about topic).
  models/nlp-venv/bin/python newsreader/bitmob/topic_phrases.py <in.jsonl> <out.jsonl>
"""
import json, sys, time
import spacy

SKIP_ENT = {"GPE", "LOC", "PERSON", "NORP", "DATE", "TIME", "CARDINAL", "ORDINAL", "PERCENT", "MONEY", "QUANTITY"}
STOP_HEAD = {"it", "they", "he", "she", "we", "you", "i", "who", "that", "this", "which", "what", "one", "year", "day", "week", "time", "people"}


def phrases(doc, where):
    out, seen = [], set()
    for e in doc.ents:
        if e.label_ not in SKIP_ENT and e.text.lower() not in seen: seen.add(e.text.lower()); out.append({"text": e.text, "where": where, "kind": e.label_})
    for c in doc.noun_chunks:
        t = " ".join(w.text for w in c if w.pos_ not in ("DET", "PRON") and not w.is_punct).strip()
        if not t or c.root.lemma_.lower() in STOP_HEAD or c.root.ent_type_ in ("GPE", "PERSON", "LOC") or t.lower() in seen: continue
        seen.add(t.lower()); out.append({"text": t, "where": where, "kind": "chunk"})
    return out


def main(src, dst):
    nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"])
    rows = [json.loads(l) for l in open(src)]; t0 = time.perf_counter()
    heads = nlp.pipe([r["title"] for r in rows], batch_size=256); descs = nlp.pipe([(r.get("description") or "")[:250] for r in rows], batch_size=256)
    with open(dst, "w") as f:
        for r, h, d in zip(rows, heads, descs):
            f.write(json.dumps({"id": r["id"], "phrases": phrases(h, "headline") + phrases(d, "description")}, ensure_ascii=False) + "\n")
    print(f"{len(rows)} stories, {1000 * (time.perf_counter() - t0) / len(rows):.1f} ms/story -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
