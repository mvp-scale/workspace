#!/usr/bin/env python3
"""Turns PLAN.md into the dashboard's data files (view_data/*.json). PLAN.md is the only source; run this at the end of every phase.
    python3 -I view.py            write view_data/{phases,blockers,decisions,layers,money}.json
Progress comes from the 'Status' column of the phase table and from `Actual:` lines you add under a phase."""
import json, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent; OUT = HERE / "view_data"; OUT.mkdir(exist_ok=True)
T = (HERE / "PLAN.md").read_text(encoding="utf-8")
clean = lambda s: re.sub(r"\s+", " ", re.sub(r"[`*]", "", s)).strip()

def section(title):
    m = re.search(r"^## " + re.escape(title) + r".*?$", T, re.M)
    if not m: return ""
    n = re.search(r"^## ", T[m.end():], re.M)
    return T[m.end(): m.end() + n.start()] if n else T[m.end():]

def table(text):
    rows = [l for l in text.splitlines() if l.startswith("|")]
    rows = [[c.strip() for c in r.strip("|").split("|")] for r in rows if not re.match(r"^\|\s*-", r)]
    return rows[0], rows[1:]

# ---- phases: table on the first page + the per-phase sections
head, body = table(section("The plan on one page"))
phases = []
for r in body:
    m = re.match(r"(P\d+)\s+(.*)", r[0]); 
    if not m: continue
    phases.append({"id": m.group(1), "name": clean(m.group(2)), "owner": clean(r[1]), "cost": clean(r[2]), "gate": clean(r[3]), "status": clean(r[4])})
blocks = {m.group(1): m.group(0) for m in re.finditer(r"^### (P\d+) .*?(?=^### P|^## )", T, re.M | re.S)}
KEYS = r"Goal|Entry|Steps|Exit|Caps|Stop|Rollback|Predict(?: \(p [0-9.]+\))?|Score|Learn|Actual|Added 2026-10-29|Updated 2026-10-29(?: \([^)]*\))?|Comparison set in advance[^:]*"
for p in phases:
    b = blocks.get(p["id"], "")
    b = re.sub(r"^### .*\n", "", b, count=1)
    parts = re.split(r"(?:(?<=\s)|^)(?:- )?(" + KEYS + r"):\s", b)
    f = {}
    for i in range(1, len(parts) - 1, 2): f.setdefault(re.sub(r" \(.*", "", parts[i]).split()[0], []).append(clean(parts[i + 1]).rstrip("-").strip())
    j = lambda k: " ".join(f.get(k, [])) or ""
    p["situation"] = j("Entry") or ("Starts the project." if p["id"] == "P0" else "Runs after the phases before it.")
    p["task"] = j("Goal") or clean(re.split(r"\n- ", b.strip())[0].lstrip("- "))[:240]
    p["action"] = j("Steps") or clean(b)[:300]
    p["result"] = " ".join(x for x in [j("Exit"), ("Prediction: " + j("Predict")) if j("Predict") else ""] if x)
    p["result"] = p["result"] or "Conditional: only runs if its trigger fires."
    p["predict"] = j("Predict"); p["actual"] = j("Actual"); p["stop"] = j("Stop"); p["rollback"] = j("Rollback"); p["learn"] = j("Learn")

# ---- blockers
h, rows = table(section("Blockers"))
blockers = [{"n": int(r[0]), "blocker": clean(r[1]), "blocks": clean(r[2]), "who": clean(r[3]), "status": clean(r[4])} for r in rows]
# ---- layers
h, rows = table(section("Layers"))
layers = [{"layer": clean(r[0]), "does": clean(r[1]), "built_from": clean(r[2])} for r in rows]
# ---- decisions
decisions = []
for m in re.finditer(r"^(\d+)\. (.*?)(?=^\d+\. |\Z)", section("Owner decisions"), re.M | re.S):
    t = clean(m.group(2)); state = "assumed" if re.search(r"\bAssumed\b", t) else "answered"
    decisions.append({"n": int(m.group(1)), "decision": re.sub(r"\s*(Answered\.|Assumed\.?.*|From owner's message\.)$", "", t).strip(), "state": state})
# ---- money, from the 'Money' paragraph on the first page
mp = re.search(r"\*\*Money.*?\*\*(.*?)\*\*Kaggle GPU", section("The plan on one page"), re.S).group(1)
money = []
for m in re.finditer(r"(?:^|[:,]\s*)(?:and )?([A-Za-z0-9 ./-]+?(?: \([^)]*\))?) \$([0-9.]+)", clean(mp)):
    label = m.group(1).strip(" ,"); 
    if not label.lower().startswith(("planned", "reserve")): money.append({"line": label, "usd": float(m.group(2)), "kind": "planned"})
