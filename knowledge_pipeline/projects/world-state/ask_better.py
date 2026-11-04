#!/usr/bin/env python3
"""Does asking narrower questions fix Clef/Jev 'anything changing'? Old: one long compound question. New: 3 narrow yes/no questions (probe rules: one judgment each,
positive wording, a 'cannot tell' option); change = at least 2 of 3 say yes. Scored on gold-Q (50 items) against Haiku/Sonnet agreement."""
import json, sys, pathlib
sys.path.insert(0, "/workspace/demo"); import backends
HERE = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
YN = lambda q: {"type": "choice", "instructions": q, "criteria": {"yes": "Yes, the item says this", "no": "No, the item does not say this", "cannot_tell": "The item is too short or vague to tell"}}
NEW = {"a_number": YN("Does the item say a price, rate, amount or level went up or down?"),
       "b_effect": YN("Does the item report a shortage, harm, disruption or relief affecting people in a place?"),
       "c_lasting": YN("Does the item report an effect that lasts beyond the single event it describes?")}
rows = J(HERE / "gold/q50_jury.jsonl"); out = {}
for bid, name in (("clef-flash-q4km", "clef"), ("jev", "jev")):
    for r in rows:
        v = {k: backends.ask(bid, "News item:\n" + r["text"], {k: q}, timeout=90)[k]["choice"] for k, q in NEW.items()}
        out.setdefault(r["id"], {})[name] = {"votes": v, "change": sum(x == "yes" for x in v.values()) >= 2, "any": any(x == "yes" for x in v.values())}
json.dump(out, open(HERE / "runs/p1/ask_better.json", "w"))
H = [r["raters"]["haiku"]["change"] for r in rows]; S = [r["raters"]["sonnet"]["change"] for r in rows]; A = [h and s for h, s in zip(H, S)]
anth = [(h == s) for h, s in zip(H, S)]
print(f"Haiku says change on {sum(H)} of 50, Sonnet on {sum(S)}; both agree on {sum(anth)} items ({sum(h and s for h,s in zip(H,S))} yes)")
for name in ("clef", "jev"):
    old = [r["raters"][name]["change"] for r in rows]; new = [out[r["id"]][name]["change"] for r in rows]; anyy = [out[r["id"]][name]["any"] for r in rows]
    ag = lambda x, y: sum(a == b for a, b in zip(x, y)) / len(x)
    ag2 = lambda x: sum(a == h for a, h, k in zip(x, H, anth) if k) / sum(anth)
    print(f"{name}: yes on old wording {sum(old)}, new 2-of-3 {sum(new)}, new any-of-3 {sum(anyy)} | agreement with Haiku: old {ag(old,H):.2f} new {ag(new,H):.2f} | with Sonnet: old {ag(old,S):.2f} new {ag(new,S):.2f} | on the {sum(anth)} items where Haiku and Sonnet agree: old {ag2(old):.2f} new {ag2(new):.2f}")
