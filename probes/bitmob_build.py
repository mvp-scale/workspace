"""Builds what the live BitMob loads for routing (data/bitmob/live/): the area router and the questions learned per location.

router.npz       LogisticRegression on the router_reader member's vector of a request -> area, trained on every area-labelled
                 request (bitmob_router.py's data; labels are areas, never answers)
questions.json   questions learned in more than one location, one head per location (the location's member encoder):
                 "vuln" = is this code a real security vulnerability, taught by the OWASP Benchmark's own labels, trained on the
                 OWASP train split minus the 80 websec probe items (so the Scenario lab sets stay unseen); each head's balanced
                 accuracy on the 905 held-out OWASP cases is stored with it (measured, not claimed)
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/bitmob_build.py   then ./service.sh restart classifier
"""
import json, sys, pathlib, time
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pocket_test as pt, bitmob_bench as bb, bitmob_router as br
from latent_intake import gate

LIVE = bb.OUT / "live"; LIVE.mkdir(parents=True, exist_ok=True)
VULN = {"id": "vuln", "name": "Real security vulnerability (code)",
        "instructions": "Is this code a real security vulnerability: does untrusted input reach a dangerous operation without being made safe?",
        "criteria": {"true": "Yes: untrusted input reaches a dangerous operation (query, command, file path, HTML output, crypto choice ...) without proper neutralisation.",
                     "false": "No: the input is neutralised, constant, or never reaches the dangerous operation (a safe look-alike)."},
        "taught_by": "OWASP Benchmark 1.2 labels (expectedresults-1.2.csv)",
        "example": 'String id = request.getParameter("id");\nStatement st = conn.createStatement();\nResultSet rs = st.executeQuery("SELECT * FROM users WHERE id = \'" + id + "\'");', "locations": {"code": "code-16m", "general": "e5-small"}}


def main():
    t0 = time.time()
    # ---- router: same requests and labels as probes/bitmob_router.py, all of them ----
    ow = br.owasp_items(pathlib.Path("/workspace/data/sources/owasp/BenchmarkJava"))
    req = [f"Is this code a real security vulnerability? | yes / no\n{i['text'][:1500]}" for i in ow["items"]]; area = [br.area_of_source["owasp"]] * len(req)
    for t, items in bb.TASKS.items():
        for i in items:
            s = f"mmlu:{i['family'][5:]}" if t == "mmlu" else t; req.append(bb.request_text(i)); area.append(br.area_of_source.get(s, br.GEN))
    X = br.enc(bb.CFG["router_reader"])(req)
    r = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(X, area)
    np.savez(LIVE / "router.npz", coef=r.coef_.astype(np.float32), intercept=r.intercept_.astype(np.float32), classes=np.array(r.classes_))
    print(f"router: {len(req)} requests, areas {list(r.classes_)}, reader {bb.CFG['router_reader']}", flush=True)

    # ---- the vuln question, one head per location ----
    websec = {json.loads(l)["id"].split("-")[1] for l in open("/workspace/probes/v2/websec.jsonl")}
    keep = lambda k: ow["items"][k]["id"][-5:] not in websec
    tr = np.array([k for k in ow["train"] if keep(k)]); te = np.array(ow["test"]); y = np.array([i["y"] for i in ow["items"]])
    texts = [i["text"] for i in ow["items"]]; heads = {}
    for loc, mid in VULN["locations"].items():
        V = br.enc(mid)(texts)
        clf = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(V[tr], y[tr])
        acc = float(pt.bal(y[te], (clf.predict_proba(V[te])[:, 1] > 0.5).astype(int)))
        oof = np.zeros(len(tr))
        for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(V[tr], y[tr]):
            oof[b] = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(V[tr][a], y[tr][a]).predict_proba(V[tr][b])[:, 1]
        _, lo, hi = gate(oof, y[tr])
        heads[loc] = {"member": mid, "w": clf.coef_[0].round(6).tolist(), "b": float(clf.intercept_[0]), "t": 0.5, "lo": float(lo), "hi": float(hi),
                      "trained_on": int(len(tr)), "positives": int(y[tr].sum()), "held_out_balanced_accuracy": acc, "held_out_n": int(len(te))}
        print(f"vuln @ {loc} ({mid}): held-out balanced accuracy {acc:.1%} on {len(te)} cases; gate {lo:.2f}-{hi:.2f}", flush=True)
    q = {k: v for k, v in VULN.items() if k != "locations"} | {"heads": heads}
    json.dump({"note": "built by probes/bitmob_build.py", "router_reader": bb.CFG["router_reader"],
               "areas": {a: bb.CFG["areas"][a]["member"] for a in br.AREAS}, "questions": [q]}, open(LIVE / "questions.json", "w"))
    print(f"wrote {LIVE}/router.npz and questions.json in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
