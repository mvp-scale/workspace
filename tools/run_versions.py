#!/usr/bin/env python3
"""Versioned archive for the console's benchmark results. Nothing here deletes or edits a result.

Plain folders (data/probe-runs-v2/<id>-<set>, data/bench/<id>-<tier>, data/image-lab/runs/<id>/<task>)
always hold the CURRENT version and are what the pages read. The archive lives outside every discovery
folder:  data/run-versions/<kind>/<id>/<version>/<set-or-tier>/   (kind = probe-runs-v2 | bench | image-lab)

  run_versions.py snapshot [<id>|--all] [--dry-run]   copy current folders into the archive if that version is not archived yet
  run_versions.py prepare <id> <new-version>          archive, then move the plain folders aside so the runner re-runs
  run_versions.py diff <id> <old-version> <new-version|current>   accuracy change per set, paired exact McNemar + Wilson

Version = the resolved model version found in the run's own files (results "model", manifest resolved_models,
summary model_identities), e.g. jev-1.13.0. Aliases (jev-latest, the model id) and names without a version
number (Winnow-12B, clef-flash) have no version, so they are labelled unversioned-<finished date, UTC>.
"""
import argparse, hashlib, json, math, os, re, shutil, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("RV_ROOT", Path(__file__).resolve().parent.parent))
DATA = ROOT / "data"
ARCH = Path(os.environ.get("RV_ARCHIVE", DATA / "run-versions"))
SOURCES = {"probe-runs-v2": DATA / "probe-runs-v2", "bench": DATA / "bench", "image-lab": DATA / "image-lab" / "runs"}
DEFAULT_PREPARE_KINDS = ("probe-runs-v2", "bench")   # image-lab only with --kinds: the pages read one folder per model there
FRESH_S = 120                                         # a folder written to in the last 2 minutes may be a run in progress
VERSION_RE = re.compile(r"\d+\.\d+|(^|[-_])v\d+$")


