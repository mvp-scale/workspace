"""S4 student training: shared encoder, one BIO head per token span layer, optional multi-label sequence head.

    python train.py --config cfg.yaml [--seed 42 | --all-seeds] [--out-dir DIR]
    python train.py --config cfg.yaml --smoke          # R2: 3 items x 1 step, writes smoke.json (cite its id)

GPU only (local RTX 5090/3090, RunPod or Kaggle). Never on the dev machine: without CUDA it stops unless --smoke
or --allow-cpu. Recipe = the first project's student v2 (pipeline/kaggle/student/train_v2): MiniLM-L12 cut to N
layers, 254-token windows step 192 with [CLS]/[SEP], every window of every item trained, AdamW (encoder / head LRs),
linear warm-up + decay, grad clip 1, AMP, fixed seed. Overlapping spans of one label are layered greedily into that
head's channels (core.layer). Optional: class weights, soft targets (KL to teacher probabilities from span `p` /
item `probs`), dev eval each epoch (exact-span F1 per head, sequence micro F1).
Writes to out_dir/seed<N>/: selection_rule.json (before training, M3), inputs.json (R3 shas), dev_curve.json,
last.pt (+ best.pt with selection best_dev_min_f1), backbone/ (truncated encoder config), tokenizer/, kit_meta.json.
"""
import argparse
import datetime as dt
import inspect
import json
import os
import pathlib
import random
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402

T0 = time.time()


def log(*a):
    print(f"[train {time.time() - T0:6.0f}s]", *a, flush=True)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------------- model
def _layers_attr(enc):
    """the encoder's ModuleList of layers, across BERT / ModernBERT / DistilBERT layouts"""
    for path in ("encoder.layer", "layers", "transformer.layer", "encoder.layers"):
        obj = enc
        try:
            for p in path.split("."):
                obj = getattr(obj, p)
        except AttributeError:
            continue
        return path, obj
    raise ValueError(f"can't find encoder layers on {type(enc).__name__}")


def build_encoder(bcfg, backbone_dir=None):
    """bcfg: config['backbone']. backbone_dir: saved truncated config (export: no download, weights from ckpt)."""
    from transformers import AutoConfig, AutoModel
    kw = {"attn_implementation": bcfg.get("attn_implementation", "eager")}
    if backbone_dir:
        return AutoModel.from_config(AutoConfig.from_pretrained(backbone_dir), **kw)
    enc = AutoModel.from_pretrained(bcfg["name"], **kw)
    n = bcfg.get("layers")
    if n:
        path, layers = _layers_attr(enc)
        parent = enc
        for p in path.split(".")[:-1]:
            parent = getattr(parent, p)
        setattr(parent, path.split(".")[-1], layers[:n])
        enc.config.num_hidden_layers = n
        if hasattr(enc.config, "layer_types") and enc.config.layer_types:   # newer ModernBERT configs
            enc.config.layer_types = enc.config.layer_types[:n]
    return enc


