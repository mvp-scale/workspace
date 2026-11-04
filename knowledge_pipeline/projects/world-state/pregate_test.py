"""Pre-gate test: do cheap up-front signals (URL section words, headline cues) find the rare story types? Stdlib only. Target = Haiku story_type (noisy proxy). Prediction: ledger."""
import json, re, glob, collections
pool = {}
for l in open("data/pool_train.jsonl", encoding="utf-8"):
    r = json.loads(l); pool[r["id"]] = r
H = {}
for f in glob.glob("runs/p7/*/labels.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); H[r["item_id"]] = r["label"]["story_type"]
ids = [i for i in H if i in pool]; N = len(ids)
SEC_OP = re.compile(r"/(opinions?|comments?|commentary|editorials?|analysis|columns?|columnists?|viewpoints?|views|blogs?|voices|perspectives?|op-?ed|forum|letters?|insight|ideas)(/|-|\.|$)", re.I)
SEC_FC = re.compile(r"/(forecasts?|outlook|preview|predictions?)(/|-|\.|$)", re.I)
HL = lambda t: re.split(r"(?<=[.!?])\s", t, 1)[0]
OPH = re.compile(r"^(opinion|analysis|editorial|comment|column|commentary|view|perspective|why|how)\b|\b(should|must|we need|needs to|time to|let's)\b|\?\s*$", re.I)
FCH = re.compile(r"\b(will|expected to|forecast|predict\w*|set to|projected|outlook|likely to|could|to rise|to fall|plans? to|aims? to)\b", re.I)
SIG = {"url_section_opinion": lambda i, t: bool(SEC_OP.search(i)) if i.startswith("cc:") else None,
       "url_section_forecast": lambda i, t: bool(SEC_FC.search(i)) if i.startswith("cc:") else None,
       "headline_opinion_cue": lambda i, t: bool(OPH.search(HL(t))),
       "headline_forecast_cue": lambda i, t: bool(FCH.search(HL(t)))}
TARGET = {"url_section_opinion": "opinion", "url_section_forecast": "forecast", "headline_opinion_cue": "opinion", "headline_forecast_cue": "forecast"}
base = collections.Counter(H[i] for i in ids); out = {"n": N, "base": {k: round(v / N, 4) for k, v in base.items()}, "signals": {}}
flag = collections.defaultdict(set)
for name, fn in SIG.items():
    scope = [i for i in ids if fn(i, pool[i]["text"]) is not None]; hit = [i for i in scope if fn(i, pool[i]["text"])]; cls = TARGET[name]
    tp = sum(H[i] == cls for i in hit); pool_cls = sum(H[i] == cls for i in scope)
    out["signals"][name] = {"scope": len(scope), "flagged": len(hit), "coverage": round(len(hit) / len(scope), 4), "precision": round(tp / len(hit), 3) if hit else None,
                            "recall": round(tp / pool_cls, 3) if pool_cls else None, "lift": round((tp / len(hit)) / (pool_cls / len(scope)), 2) if hit and pool_cls else None}
    flag[cls] |= set(hit)
for cls in ("opinion", "forecast"):
    hit = flag[cls]; tp = sum(H[i] == cls for i in hit); tot = base[cls]
    out["or_gate_" + cls] = {"flagged_share": round(len(hit) / N, 4), "precision": round(tp / len(hit), 3), "recall": round(tp / tot, 3), "lift": round((tp / len(hit)) / (tot / N), 2),
                             "cost_cut_if_label_only_flagged": round(N / len(hit), 2)}
json.dump(out, open("runs/pulse/pregate_test.json", "w"), indent=1); print(json.dumps(out, indent=1))
