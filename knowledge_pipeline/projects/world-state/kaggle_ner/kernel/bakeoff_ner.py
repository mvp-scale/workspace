"""T67: entity extractor bake-off on Few-NERD (CC BY-SA 4.0) 1,000-sentence sample. Type-agnostic span F1, exact and IoU>=0.5. Each system in its own try/except.
    SYSTEMS=spacy_sm,spacy_trf,stanza,gliner N=1000 DATA=<sample1k.jsonl> OUT=<dir> python bakeoff_ner.py"""
import os, sys, json, time, subprocess
DATA = os.environ.get("DATA", "/kaggle/input/kp-fewnerd-1k/sample1k.jsonl"); OUT = os.environ.get("OUT", "/kaggle/working"); N = int(os.environ.get("N", "1000"))
SYSTEMS = os.environ.get("SYSTEMS", "spacy_trf,gliner").split(",")
import glob
if not os.path.exists(DATA):
    hit = glob.glob("/kaggle/input/**/sample1k.jsonl", recursive=True); DATA = hit[0] if hit else DATA
print("DATA", DATA, flush=True)
if os.environ.get("CHILD") != "1" and len(SYSTEMS) > 1:
    merged = {"systems": {}}
    for sy in SYSTEMS:
        env = dict(os.environ, CHILD="1", SYSTEMS=sy, OUT=OUT, ONLY_FILE="ner_bakeoff_" + sy + ".json")
        subprocess.run([sys.executable, __file__], env=env)
        try: part = json.load(open(os.path.join(OUT, "ner_bakeoff_" + sy + ".json"))); merged.update({k: v for k, v in part.items() if k != "systems"}); merged["systems"].update(part["systems"])
        except Exception as ex: merged["systems"][sy] = {"error": "child gave no result: " + repr(ex)[:200]}
        json.dump(merged, open(os.path.join(OUT, "ner_bakeoff.json"), "w"), indent=1)
    print(json.dumps(merged["systems"], indent=1)); sys.exit(0)
rows = [json.loads(l) for l in open(DATA)][:N]
texts, gold = [], []
for r in rows:
    offs, pos, parts = [], 0, []
    for t in r["tokens"]:
        offs.append((pos, pos + len(t))); pos += len(t) + 1; parts.append(t)
    texts.append(" ".join(parts)); gold.append({(offs[s][0], offs[e - 1][1]) for s, e, _ in r["spans"]})
def pip(*a): subprocess.run([sys.executable, "-m", "pip", "install", "-q", *a], check=True)
def sp_run(model):
    import spacy
    nlp = spacy.load(model); return [{(e.start_char, e.end_char) for e in d.ents} for d in nlp.pipe(texts, batch_size=64)]
def run_system(name):
    if name == "spacy_sm":
        try: import spacy; spacy.load("en_core_web_sm")
        except Exception: pip("spacy"); subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
        return sp_run("en_core_web_sm")
    if name == "spacy_trf":
        pip("spacy[transformers]", "spacy-curated-transformers"); subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_trf"], check=True)
        return sp_run("en_core_web_trf")
    if name == "stanza":
        pip("stanza"); import stanza; stanza.download("en", processors="tokenize,ner", verbose=False)
        nlp = stanza.Pipeline("en", processors="tokenize,ner", tokenize_no_ssplit=True, verbose=False, use_gpu=False)
        return [{(e.start_char, e.end_char) for e in nlp(t).ents} for t in texts]
    if name == "gliner":
        pip("gliner", "transformers>=4.51,<5"); from gliner import GLiNER
        m = GLiNER.from_pretrained("urchade/gliner_medium-v2.1"); lab = ["person", "organization", "location", "event", "product", "building", "art work", "other entity"]
        return [{(e["start"], e["end"]) for e in m.predict_entities(t, lab, threshold=0.5)} for t in texts]
    raise ValueError(name)
def f1(pred, gold, iou):
    tp = np_ = ng = 0
    for P, G in zip(pred, gold):
        np_ += len(P); ng += len(G); used = set()
        for p in P:
            for g in G:
                if g in used: continue
                inter = max(0, min(p[1], g[1]) - max(p[0], g[0]))
                u = (p[1] - p[0]) + (g[1] - g[0]) - inter
                if (iou == 1 and p == g) or (iou < 1 and u and inter / u >= iou): tp += 1; used.add(g); break
    pr = tp / max(1, np_); rc = tp / max(1, ng); return round(2 * pr * rc / max(1e-9, pr + rc), 4), round(pr, 4), round(rc, 4)
res = {"sentences": len(texts), "gold_spans": sum(len(g) for g in gold), "note": "Few-NERD is Wikipedia text; type ignored; adjacent same-type entities are merged in the gold", "systems": {}}
for s in SYSTEMS:
    t0 = time.time()
    try:
        pred = run_system(s); dt = time.time() - t0
        e = f1(pred, gold, 1); o = f1(pred, gold, 0.5)
        res["systems"][s] = {"exact_f1": e[0], "exact_p": e[1], "exact_r": e[2], "iou50_f1": o[0], "pred_spans": sum(len(p) for p in pred), "seconds_total_incl_setup": round(dt, 1)}
    except Exception as ex: res["systems"][s] = {"error": repr(ex)[:300]}
    print(s, res["systems"][s], flush=True)
    json.dump(res, open(os.path.join(OUT, os.environ.get("ONLY_FILE", "ner_bakeoff.json")), "w"), indent=1)
