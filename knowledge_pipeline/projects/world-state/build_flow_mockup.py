"""Builds /workspace/_remove/knowledge_flow_mockup.html from the fingerprint store (local only: holds publisher text; do not publish or commit)."""
import json, sqlite3, re, pathlib
H0 = pathlib.Path(__file__).resolve().parent; R = H0 / "runs/fingerprint"; con = sqlite3.connect(R / "fingerprints.db"); res = json.load(open(R / "store_results.json"))
pool = {}
want = {"confirmed": "nq:a44d535349028324676bf674e93e345d2fbd3a85389fdbd09824fce9a7cf80bc", "disagree": "cc:http://nation.com.pk/business/15-Aug-2017/kenya-s-stock-market-hits-14-month-high", "floor": "cc:http://abcnews.go.com/International/wireStory/germany-concerned-sale-gms-opel-45508036"}
for l in open(H0 / "data/pool_train.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if r["id"] in want.values(): pool[r["id"]] = r
items = []
for kind, i in want.items():
    it = con.execute("select source,date,topic,story_type,haiku_conditions,sonnet_conditions from items where id=?", (i,)).fetchone()
    parts = [r[0] for r in con.execute("select key from part where item_id=?", (i,))]
    z = dict(con.execute("select key,z from stat where outcome='names_a_condition' and key in (%s)" % ",".join("?" * len(parts)), parts).fetchall()) if parts else {}
    sig = sorted(((k, round(v, 1)) for k, v in z.items() if v >= 3), key=lambda x: -x[1]); neg = sorted(((k, round(v, 1)) for k, v in z.items() if v <= -3), key=lambda x: x[1])
    items.append({"kind": kind, "id": i, "text": re.sub(r"\s+", " ", pool[i]["text"]), "source": it[0], "date": it[1], "topic": it[2], "story_type": it[3], "haiku": it[4] or "none", "sonnet": it[5] or "none",
                  "n_parts": len(parts), "parts_sample": sorted(parts)[:0] or [p for p in parts if p.startswith(("w:", "b:", "h:", "et:", "en:", "f:", "s:"))][:0], "parts": sorted(parts), "sig": sig[:10], "neg": neg[:6], "hits": len(sig)})
data = {"items": items, "m1": res["M1_stability_jaccard_top50"], "m2": {"share": res["M2_share_sonnet_confirms_same_condition"], "n": res["M2_voted_haiku_positive"], "auc": res["M2_cv_auc_confirmed"], "conf": res["M2_top_confirmed_parts"][:8], "pas": res["M2_top_passing_parts"][:8]},
        "m3": res["M3_floor"]["hits_le_5"], "m4": res["M4_store"], "vocab": res["vocab"], "ppi": res["parts_per_item"], "n": res["items"]}
html = open(H0 / "flow_mockup_template_v2.html", encoding="utf-8").read().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
out = pathlib.Path("/workspace/_remove/knowledge_flow_mockup.html"); out.write_text(html, encoding="utf-8"); print(out, len(html) // 1024, "KB")
