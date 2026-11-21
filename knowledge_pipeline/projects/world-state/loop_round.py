"""loop_round: the fixed round template of the self-improvement loop (design docs/research/2026-11-20-self-improvement-loop.md, process guards after L2755). Generalises topic_loop.py's pre-registration, split and scoring steps; a round script keeps its own cache and fit code.
A round is a folder (runs/pulse/<loop>/<round>/) holding prereg.json, then results_dev.json (any number of dev runs) and results.json (the one final run).
  loop_round.py prereg <dir> --script <round script .py> --split <split spec .json> --prediction <prediction .json> [--rescore <rescore .json>]   write prereg.json (refuses if it exists): sha256 of the script and of the split file, the prediction, optional rescore recipe
  loop_round.py check  <dir>                          exit 1 unless prereg.json exists and the script and the split still hash as recorded
  loop_round.py score  <dir> --dev                    runs the script's score(ctx) with confirm closed: ctx.ids("confirm") raises; writes results_dev.json (never results.json)
  loop_round.py score  <dir> --final                  runs score(ctx) with confirm open, exactly once (confirm.lock is written first, results.json must not exist); results.json cites prereg_sha256, script_sha256, split_sha256
  loop_round.py rescore <dir> --part select|confirm   independent re-score of the primary's top-1 from the saved model + cached inputs + gold only (no round-script code); confirm needs results.json to exist (the final run came first)
  loop_round.py --selftest                            tiny synthetic split: tamper, dev-closes-confirm, one final, independent re-score
Round script contract: a module with score(ctx) -> dict; ctx.dir, ctx.split (parsed spec: ids {train, select, confirm}, publishers, content_sha256), ctx.mode, ctx.ids(part) -> list of item ids (raises for confirm in dev mode and for any part not in the spec).
Rescore recipe (rescore.json, in prereg): {"model": path to a pickle dict (scaler_mean, scaler_scale, coef, intercept, classes, card_ids, live_mix), "cache": path to an npz (order, Sm [items x cards], card_ids), "gold": "mnds" | path to a json {id: class}}. Top-1 is reported uncorrected and with the live-mix prior correction."""
import sys, os, json, hashlib, pickle, pathlib, importlib.util, time, tempfile
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def sha_obj(o): return hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()
def _path(p): p = pathlib.Path(p); return p if p.is_absolute() else HERE / p
class Ctx:
    def __init__(self, d, split, mode): self.dir = d; self.split = split; self.mode = mode
    def ids(self, part):
        if part == "confirm" and self.mode != "final": raise PermissionError("confirm is closed in %s mode: only the final run scores it, once" % self.mode)
        if part not in self.split["ids"]: raise KeyError("no part %r in the split" % part)
        return list(self.split["ids"][part])
def write_prereg(d, script, split, prediction, rescore=None):
    d = pathlib.Path(d); d.mkdir(parents=True, exist_ok=True); f = d / "prereg.json"
    if f.exists(): raise FileExistsError("prereg.json exists: a pre-registration is written once")
    pre = {"written_before_scoring": True, "written": time.strftime("%Y-%m-%dT%H:%M:%S"), "script": str(script), "script_sha256": sha_file(_path(script)), "split": str(split), "split_sha256": sha_file(_path(split)), "prediction": prediction, "rescore": rescore, "rules": "script and split must hash as recorded; dev runs score select only; confirm is scored once by the final run; every adopted result is re-scored independently"}
    json.dump(pre, open(f, "w"), indent=1); return pre
def check_prereg(d):
    f = pathlib.Path(d) / "prereg.json"
    if not f.exists(): raise FileNotFoundError("no prereg.json in %s: write it before any scoring" % d)
    pre = json.load(open(f)); bad = [k for k, p in (("script", pre["script"]), ("split", pre["split"])) if sha_file(_path(p)) != pre[k + "_sha256"]]
    if bad: raise RuntimeError("scoring refused: %s changed since the pre-registration (%s)" % (" and ".join(bad), f))
    pre["prereg_sha256"] = sha_file(f); return pre
