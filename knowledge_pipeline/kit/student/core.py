"""Student kit core: windows, owner-by-centrality, BIO encode/decode, word-boundary snap, channel layout. numpy only.

The window / owner / decode / snap code is pipeline/ship/we_classifier.py's (the T61 kernel's), with the window size,
stride and channel -> head map passed in instead of module constants. Shared by train.py, export.py, runtime.py,
bench.py, so training eval, export checks and the shipped runtime decode identically.

Channel layout (`channel_heads`): the first channel of every token head in config order, then the extra channels of
every multi-channel head in config order. heads [A(2 channels), B, C] -> [A, B, C, A]. This is the student v2 layout
(ENTITY, EVENT_VERB, EVENT_NOUN, TIME, QUANTITY, ENTITY#2), so a v2 model decodes unchanged.
"""
import bisect
import hashlib
import json

import numpy as np

W_DEFAULT, STEP_DEFAULT = 254, 192
NO_LABEL = -100


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_jsonl(path, limit=None):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
                if limit and len(out) >= limit:
                    break
    return out


def load_config(path):
    """YAML (needs pyyaml) or JSON."""
    txt = open(path, encoding="utf-8").read()
    if str(path).endswith((".yaml", ".yml")):
        import yaml
        return yaml.safe_load(txt)
    return json.loads(txt)


# ----------------------------------------------------------------------------- channel layout
def channel_heads(token_heads):
    """token_heads: [{"name", "channels"?}] -> list, one head name per output channel (layout in module doc)."""
    first = [h["name"] for h in token_heads]
    extra = [h["name"] for h in token_heads for _ in range(int(h.get("channels", 1)) - 1)]
    return first + extra


def head_channels(chs):
    """channel list -> {head: [channel indices in layer order]}"""
    out = {}
    for c, h in enumerate(chs):
        out.setdefault(h, []).append(c)
    return out


# ----------------------------------------------------------------------------- windows (as we_classifier.py)
def starts_of(n, w=W_DEFAULT, step=STEP_DEFAULT):
    if n <= w:
        return [0]
    st = list(range(0, n - w + 1, step))
    if st[-1] + w < n:
        st.append(n - w)
    return st


def owner(n, starts, w=W_DEFAULT):
    """token -> index of the window where it is farthest from an edge (first window wins ties)"""
    own = np.zeros(n, np.int64)
    best = np.full(n, -1)
    for wi, s in enumerate(starts):
        e = min(s + w, n)
        pos = np.arange(s, e)
        d = np.minimum(pos - s, e - 1 - pos)
        m = d > best[s:e]
        best[s:e][m] = d[m]
        own[s:e][m] = wi
    return own


def rows_of(cls_id, sep_id, ids, w=W_DEFAULT, step=STEP_DEFAULT):
    st = starts_of(len(ids), w, step)
    return st, [[cls_id] + list(ids[s:s + w]) + [sep_id] for s in st]


def predict(run_fn, ids, cls_id, sep_id, w=W_DEFAULT, step=STEP_DEFAULT):
    """run_fn(x int64 [1, L]) -> (token logits [L, 3*nch], seq logits [n_seq] or None).
    Whole item -> (tags [n_tok, nch] in {0,1,2}, [seq logits per window]). One call per window, as we_classifier."""
    st, rows = rows_of(cls_id, sep_id, ids, w, step)
    own = owner(len(ids), st, w)
    tags, seqs = None, []
    for wi, (s, r) in enumerate(zip(st, rows)):
        x = np.array([r], np.int64)
        lg, sq = run_fn(x)
        t = lg[1:-1].reshape(len(r) - 2, -1, 3).argmax(-1)
        if tags is None:
            tags = np.zeros((len(ids), t.shape[1]), np.int64)
        sel = np.where(own[s:s + len(t)] == wi)[0]
        tags[s + sel] = t[sel]
        if sq is not None:
            seqs.append(np.asarray(sq, np.float64))
    return tags, seqs


def pool_seq(seqs, pool="max"):
    """per-window sequence logits -> one logit vector (max or mean over windows)"""
    if not seqs:
        return None
    a = np.stack(seqs)
    return a.max(0) if pool == "max" else a.mean(0)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, np.float64)))


# ----------------------------------------------------------------------------- decode (as we_classifier.py)
def snap(text, spans):
    """word-boundary fix: widen each span to whole alnum words, merge spans that now overlap (spans in start order)"""
    fixed = []
    for a, b in spans:
        while a > 0 and text[a - 1].isalnum() and text[a].isalnum():
            a -= 1
        while b < len(text) and text[b].isalnum() and text[b - 1].isalnum():
            b += 1
        if fixed and a < fixed[-1][1]:
            fixed[-1] = (fixed[-1][0], max(b, fixed[-1][1]))
        else:
            fixed.append((a, b))
    return fixed