def make_student(cfg, nch, n_seq, backbone_dir=None):
    import torch
    import torch.nn as nn

    class Student(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = build_encoder(cfg["backbone"], backbone_dir)
            h = self.enc.config.hidden_size
            self.drop = nn.Dropout(cfg.get("train", {}).get("dropout", 0.1))
            self.head = nn.Linear(h, 3 * nch)
            self.seq = nn.Linear(h, n_seq) if n_seq else None
            sig = inspect.signature(self.enc.forward).parameters
            self.tti = "token_type_ids" in sig and getattr(self.enc.config, "type_vocab_size", 0) > 0

        def forward(self, input_ids, attention_mask):
            kw = {"token_type_ids": torch.zeros_like(input_ids)} if self.tti else {}
            h = self.enc(input_ids=input_ids, attention_mask=attention_mask, **kw).last_hidden_state
            h = self.drop(h)
            tags = self.head(h)
            if self.seq is None:
                return tags
            return tags, self.seq(h[:, 0])

    return Student()


# ----------------------------------------------------------------------------- data
def heads_of(cfg):
    th = cfg["heads"]["token"]
    sq = cfg["heads"].get("sequence") or None
    return th, core.channel_heads(th), (sq["labels"] if sq else [])


def check_item(it, names, bad):
    """valid spans of one item -> [(start, end, p, label)]; unknown labels and bad offsets are counted, not used"""
    text = it["text"]
    ok = []
    for s in it.get("spans", []):
        a, b, lab = s["start"], s["end"], s["label"]
        if lab not in names:
            bad["unknown_label"] += 1
            continue
        if not (0 <= a < b <= len(text)):
            bad["bad_offsets"] += 1
            continue
        ok.append((a, b, float(s.get("p", 1.0)), lab))
    return ok


def prepare(items, tok, cfg, with_targets=True):
    """items -> encoded items with windows; targets per channel (hard BIO, optional soft [n,nch,3]) and seq vector."""
    import collections
    th, chs, seq_labels = heads_of(cfg)
    W, STEP = cfg["window"]["size"], cfg["window"]["stride"]
    soft_cfg = cfg.get("train", {}).get("soft_targets") or {}
    thr = soft_cfg.get("hard_threshold", 0.5)
    hc = core.head_channels(chs)
    bad, drops, nspan = collections.Counter(), collections.Counter(), collections.Counter()
    any_soft = False
    out = []
    for it in items:
        e = tok(it["text"], add_special_tokens=False, return_offsets_mapping=True)
        ids, offs = list(e["input_ids"]), [tuple(o) for o in e["offset_mapping"]]
        spans = check_item(it, set(chs), bad)
        rec = {"id": it.get("id"), "text": it["text"], "ids": ids, "offs": offs,
               "gold": {h["name"]: sorted({(a, b) for a, b, p, lab in spans if lab == h["name"] and p >= thr})
                        for h in th},
               "gold_labels": sorted(it.get("labels", []))}
        if with_targets:
            soft_here = any(p < 1.0 for _, _, p, _ in spans) or bool(it.get("probs"))
            any_soft |= soft_here
            hard = np.zeros((len(ids), len(chs)), np.int64)
            soft = np.zeros((len(ids), len(chs), 3), np.float32)
            soft[:, :, 0] = 1.0
            for h in th:
                mine = [(a, b, p) for a, b, p, lab in spans if lab == h["name"]]
                nspan[h["name"]] += len(mine)
                layers, nd = core.layer(mine, len(hc[h["name"]]))
                drops[h["name"]] += nd
                for c, sp in zip(hc[h["name"]], layers):
                    hard[:, c] = core.bio(offs, [s for s in sp if s[2] >= thr])
                    soft[:, c] = core.soft_bio(offs, sp)
            rec["hard"], rec["soft"] = hard, soft
            if seq_labels:
                pr = it.get("probs") or {}
                lab = set(it.get("labels", []))
                rec["seq"] = np.array([float(pr.get(l, 1.0 if l in lab else 0.0)) for l in seq_labels], np.float32)
        st, rows = core.rows_of(tok.cls_token_id, tok.sep_token_id, ids, W, STEP)
        rec["starts"], rec["rows"] = st, rows
        out.append(rec)
    info = {"items": len(out), "label_issues": dict(bad), "spans_by_head": dict(nspan),
            "dropped_by_layering": dict(drops), "soft_targets_present": any_soft}
    return out, info


def windows_of(recs, W):
    """training windows: (ids row, hard [L, nch] with -100 at CLS/SEP, soft [L, nch, 3], seq)"""
    wins = []
    for r in recs:
        for s, row in zip(r["starts"], r["rows"]):
            n = len(row) - 2
            y = np.full((len(row), r["hard"].shape[1]), core.NO_LABEL, np.int64)
            y[1:-1] = r["hard"][s:s + n]
            sf = np.zeros((len(row), r["hard"].shape[1], 3), np.float32)
            sf[1:-1] = r["soft"][s:s + n]
            wins.append((row, y, sf, r.get("seq")))
    return wins


def batches(wins, bs, shuffle, rng):
    import torch
    idx = list(range(len(wins)))
    if shuffle:
        rng.shuffle(idx)
    nch = wins[0][1].shape[1]
    for i in range(0, len(idx), bs):
        chunk = [wins[j] for j in idx[i:i + bs]]
        L = max(len(x) for x, *_ in chunk)
        ids = np.zeros((len(chunk), L), np.int64)
        am = np.zeros((len(chunk), L), np.int64)
        ys = np.full((len(chunk), L, nch), core.NO_LABEL, np.int64)
        sf = np.zeros((len(chunk), L, nch, 3), np.float32)
        for r, (x, y, s, _) in enumerate(chunk):
            ids[r, :len(x)] = x
            am[r, :len(x)] = 1
            ys[r, :len(x)] = y
            sf[r, :len(x)] = s
        sq = None
        if chunk[0][3] is not None:
            sq = torch.from_numpy(np.stack([c[3] for c in chunk]))
        yield torch.from_numpy(ids), torch.from_numpy(am), torch.from_numpy(ys), torch.from_numpy(sf), sq


def class_weights(spec, recs, nch):
    """-> np [nch, 3]"""
    if spec in (None, "none"):
        return np.ones((nch, 3), np.float32)
    if isinstance(spec, (list, tuple)):
        return np.tile(np.array(spec, np.float32), (nch, 1))
    cnt = np.ones((nch, 3), np.float64)
    for r in recs:
        for c in range(nch):
            cnt[c] += np.bincount(r["hard"][:, c], minlength=3)[:3]
    w = 1.0 / np.sqrt(cnt / cnt.sum(1, keepdims=True))
    return (w / w[:, :1]).astype(np.float32)   # O weight 1


# ----------------------------------------------------------------------------- eval
def torch_runner(model, dev):
    import torch

    def f(x):
        with torch.no_grad(), torch.autocast(dev.type, enabled=dev.type == "cuda"):
            o = model(torch.from_numpy(x).to(dev), torch.ones_like(torch.from_numpy(x)).to(dev))
        if isinstance(o, tuple):
            return o[0][0].float().cpu().numpy(), o[1][0].float().cpu().numpy()
        return o[0].float().cpu().numpy(), None
    return f


def evaluate(run_fn, recs, cfg, cls_id, sep_id):
    th, chs, seq_labels = heads_of(cfg)
    W, STEP = cfg["window"]["size"], cfg["window"]["stride"]
    sq = cfg["heads"].get("sequence") or {}
    preds, seq_pred = [], []
    for r in recs:
        if not r["ids"]:
            preds.append({h: [] for h in dict.fromkeys(chs)})
            seq_pred.append([])
            continue
        tags, seqs = core.predict(run_fn, r["ids"], cls_id, sep_id, W, STEP)
        preds.append(core.decode(r["text"], r["offs"], tags, chs))
        if seq_labels:
            p = core.sigmoid(core.pool_seq(seqs, sq.get("pool", "max")))
            seq_pred.append([l for l, v in zip(seq_labels, p) if v >= sq.get("threshold", 0.5)])
    f1 = {h["name"]: core.span_f1([r["gold"][h["name"]] for r in recs], [p[h["name"]] for p in preds]) for h in th}
    res = {"span_f1": f1, "min_f1": min(f1.values()) if f1 else None}
    if seq_labels:
        per = {}
        for l in seq_labels:
            per[l] = core.span_f1([[(0, 1)] if l in r["gold_labels"] else [] for r in recs],
                                  [[(0, 1)] if l in p else [] for p in seq_pred])
        res["seq_f1"] = per
        res["seq_macro_f1"] = round(float(np.mean(list(per.values()))), 6)
    return res, preds


# ----------------------------------------------------------------------------- train one seed
def train_seed(cfg, seed, out_dir, smoke=False):
    import torch
    import torch.nn.functional as F
    from transformers import AutoTokenizer
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tc = cfg.get("train", {})
    th, chs, seq_labels = heads_of(cfg)
    nch, W = len(chs), cfg["window"]["size"]

    # R3: frozen inputs by sha, printed and saved before any work
    inputs = {k: {"path": v, "sha256": core.sha256(v)} for k, v in cfg["data"].items() if v and os.path.exists(v)}
    inputs["config"] = {"sha256": __import__("hashlib").sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()}
    log("INPUTS SHA256", json.dumps({k: v["sha256"][:12] for k, v in inputs.items()}))
    json.dump({"at": now(), "inputs": inputs}, open(out / "inputs.json", "w"), indent=1)

    # M3: selection rule on disk before training or any test scoring
    sel = tc.get("selection", "last")
    json.dump({"rule": sel, "written_at": now(), "seed": seed,
               "detail": "last = final epoch checkpoint, no dev pick" if sel == "last" else
               "best_dev_min_f1 = epoch with the highest min over token heads of dev exact-span F1; ties -> earlier"},
              open(out / "selection_rule.json", "w"), indent=1)

    tok = AutoTokenizer.from_pretrained(cfg["backbone"].get("tokenizer") or cfg["backbone"]["name"])
    if not tok.is_fast:
        raise SystemExit("need a fast tokenizer (offsets + tokenizer.json for the runtime)")
    lim = 3 if smoke else None
    tr_items = core.read_jsonl(cfg["data"]["train"], lim)
    dv_path = cfg["data"].get("dev")
    dv_items = core.read_jsonl(dv_path, lim) if dv_path and os.path.exists(dv_path) else tr_items[:3]
    tr, tr_info = prepare(tr_items, tok, cfg)
    dv, _ = prepare(dv_items, tok, cfg, with_targets=False)
    for h, nd in tr_info["dropped_by_layering"].items():
        n = tr_info["spans_by_head"].get(h, 0)
        if n and nd / n > tc.get("max_drop_frac", 0.01):
            log(f"WARN head {h}: layering drops {nd}/{n} spans; raise its channels")
    log("DATA", json.dumps(tr_info))

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    rng = random.Random(seed)
    wins = windows_of(tr, W)
    model = make_student(cfg, nch, len(seq_labels)).to(dev)
    nparams = sum(p.numel() for p in model.parameters())
    hp = [p for nm, p in model.named_parameters() if nm.startswith(("head", "seq"))]
    ep = [p for nm, p in model.named_parameters() if not nm.startswith(("head", "seq"))]
    opt = torch.optim.AdamW([{"params": ep, "lr": tc.get("lr_encoder", 1e-4)},
                             {"params": hp, "lr": tc.get("lr_head", 1e-3)}], weight_decay=tc.get("weight_decay", 0.01))
    bs = 3 if smoke else tc.get("batch_size", 32)
    epochs = 1 if smoke else tc.get("epochs", 12)
    per_ep = (len(wins) + bs - 1) // bs
    steps = (1 if smoke else tc.get("schedule_epochs", epochs)) * per_ep
    warm = max(1, int(tc.get("warmup_frac", 0.1) * steps))
    sch = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: s / warm if s < warm else max(0.0, (steps - s) / max(1, steps - warm)))
    amp = bool(tc.get("amp", True)) and dev.type == "cuda"
    scaler = torch.amp.GradScaler(enabled=amp)
    cw = torch.from_numpy(class_weights(tc.get("class_weights"), tr, nch)).to(dev)
    sc = tc.get("soft_targets") or {}
    alpha = float(sc.get("weight", 0.5)) if tr_info["soft_targets_present"] else 0.0
    T = float(sc.get("temperature", 1.0))
    seq_w = float((cfg["heads"].get("sequence") or {}).get("loss_weight", 1.0))

    def loss_fn(o, y, sf, sq):
        lg = o[0] if isinstance(o, tuple) else o
        B, L = y.shape[:2]
        lg = lg.float().view(B, L, nch, 3)
        logp = F.log_softmax(lg, -1)
        mask = (y != core.NO_LABEL).float()
        yc = y.clamp(min=0)
        nll = -logp.gather(-1, yc.unsqueeze(-1)).squeeze(-1)
        w = cw[torch.arange(nch, device=dev).view(1, 1, nch).expand(B, L, nch), yc] * mask
        loss = (nll * w).sum() / w.sum().clamp(min=1e-8)
        if alpha:
            lq = F.log_softmax(lg / T, -1)
            kl = (sf * (sf.clamp(min=1e-8).log() - lq)).sum(-1)
            loss = (1 - alpha) * loss + alpha * (T * T) * (kl * mask).sum() / mask.sum().clamp(min=1.0)
        if isinstance(o, tuple) and sq is not None:
            loss = loss + seq_w * F.binary_cross_entropy_with_logits(o[1].float(), sq)
        return loss

    tok.save_pretrained(out / "tokenizer")
    (out / "backbone").mkdir(exist_ok=True)
    model.enc.config.save_pretrained(out / "backbone")
    meta = {"kit": "student", "run_name": cfg.get("run_name"), "seed": seed, "channels": chs,
            "token_heads": [h["name"] for h in th], "seq_labels": seq_labels, "window": cfg["window"],
            "cls_id": tok.cls_token_id, "sep_id": tok.sep_token_id, "params": nparams,
            "torch": torch.__version__, "device": str(dev),
            "gpu": torch.cuda.get_device_name(0) if dev.type == "cuda" else None,
            "class_weights": cw.cpu().numpy().round(4).tolist(), "soft_weight": alpha, "train_windows": len(wins),
            "steps_schedule": steps}
    json.dump(meta, open(out / "kit_meta.json", "w"), indent=1)

    def save(name, epoch, metrics):
        torch.save({"state_dict": model.state_dict(), "config": cfg, "meta": meta, "epoch": epoch, "dev": metrics},
                   out / name)

    curve, best, step = [], None, 0
    for epoch in range(1, epochs + 1):
        model.train()
        tot, nb, t_ep = 0.0, 0, time.time()
        for x, am, y, sf, sq in batches(wins, bs, True, rng):
            x, am, y, sf = x.to(dev), am.to(dev), y.to(dev), sf.to(dev)
            sq = sq.to(dev) if sq is not None else None
            with torch.autocast(dev.type, enabled=amp):
                o = model(x, am)
            loss = loss_fn(o, y, sf, sq)
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), tc.get("grad_clip", 1.0))
            scaler.step(opt)
            scaler.update()
            sch.step()
            tot += loss.item()
            nb += 1
            step += 1
            if smoke:
                break
        model.eval()
        m, _ = evaluate(torch_runner(model, dev), dv, cfg, tok.cls_token_id, tok.sep_token_id)
        row = {"epoch": epoch, "step": step, "loss": round(tot / max(nb, 1), 5), "epoch_s": round(time.time() - t_ep, 1),
               **m}
        curve.append(row)
        log(f"seed {seed} epoch {epoch} loss {row['loss']:.4f} dev {json.dumps(m)}")
        json.dump({"seed": seed, "selection": sel, "curve": curve}, open(out / "dev_curve.json", "w"), indent=1)
        if sel == "best_dev_min_f1" and (best is None or (m["min_f1"] or 0) > best[1]):
            best = (epoch, m["min_f1"] or 0)
            save("best.pt", epoch, m)
    save("last.pt", epochs, curve[-1])
    pick = "last.pt" if sel == "last" else "best.pt"
    res = {"seed": seed, "picked_checkpoint": pick, "picked_epoch": epochs if sel == "last" else best[0],
           "dev_at_pick": curve[-1] if sel == "last" else curve[best[0] - 1], "wall_s": round(time.time() - T0, 1)}
    json.dump(dict(res, curve_file="dev_curve.json"), open(out / "result.json", "w"), indent=1)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--all-seeds", action="store_true")
    ap.add_argument("--out-dir")
    ap.add_argument("--smoke", action="store_true", help="R2: 3 items x 1 step, then stop")
    ap.add_argument("--allow-cpu", action="store_true", help="permit a non-smoke run without CUDA (not on the dev box)")
    a = ap.parse_args(argv)
    cfg = core.load_config(a.config)
    import torch
    if not torch.cuda.is_available() and not (a.smoke or a.allow_cpu):
        raise SystemExit("no CUDA: training runs on a GPU host (local 5090/3090, RunPod, Kaggle), not here")
    base = pathlib.Path(a.out_dir or cfg.get("out_dir", "runs/student"))
    seeds = cfg.get("train", {}).get("seeds", [42])
    seeds = seeds if a.all_seeds else [a.seed if a.seed is not None else seeds[0]]
    if a.smoke:
        t = time.time()
        r = train_seed(cfg, seeds[0], base / "smoke", smoke=True)
        sid = f"smoke-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        json.dump({"smoke_id": sid, "ok": True, "items": 3, "steps": 1, "s": round(time.time() - t, 1), "result": r},
                  open(base / "smoke" / "smoke.json", "w"), indent=1)
        log("SMOKE OK", sid)
        return
    res = [train_seed(cfg, s, base / f"seed{s}") for s in seeds]
    json.dump(res, open(base / "seeds_summary.json", "w"), indent=1)
    log("DONE", json.dumps([{k: r[k] for k in ("seed", "picked_epoch")} for r in res]))


if __name__ == "__main__":
    main()