def score(d, mode):
    assert mode in ("dev", "final"); d = pathlib.Path(d); pre = check_prereg(d); split = json.load(open(_path(pre["split"])))
    if mode == "final":
        if (d / "confirm.lock").exists() or (d / "results.json").exists(): raise RuntimeError("confirm was already scored (confirm.lock or results.json exists): it is scored once")
        open(d / "confirm.lock", "w").write(time.strftime("%Y-%m-%dT%H:%M:%S") + " " + pre["prereg_sha256"] + "\n")
    spec = importlib.util.spec_from_file_location("round_script", _path(pre["script"])); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    res = m.score(Ctx(d, split, mode)); res = {**res, "mode": mode, "prereg_sha256": pre["prereg_sha256"], "script_sha256": pre["script_sha256"], "split_sha256": pre["split_sha256"], "scored_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(res, open(d / ("results.json" if mode == "final" else "results_dev.json"), "w"), indent=1); return res
def mnds_gold():
    """item id -> IPTC level-1 code for every MN-DS set the topic loop uses, through mnds_codes (no label strings)."""
    sys.path.insert(0, str(HERE)); from mnds_codes import gold_codes
    out = {}
    for g in ("gold_T28_clean.json", "gold_T28b.json", "gold_fresh.json", "gold_fresh2.json"):
        for i, v in json.load(open("/workspace/data/anchors/mn_ds/" + g)).items():
            c = gold_codes(v)[0]
            if c and i not in out: out[i] = c
    return out
def rescore(d, part, gold=None):
    """Independent of any round script: top-1 of the saved model on one split part, from cached card scores only. softmax(((S - mean) / scale) @ coef.T + b); corrected = x live_mix."""
    d = pathlib.Path(d); pre = check_prereg(d); rc = pre.get("rescore")
    if not rc: raise RuntimeError("prereg has no rescore recipe")
    if part == "confirm" and not (d / "results.json").exists(): raise PermissionError("confirm is re-scored only after the final run has written results.json")
    return rescore_recipe(rc, _path(pre["split"]), part, gold, pre["prereg_sha256"])
def rescore_recipe(rc, split_path, part, gold=None, prereg_sha=None):
    split = json.load(open(split_path)); m = pickle.load(open(_path(rc["model"]), "rb")); z = np.load(_path(rc["cache"]), allow_pickle=False); order = [str(i) for i in z["order"]]
    assert list(m["card_ids"]) == [str(c) for c in z["card_ids"]], "card lists differ between model and cache"
    gold = gold or (mnds_gold() if rc["gold"] == "mnds" else json.load(open(_path(rc["gold"])))); pos = {i: k for k, i in enumerate(order)}; ids = [i for i in split["ids"][part] if i in pos and i in gold]; S = z["Sm"][[pos[i] for i in ids]].astype(np.float64)
    zz = ((S - np.array(m["scaler_mean"])) / np.array(m["scaler_scale"])) @ np.array(m["coef"]).T + np.array(m["intercept"]).ravel(); zz -= zz.max(1, keepdims=True); p = np.exp(zz); p /= p.sum(1, keepdims=True)
    cl = np.array(m["classes"]); y = np.array([gold[i] for i in ids]); r = {"part": part, "n": len(ids), "top1": round(float((cl[p.argmax(1)] == y).mean()), 4), "top1_live_corrected": round(float((cl[(p * np.array(m["live_mix"])).argmax(1)] == y).mean()), 4), "model_sha256": sha_file(_path(rc["model"])), "prereg_sha256": prereg_sha}
    return r
def selftest():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="loop_round_")); rng = np.random.default_rng(0); n, K, C = 90, 3, 12; cards = ["c%d" % i for i in range(C)]; ids = ["i%d" % i for i in range(n)]
    cls = rng.integers(0, K, n); S = rng.normal(0, 1, (n, C)) + np.eye(K)[cls] @ rng.normal(0, 0.8, (K, C)); parts = {"train": ids[:50], "select": ids[50:70], "confirm": ids[70:]}
    (tmp / "split.json").write_text(json.dumps({"ids": parts, "publishers": {}, "content_sha256": sha_obj(parts)}))
    mean, scale = S[:50].mean(0), S[:50].std(0); W = np.zeros((K, C))
    for k in range(K): W[k] = ((S[:50][cls[:50] == k] - mean) / scale).mean(0)
    mdl = {"scaler_mean": mean.tolist(), "scaler_scale": scale.tolist(), "coef": W.tolist(), "intercept": [0.0] * K, "classes": ["k0", "k1", "k2"], "card_ids": cards, "live_mix": [1 / 3] * 3}; pickle.dump(mdl, open(tmp / "model.pkl", "wb"))
    np.savez(tmp / "cache.npz", order=np.array(ids), Sm=S.astype(np.float32), card_ids=np.array(cards)); gold = {i: "k%d" % c for i, c in zip(ids, cls)}; json.dump(gold, open(tmp / "gold.json", "w"))
    (tmp / "round_script.py").write_text('import numpy as np, pickle, json, pathlib\nHERE = pathlib.Path(__file__).resolve().parent\ndef score(ctx):\n    m = pickle.load(open(HERE / "model.pkl", "rb")); z = np.load(HERE / "cache.npz"); g = json.load(open(HERE / "gold.json")); pos = {str(i): k for k, i in enumerate(z["order"])}; out = {}\n    for part in ("select", "confirm"):\n        ids = ctx.ids(part); S = z["Sm"][[pos[i] for i in ids]].astype(float); zz = ((S - np.array(m["scaler_mean"])) / np.array(m["scaler_scale"])) @ np.array(m["coef"]).T; out[part + "_top1"] = round(float((np.array(m["classes"])[zz.argmax(1)] == np.array([g[i] for i in ids])).mean()), 4)\n    return out\n')
    d = tmp / "round"; rc = {"model": str(tmp / "model.pkl"), "cache": str(tmp / "cache.npz"), "gold": str(tmp / "gold.json")}
    try: check_prereg(d); raise SystemExit("FAIL: no prereg accepted")
    except FileNotFoundError: pass
    write_prereg(d, tmp / "round_script.py", tmp / "split.json", {"primary_confirm_top1": [0.5, 1.0]}, rc)
    try: write_prereg(d, tmp / "round_script.py", tmp / "split.json", {}); raise SystemExit("FAIL: prereg overwritten")
    except FileExistsError: pass
    try: score(d, "dev"); raise SystemExit("FAIL: dev run touched confirm")   # the self-test script asks for both parts, so dev must refuse
    except PermissionError: pass
    assert not (d / "results_dev.json").exists() and not (d / "confirm.lock").exists()
    try: rescore(d, "confirm"); raise SystemExit("FAIL: confirm re-scored before the final run")
    except PermissionError: pass
    r_sel = rescore(d, "select")["top1"]; (tmp / "split.json").write_text((tmp / "split.json").read_text() + " ")   # a changed split must stop scoring
    try: score(d, "final"); raise SystemExit("FAIL: changed split accepted")
    except RuntimeError as e: assert "split changed" in str(e), e
    (tmp / "split.json").write_text((tmp / "split.json").read_text().rstrip()); res = score(d, "final"); assert res["prereg_sha256"] == sha_file(d / "prereg.json") and (d / "confirm.lock").exists()
    try: score(d, "final"); raise SystemExit("FAIL: confirm scored twice")
    except RuntimeError: pass
    rr = rescore(d, "confirm"); assert abs(rr["top1"] - res["confirm_top1"]) < 1e-9 and abs(r_sel - res["select_top1"]) < 1e-9, (rr, res, r_sel)
    (tmp / "round_script.py").write_text((tmp / "round_script.py").read_text() + "\n# edited\n")
    try: check_prereg(d); raise SystemExit("FAIL: changed script accepted")
    except RuntimeError as e: assert "script changed" in str(e), e
    print("selftest ok: prereg once, dev closes confirm, tamper refused (split, script), one final, rescore matches (select %.3f, confirm %.3f)" % (r_sel, rr["top1"]))
if __name__ == "__main__":
    a = sys.argv[1:]; arg = lambda k: a[a.index(k) + 1] if k in a else None
    if "--selftest" in a: selftest()
    elif a[0] == "prereg": print(json.dumps(write_prereg(a[1], arg("--script"), arg("--split"), json.load(open(arg("--prediction"))), json.load(open(arg("--rescore"))) if arg("--rescore") else None), indent=1)[:600])
    elif a[0] == "check": check_prereg(a[1]); print("prereg ok")
    elif a[0] == "score": print(json.dumps(score(a[1], "final" if "--final" in a else "dev"), indent=1)[:1500])
    elif a[0] == "rescore": print(json.dumps(rescore(a[1], arg("--part") or "select")))