def bio_spans(offs, col):
    """one channel's tags (0 O, 1 B, 2 I) -> token-offset spans; an I with no open span starts one"""
    spans, cur = [], None
    for t, v in enumerate(col):
        if v == 1 or (v == 2 and cur is None):
            if cur:
                spans.append(cur)
            cur = [offs[t][0], offs[t][1]]
        elif v == 2:
            cur[1] = offs[t][1]
        else:
            if cur:
                spans.append(cur)
            cur = None
    if cur:
        spans.append(cur)
    return spans


def decode(text, offs, tags, chs):
    """tags [n_tok, nch] -> {head: sorted [(a, b)]}; a head's spans = union of its channels (exact duplicates once)"""
    res = {h: set() for h in dict.fromkeys(chs)}
    if tags is None or len(tags) == 0:
        return {h: [] for h in res}
    for c, head in enumerate(chs[:tags.shape[1]]):
        res[head].update(snap(text, bio_spans(offs, tags[:, c])))
    return {h: sorted(v) for h, v in res.items()}


# ----------------------------------------------------------------------------- training targets
def layer(spans, k):
    """greedy layering into k non-overlapping channels (student v2): channel 1 keeps, in (start, longer-first)
    order, every span starting at or after the last kept end; rejects go to channel 2 by the same rule, etc.
    -> (channels [[(a, b, p)]], n dropped). Items may be (a, b) or (a, b, p)."""
    rest = sorted(spans, key=lambda x: (x[0], -x[1]))
    chans = []
    for _ in range(k):
        keep, nxt, last = [], [], -1
        for sp in rest:
            if sp[0] >= last:
                keep.append(sp)
                last = sp[1]
            else:
                nxt.append(sp)
        chans.append(keep)
        rest = nxt
    return chans, len(rest)


def bio(offs, spans):
    """char spans -> token BIO column (0 O, 1 B, 2 I); a token is in a span if their char ranges overlap"""
    lab = np.zeros(len(offs), np.int64)
    ends = [b for a, b in offs]
    for sp in spans:
        s, e = sp[0], sp[1]
        t = bisect.bisect_right(ends, s)
        first = True
        while t < len(offs) and offs[t][0] < e:
            if offs[t][1] > s:
                lab[t] = 1 if first else 2
                first = False
            t += 1
    return lab


def soft_bio(offs, spans):
    """char spans (a, b, p) -> soft targets [n_tok, 3]: in-span tokens get B (first) or I with prob p, O with 1 - p;
    other tokens are O with prob 1. Overlapping spans in one channel can't happen after layer()."""
    t3 = np.zeros((len(offs), 3), np.float32)
    t3[:, 0] = 1.0
    ends = [b for a, b in offs]
    for sp in spans:
        s, e = sp[0], sp[1]
        p = float(sp[2]) if len(sp) > 2 else 1.0
        t = bisect.bisect_right(ends, s)
        first = True
        while t < len(offs) and offs[t][0] < e:
            if offs[t][1] > s:
                t3[t] = 0.0
                t3[t, 0] = 1.0 - p
                t3[t, 1 if first else 2] = p
                first = False
            t += 1
    return t3


# ----------------------------------------------------------------------------- scoring
def span_f1(gold, pred):
    """lists of per-item span sets -> exact-match F1 pooled over items (1.0 when both are empty)"""
    tp = ng = npd = 0
    for g, p in zip(gold, pred):
        g, p = set(map(tuple, g)), set(map(tuple, p))
        tp += len(g & p)
        ng += len(g)
        npd += len(p)
    return round(2 * tp / (ng + npd), 6) if ng + npd else 1.0


def bootstrap_f1_diff(gold, a, b, n=1000, seed=0):
    """paired item bootstrap of F1(a) - F1(b) vs gold -> (lo, hi) 95%"""
    rng = np.random.default_rng(seed)
    m = len(gold)
    if m == 0:
        return 0.0, 0.0
    d = []
    for _ in range(n):
        ix = rng.integers(0, m, m)
        d.append(span_f1([gold[i] for i in ix], [a[i] for i in ix]) - span_f1([gold[i] for i in ix], [b[i] for i in ix]))
    return round(float(np.percentile(d, 2.5)), 6), round(float(np.percentile(d, 97.5)), 6)


def stats(v):
    v = np.asarray(v, np.float64)
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), "p50": round(float(np.percentile(v, 50)), 3), "p95": round(float(np.percentile(v, 95)), 3),
            "p99": round(float(np.percentile(v, 99)), 3), "mean": round(float(v.mean()), 3)}