# ---------- discovery ----------
def units(kind, only_id=None):
    """Yield (id, set, path) for every current run in a source."""
    src = SOURCES[kind]
    if not src.is_dir():
        return
    if kind == "image-lab":
        for m in sorted(src.iterdir()):
            if not m.is_dir() or (only_id and m.name != only_id):
                continue
            for e in sorted(m.iterdir()):
                yield m.name, e.name, e
        return
    for d in sorted(src.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or "-" not in d.name or not (d / "results.jsonl").exists():
            continue
        i, s = d.name.rsplit("-", 1)            # the leaderboard and /api/probes split on the last "-"
        if only_id and i != only_id:
            continue
        yield i, s, d


def read_json(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def files_of(path):
    path = Path(path)
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file())


def newest_mtime(path):
    return max([p.stat().st_mtime for p in files_of(path)] or [0])


def content_hash(path):
    """sha256 over relative names and bytes: equal hash = identical folder contents."""
    path = Path(path)
    h = hashlib.sha256()
    if path.is_file():
        h.update(b"F"); h.update(path.read_bytes()); return h.hexdigest()
    for f in files_of(path):
        h.update(str(f.relative_to(path)).encode() + b"\0")
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        h.update(b"\1")
    return h.hexdigest()


def model_strings(path):
    out = set()
    if Path(path).is_dir():
        man = read_json(Path(path) / "manifest.json") or {}
        out |= {str(x) for x in man.get("resolved_models") or []}
        summ = read_json(Path(path) / "summary.json") or {}
        out |= {str(x) for x in summ.get("model_identities") or []}
        try:
            with open(Path(path) / "results.jsonl") as fh:
                for line in fh:
                    try:
                        m = json.loads(line).get("model")
                    except Exception:
                        continue
                    if m:
                        out.add(str(m))
        except OSError:
            pass
    return out


def finished_date(path):
    man = read_json(Path(path) / "manifest.json") if Path(path).is_dir() else None
    fin = (man or {}).get("finished_utc")
    if fin:
        return fin[:10]
    return datetime.fromtimestamp(newest_mtime(path), timezone.utc).strftime("%Y-%m-%d")


def version_of(mid, path):
    concrete = sorted(m for m in model_strings(path) if VERSION_RE.search(m) and not m.endswith("-latest") and m != mid)
    return "+".join(concrete) if concrete else "unversioned-" + finished_date(path)


def norm_version(mid, v):
    """Accept '1.14.0' for 'jev-1.14.0'."""
    return v


# ---------- archive ----------
def adir(kind, mid, version, sset):
    return ARCH / kind / mid / version / sset


def load_index():
    f = ARCH / "index.jsonl"
    rows = []
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def add_index(row):
    ARCH.mkdir(parents=True, exist_ok=True)
    with open(ARCH / "index.jsonl", "a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def copy_in(src, dest):
    """Copy src to dest atomically (copy to a hidden sibling, verify the hash, rename). Returns the hash."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / (".tmp-" + dest.name + "-" + str(os.getpid()))
    if src.is_file():
        shutil.copy2(src, tmp)
    else:
        shutil.copytree(src, tmp)
    hs, ht = content_hash(src), content_hash(tmp)
    if hs != ht:
        raise RuntimeError(f"copy of {src} did not verify (left at {tmp}; delete by hand)")
    os.rename(tmp, dest)
    return hs


def snapshot_one(kind, mid, sset, path, dry=False):
    """Returns one of: archived, present, fresh, variant."""
    if time.time() - newest_mtime(path) < FRESH_S:
        return "fresh", None
    ver = version_of(mid, path)
    h = content_hash(path)
    base = adir(kind, mid, ver, sset)
    for r in load_index():
        if (r["kind"], r["id"], r["version"], r["set"], r["hash"]) == (kind, mid, ver, sset, h) and Path(r["archive"]).exists():
            return "present", ver
    dest, status = base, "archived"
    if base.exists():           # same version label but different content: keep both, never overwrite
        dest, status = base.parent / f"{sset}@{h[:12]}", "variant"
        if dest.exists():
            return "present", ver
    if dry:
        return status + "?", ver
    copy_in(path, dest)
    add_index({"kind": kind, "id": mid, "version": ver, "set": sset, "hash": h, "archive": str(dest), "source": str(path),
               "archived_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source_date": finished_date(path)})
    return status, ver


def cmd_snapshot(a):
    kinds = list(SOURCES)
    tally = {}
    for kind in kinds:
        for mid, sset, path in units(kind, None if a.all else a.id):
            st, ver = snapshot_one(kind, mid, sset, path, a.dry_run)
            tally[(kind, mid, ver, st)] = tally.get((kind, mid, ver, st), 0) + 1
    for (kind, mid, ver, st), n in sorted(tally.items(), key=lambda kv: tuple(map(str, kv[0]))):
        print(f"{st:10} {kind:14} {mid:18} {ver}  x{n}")
    if not tally:
        print("nothing to snapshot (no matching run folders)")


def cmd_prepare(a):
    kinds = a.kinds.split(",") if a.kinds else DEFAULT_PREPARE_KINDS
    plan = []
    for kind in kinds:
        for mid, sset, path in units(kind, a.id):
            plan.append((kind, mid, sset, path))
    if not plan:
        sys.exit(f"refuse: no current folders for id '{a.id}' in {', '.join(kinds)}")
    cur = {version_of(m, p) for _, m, _, p in plan}
    if a.new_version in cur or any(a.new_version == v.split("-", 1)[-1] for v in cur):
        sys.exit(f"refuse: the current folders already hold version {a.new_version} ({sorted(cur)}); nothing to prepare")
    # 1. archive everything current, 2. verify every archive copy against its plain folder, 3. only then move
    for kind, mid, sset, path in plan:
        st, _ = snapshot_one(kind, mid, sset, path)
        if st == "fresh":
            sys.exit(f"refuse: {path} was written in the last {FRESH_S}s (run in progress?)")
    checks = []
    for kind, mid, sset, path in plan:
        ver, h = version_of(mid, path), content_hash(path)
        hit = [r for r in load_index() if (r["kind"], r["id"], r["version"], r["set"], r["hash"]) == (kind, mid, ver, sset, h)]
        if not hit or not Path(hit[-1]["archive"]).exists() or content_hash(hit[-1]["archive"]) != h:
            sys.exit(f"refuse: archive copy of {path} does not verify identical")
        checks.append((kind, mid, sset, path, ver))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    moved = 0
    for kind, mid, sset, path, ver in checks:
        dest = ARCH / "_displaced" / kind / mid / stamp / sset
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            sys.exit(f"refuse: {dest} exists")
        shutil.move(str(path), str(dest))          # same filesystem: a rename; the verified copy stays in the archive
        moved += 1
    print(f"prepared {a.id} for {a.new_version}: {moved} folders archived and moved to {ARCH/'_displaced'}/<kind>/{a.id}/{stamp}/")
    print("the runner will now re-run them; afterwards: tools/run_versions.py diff", a.id, sorted(cur)[0], a.new_version)


# ---------- diff ----------
def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def load_results(path):
    rows = {}
    with open(Path(path) / "results.jsonl") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if "task_id" in r:
                rows[r["task_id"]] = bool(r.get("correct"))      # last row per task wins
    return rows


def dhash(path):
    for f in ("summary.json", "manifest.json"):
        d = read_json(Path(path) / f) or {}
        if d.get("dataset_hash"):
            return d["dataset_hash"]
    return None


def find_version(kind, mid, sset, version):
    """Path of the run of this version for this set: 'current' = the plain folder; else the newest archive entry."""
    if version == "current":
        for i, s, p in units(kind, mid):
            if s == sset:
                return p
        return None
    cands = [r for r in load_index() if r["kind"] == kind and r["id"] == mid and r["set"] == sset
             and (r["version"] == version or r["version"] == f"{mid}-{version}" or (version == "unversioned" and r["version"].startswith("unversioned"))) and Path(r["archive"]).exists()]
    return Path(cands[-1]["archive"]) if cands else None


def cmd_diff(a):
    rows, skipped = [], []
    for kind in ("probe-runs-v2", "bench"):
        sets = {s for _, s, _ in units(kind, a.id)} | {r["set"] for r in load_index() if r["kind"] == kind and r["id"] == a.id}
        for sset in sorted(sets):
            po, pn = find_version(kind, a.id, sset, a.old), find_version(kind, a.id, sset, a.new)
            if not po or not pn:
                skipped.append((kind, sset, "missing " + ("old" if not po else "new"))); continue
            ho, hn = dhash(po), dhash(pn)
            if not ho or ho != hn:
                skipped.append((kind, sset, "dataset_hash " + ("missing" if not ho or not hn else "differs"))); continue
            ro, rn = load_results(po), load_results(pn)
            ids = sorted(set(ro) & set(rn))
            b = sum(1 for t in ids if ro[t] and not rn[t])      # right before, wrong now
            c = sum(1 for t in ids if not ro[t] and rn[t])      # wrong before, right now
            ko, kn = sum(ro[t] for t in ids), sum(rn[t] for t in ids)
            n = len(ids)
            p = mcnemar_exact(b, c)
            rows.append({"kind": kind, "set": sset, "n": n, "n_old_only": len(set(ro) - set(rn)), "n_new_only": len(set(rn) - set(ro)),
                         "acc_old": round(ko / n, 4) if n else None, "acc_new": round(kn / n, 4) if n else None,
                         "delta_pts": round(100 * (kn - ko) / n, 2) if n else None,
                         "wilson_old": wilson(ko, n), "wilson_new": wilson(kn, n),
                         "worse_to_right": c, "right_to_wrong": b, "p_mcnemar_exact": round(p, 5), "beyond_chance_p05": p < 0.05,
                         "dataset_hash": ho[:12]})
    # pooled per kind over all sets (McNemar on the summed discordant pairs)
    pooled = []
    for kind in ("probe-runs-v2", "bench"):
        rs = [r for r in rows if r["kind"] == kind]
        if rs:
            n = sum(r["n"] for r in rs); b = sum(r["right_to_wrong"] for r in rs); c = sum(r["worse_to_right"] for r in rs)
            ko = sum(r["acc_old"] * r["n"] for r in rs); kn = sum(r["acc_new"] * r["n"] for r in rs)
            ko, kn = round(ko), round(kn); p = mcnemar_exact(b, c)
            pooled.append({"kind": kind, "sets": len(rs), "n": n, "acc_old": round(ko / n, 4), "acc_new": round(kn / n, 4),
                           "delta_pts": round(100 * (kn - ko) / n, 2), "wilson_old": wilson(ko, n), "wilson_new": wilson(kn, n),
                           "right_to_wrong": b, "worse_to_right": c, "p_mcnemar_exact": round(p, 5), "beyond_chance_p05": p < 0.05})
    # table
    print(f"{a.id}: {a.old} -> {a.new}  (paired on matched task_id, same dataset_hash; p = exact McNemar, two-sided)")
    print(f"{'kind':13} {'set':34} {'n':>5} {'old':>6} {'new':>6} {'delta':>7}  {'old 95% CI':>13} {'new 95% CI':>13} {'up/down':>7} {'p':>8}  beyond chance")
    for r in rows:
        ci = lambda w: f"{w[0]:.2f}-{w[1]:.2f}"
        print(f"{r['kind']:13} {r['set']:34} {r['n']:>5} {r['acc_old']*100:>5.1f}% {r['acc_new']*100:>5.1f}% {r['delta_pts']:>+6.1f}  {ci(r['wilson_old']):>13} {ci(r['wilson_new']):>13} {r['worse_to_right']:>3}/{r['right_to_wrong']:<3} {r['p_mcnemar_exact']:>8.4f}  {'YES' if r['beyond_chance_p05'] else 'no'}")
    for pl in pooled:
        print(f"POOLED {pl['kind']}: {pl['sets']} sets, n={pl['n']}, {pl['acc_old']*100:.1f}% -> {pl['acc_new']*100:.1f}% ({pl['delta_pts']:+.2f} pts), "
              f"+{pl['worse_to_right']}/-{pl['right_to_wrong']}, p={pl['p_mcnemar_exact']:.4f}, beyond chance: {'YES' if pl['beyond_chance_p05'] else 'no'}")
    n_yes = sum(r["beyond_chance_p05"] for r in rows)
    if rows:
        print(f"note: {n_yes} of {len(rows)} sets under p<0.05; with that many sets about {len(rows)*0.05:.1f} would pass by chance alone, so read the pooled line first")
    for k, s, why in skipped:
        print(f"skipped {k} {s}: {why}")
    if not rows or a.old == a.new:
        print("nothing comparable: no change record written")
        return
    out = ARCH / "changes" / f"{a.id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    hist = read_json(out) or {"id": a.id, "history": []}
    hist["history"].append({"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "old": a.old, "new": a.new,
                            "sets": rows, "pooled": pooled, "skipped": [list(s) for s in skipped]})
    out.write_text(json.dumps(hist, indent=1))
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("snapshot"); s.add_argument("id", nargs="?"); s.add_argument("--all", action="store_true"); s.add_argument("--dry-run", action="store_true")
    p = sp.add_parser("prepare"); p.add_argument("id"); p.add_argument("new_version"); p.add_argument("--kinds", help="comma list, default probe-runs-v2,bench")
    d = sp.add_parser("diff"); d.add_argument("id"); d.add_argument("old"); d.add_argument("new", nargs="?", default="current")
    a = ap.parse_args()
    if a.cmd == "snapshot" and not (a.all or a.id):
        ap.error("give an id or --all")
    {"snapshot": cmd_snapshot, "prepare": cmd_prepare, "diff": cmd_diff}[a.cmd](a)


if __name__ == "__main__":
    main()
