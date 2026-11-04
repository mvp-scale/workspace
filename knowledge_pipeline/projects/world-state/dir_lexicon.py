"""Direction by change-word lexicon (CPU, deterministic). Counts rise-words vs fall-words in the item; compares with the direction both models agree on."""
import json, re, glob, pathlib
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
UP = r"\b(ris(?:e|es|ing)|rose|risen|increas\w*|surg\w*|climb\w*|soar\w*|jump\w*|spik\w*|hik\w*|grow\w*|grew|higher|worsen\w*|escalat\w*|mount\w*|expand\w*|boost\w*|more|swell\w*|record high|up)\b"
DN = r"\b(fall\w*|fell|drop\w*|declin\w*|decreas\w*|plung\w*|slump\w*|cut\w*|reduc\w*|lower\w*|eas(?:e|es|ed|ing)|shrink\w*|shrank|dip\w*|tumbl\w*|slash\w*|fewer|less|down|improv\w*|recover\w*)\b"
H = {}; S = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): S[r["item_id"]] = r["label"]
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; ok = n = cov = tot = 0; byc = {}
for i in H:
    if i not in S: continue
    hh = {x["condition"]: x["direction"] for x in H[i]["conditions"]}; ss = {x["condition"]: x["direction"] for x in S[i]["conditions"]}
    t = pool[i].lower(); sc = len(re.findall(UP, t)) - len(re.findall(DN, t))
    for c in hh:
        if c in ss and hh[c] == ss[c]:
            tot += 1
            if sc != 0: cov += 1; hit = (sc > 0) == (hh[c] == "up"); ok += hit; n += 1; byc.setdefault(hh[c], [0, 0]); byc[hh[c]][0] += 1; byc[hh[c]][1] += hit
print(f"agreed-direction cases {tot}; lexicon has an opinion on {cov} ({cov/tot:.0%}); accuracy where it has one {ok/n:.3f}"); print({k: f"{v[1]}/{v[0]} = {v[1]/v[0]:.2f}" for k, v in byc.items()}); print("balanced accuracy", round(sum(v[1] / v[0] for v in byc.values()) / len(byc), 3))