res = re.search(r"Reserve \$([0-9.]+)", clean(mp)); money.append({"line": "Reserve, locked", "usd": float(res.group(1)), "kind": "reserve"})
for name, rows_ in (("phases", phases), ("blockers", blockers), ("decisions", decisions), ("layers", layers), ("money", money)):
    (OUT / f"{name}.json").write_text(json.dumps(rows_, ensure_ascii=False, indent=1), encoding="utf-8")
    print(name, len(rows_))

# ---- confidence (MM3 passes, recorded by hand in mm3_scores.json after each MM3 run on the phases)
sf = HERE / "mm3_scores.json"
if sf.exists():
    S = json.loads(sf.read_text(encoding="utf-8")); QS = S["questions"]; LOW = set(S["good_if_low"])
    grp = lambda o: "Owner or people" if o.lower().startswith("owner") else ("Claude, owner approves" if ("approves" in o.lower() or "signs" in o.lower()) else "Claude alone")
    avg = lambda xs: sum(xs) / len(xs)
    def parts(q):
        g = [(1 - x) if (i + 1) in LOW else x for i, x in enumerate(q)]
        cl, ev, sa = avg(g[0:3]), avg(g[3:6]), avg(g[6:9]); return cl, ev, sa, avg([cl, ev, sa]), g
    pinfo = {p["id"]: p for p in phases}; hist = []; conf_rows = []; prev_scores = {}
    for ps in S["passes"]:
        sc = {k: parts(v["q"]) for k, v in ps["phases"].items()}
        half1 = [k for k in sc if int(k[1:]) <= 6]; half2 = [k for k in sc if int(k[1:]) > 6]
        pct = lambda x: round(x * 100)
        hist.append({"pass": ps["pass"], "date": ps["date"], "overall": pct(avg([v[3] for v in sc.values()])), "first_half": pct(avg([sc[k][3] for k in half1])), "second_half": pct(avg([sc[k][3] for k in half2])),
                     "clarity": pct(avg([v[0] for v in sc.values()])), "evidence": pct(avg([v[1] for v in sc.values()])), "safety": pct(avg([v[2] for v in sc.values()])), "note": ps["note"]})
        conf_rows = []
        for k, v in ps["phases"].items():
            cl, ev, sa, tot, g = sc[k]; weakest = min((("Clarity", cl), ("Evidence", ev), ("Safety", sa)), key=lambda t: t[1])[0]
            ch = "" if k not in prev_scores else f"{pct(tot) - pct(prev_scores[k]):+d}"
            conf_rows.append({"id": k, "name": pinfo.get(k, {}).get("name", ""), "score": pct(tot), "clarity": pct(cl), "evidence": pct(ev), "safety": pct(sa), "weakest": weakest,
                              "route": v["route"][0].replace("-", " "), "mm3": v["mm3"], "change": ch})
        prev_scores = {k: v[3] for k, v in sc.items()}
    last = S["passes"][-1]; sc = {k: parts(v["q"]) for k, v in last["phases"].items()}
    slices = []
    def add_slice(kind, label, keys):
        slices.append({"slice": kind, "label": label, "phases": len(keys), "score": pct(avg([sc[k][3] for k in keys])), "clarity": pct(avg([sc[k][0] for k in keys])), "evidence": pct(avg([sc[k][1] for k in keys])), "safety": pct(avg([sc[k][2] for k in keys]))})
    add_slice("Half", "First half, P0 to P6", [k for k in sc if int(k[1:]) <= 6]); add_slice("Half", "Second half, P7 to P12", [k for k in sc if int(k[1:]) > 6])
    for g_ in ("Claude alone", "Claude, owner approves", "Owner or people"):
        ks = [k for k in sc if grp(pinfo[k]["owner"]) == g_]
        if ks: add_slice("Owner", g_, ks)
    kinds = ["Clarity"] * 3 + ["Evidence"] * 3 + ["Safety"] * 3
    doubts = [{"question": QS[i], "kind": kinds[i], "average": pct(avg([parts(v["q"])[4][i] for v in last["phases"].values()]))} for i in range(9)]
    for name, rows_ in (("confidence", conf_rows), ("slices", slices), ("doubts", doubts), ("history", hist)):
        (OUT / f"{name}.json").write_text(json.dumps(rows_, ensure_ascii=False, indent=1), encoding="utf-8"); print(name, len(rows_))
