"""Track D PREPARATION (nothing uploaded, nothing run on a GPU, no network, no credentials read).
Builds runs/harvest/trackD_prep/bundle/ (train.jsonl + manifest.json + guard.py copy), scans it for anchor leakage,
and writes trackD_plan.json. CPU only.   python3 -I trackD_prep.py"""
import json, os, re, glob, hashlib, shutil, collections, pathlib
H = pathlib.Path(__file__).resolve().parent; os.chdir(H)
OUT = H / "runs/harvest/trackD_prep"; B = OUT / "bundle"; B.mkdir(parents=True, exist_ok=True)
J = lambda p: (json.loads(l) for l in open(p, encoding="utf-8") if l.strip())
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
sents = lambda t: [s for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", t)) if s]
# ---- texts
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool.setdefault(r["id"], r["text"])
# ---- held-out ids: never in the bundle
M = json.load(open("runs/pulse/ceiling/main_ids.json")); ids = M["ids"]; nt, nq = M["n_train"], M["n_devq"]
held = {"devq": set(ids[nt:nt + nq]), "old": set(ids[nt + nq:]),
        "sealed": {r["item_id"] for r in J("runs/pulse/sealed/labels.jsonl")}, "devq_labels": {r["item_id"] for r in J("runs/pulse/devq/labels.jsonl")},
        "dev2": set(open("runs/pulse/dev2_ids.txt").read().split()), "near_dups_of_frozen_test": set(open("runs/p4/exclude_near_dups_of_test.txt").read().split())}
for r in J("data/pilot300.jsonl"): held.setdefault("pilot300", set()).add(r.get("id") or r.get("item_id"))
allheld = set().union(*held.values())
# ---- full labels where the older label dirs hold them (needed for the which-condition head)
hk, sn = {}, {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl") + glob.glob("runs/p7/more*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl") + glob.glob("runs/pulse/tranche/c*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
# ---- label store grouped per item
per = collections.defaultdict(list); skipped = collections.Counter()
for r in J("runs/label_store/labels.jsonl"):
    per[r["item_id"]].append({k: r[k] for k in ("family", "model", "version", "topic", "story_type", "kinds", "n_conditions", "max_level")})
rows = []; teach = collections.Counter(); keep = set()
for i, labs in per.items():
    if i in allheld: skipped["held_out"] += 1; continue
    if i not in pool: skipped["no_text_on_file"] += 1; continue
    r = {"id": i, "text": pool[i], "split": "dev" if int(hashlib.sha256(i.encode()).hexdigest(), 16) % 20 == 0 else "train", "labels": labs}
    if i in sn: r["sonnet_full"] = sn[i]
    if i in hk: r["haiku_full"] = hk[i]
    rows.append(r); keep.add(i)
    for l in labs: teach[l["family"]] += 1
p = B / "train.jsonl"; p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
shutil.copy("/workspace/tools/kaggle/guard.py", B / "guard.py")
sonnet_items = sum(any(l["family"] == "sonnet" for l in r["labels"]) for r in rows)
# ---- pool overlap (toolchain pool_v1): the pool rows have no text and ids are cc:<url>; only overlapping ids can be joined
ov = {}
for r in J("runs/harvest/pool_v1/pool.jsonl"):
    if r["item_id"] in keep:
        c = collections.Counter(x["strength"] for x in r["items"]); ov[r["item_id"]] = dict(c)
(B / "pool_strengths_overlap.json").write_text(json.dumps(ov))
# ---- anchor leak scan
A = pathlib.Path("/workspace/data/anchors"); anchor_ids, anchor_sent, anchor_full, src_n = set(), set(), set(), collections.Counter()
def addS(t, tag, minw=8, whole_only=False):
    n = norm(t); anchor_full.add(n); src_n[tag] += 1
    for s in ([] if whole_only else sents(t)):
        k = norm(s)
        if len(k.split()) >= minw: anchor_sent.add(k)
for f in ("mn_ds/items_T28.jsonl", "mn_ds/items_T28b.jsonl", "maven_fact/items_T29.jsonl", "maven_fact/items_T33b.jsonl", "checkthat_subj/items_T30.jsonl"):
    for r in J(A / f): anchor_ids.add(r["id"]); addS(r["text"], f.split("/")[0] + "_items")
for r in J(A / "mn_ds/train.jsonl"):
    anchor_ids.add(r["id"]); addS(r["title"], "mn_ds_title", 8, True); addS(r.get("content") or "", "mn_ds_content")
for f in ("maven_fact/train.jsonl", "maven_fact/valid.jsonl"):
    for r in J(A / f):
        anchor_ids.add(r["id"])
        for s in r["tokens"]: addS(" ".join(s), "maven_sentence")
for f in ("checkthat_subj/train_en.tsv", "checkthat_subj/dev_en.tsv", "checkthat_subj/dev_test_en.tsv", "checkthat_subj/test_en_labeled.tsv"):
    for l in list(open(A / f, encoding="utf-8"))[1:]:
        c = l.rstrip("\n").split("\t"); anchor_ids.add(c[0]); addS(c[1], "checkthat_sentence")
for f in ("carb/dev.tsv", "carb/test.tsv"):
    for l in open(A / f, encoding="utf-8"): addS(l.split("\t")[0], "carb_sentence")
# re-read the bundle FROM DISK so the scan checks the real file
n_id = n_full = n_sent = n_title = 0; ex = []
title_only = {k for k in anchor_full if len(k.split()) >= 3}
for r in J(p):
    if r["id"] in anchor_ids: n_id += 1
    nt_ = norm(r["text"])
    if nt_ in anchor_full: n_full += 1; ex.append(r["id"])
    hit = [s for s in sents(r["text"]) if norm(s) in anchor_sent]
    if hit: n_sent += 1; ex.append(r["id"])
    head = norm(sents(r["text"])[0]) if sents(r["text"]) else ""
    if head and len(head.split()) >= 4 and head in anchor_full: n_title += 1; ex.append(r["id"])
raw = p.read_bytes().decode("utf-8", "ignore"); prefix_hits = {k: raw.count('"id": "' + k) for k in ("mn:", "mn2:", "mf:", "ct:")}
leak = {"anchor_sources_scanned": dict(src_n), "anchor_ids_loaded": len(anchor_ids), "anchor_sentences_8plus_words": len(anchor_sent),
        "checks": {"1_bundle_ids_equal_anchor_ids": n_id, "2_bundle_text_equals_anchor_text": n_full, "3_bundle_sentence_8plus_words_equals_anchor_sentence_or_title_equal_whole": n_sent,
                   "4_bundle_headline_equals_anchor_title_or_sentence": n_title, "5_raw_id_prefix_strings_in_file": prefix_hits,
                   "6_heldout_ids_in_bundle": len({r["id"] for r in J(p)} & allheld)},
        "flagged_example_ids": sorted(set(ex))[:20], "n_flagged_items": len(set(ex))}
(OUT / "leak_check.json").write_text(json.dumps(leak, indent=1))
man = {"rows": len(rows), "train": sum(r["split"] == "train" for r in rows), "dev": sum(r["split"] == "dev" for r in rows), "sonnet_items": sonnet_items,
       "items_with_sonnet_full_label": sum("sonnet_full" in r for r in rows), "items_with_haiku_full_label": sum("haiku_full" in r for r in rows),
       "label_rows_by_family": dict(teach), "skipped": dict(skipped), "held_out_sets": {k: len(v) for k, v in held.items()}, "held_out_union": len(allheld),
       "id_prefixes": dict(collections.Counter(r["id"].split(":")[0] for r in rows)), "pool_strength_overlap_items": len(ov),
       "files": {f.name: {"mb": round(f.stat().st_size / 1e6, 3), "sha256_16": hashlib.sha256(f.read_bytes()).hexdigest()[:16]} for f in sorted(B.iterdir())},
       "fields": ["id", "text", "split", "labels[family,model,version,topic,story_type,kinds,n_conditions,max_level]", "sonnet_full?", "haiku_full?"],
       "text_scope": "headline + short description only (what the reader sees); not full articles"}
(B / "manifest.json").write_text(json.dumps(man, indent=1)); print(json.dumps({"manifest": {k: v for k, v in man.items() if k != "fields"}, "leak": leak}, indent=1))
# ================= plan =================
def get(path, *keys):
    d = json.load(open(path))
    for k in keys: d = d[k]
    return d
W = "/workspace/knowledge_pipeline/projects/world-state/"
sealed = W + "runs/pulse/end2end_v6b-student_sealed.json"; devq = W + "runs/pulse/end2end_v6b-student_devq.json"; mn = W + "runs/pulse/anchor_mnds_fresh_v6b-student.json"; ct = W + "runs/pulse/anchor_checkthat_v6b-student.json"
M = json.load(open("runs/pulse/ceiling/main_ids.json")); old_train = set(M["ids"][:M["n_train"]]); new_items = len({r["id"] for r in J(p)} - old_train)
beat = {
 "story_type": {"sealed_agree_with_sonnet": [get(sealed, "story_type", "end_to_end_all", "rate"), get(sealed, "story_type", "end_to_end_all", "ci95"), sealed + "#story_type.end_to_end_all"], "devq": [get(devq, "story_type", "end_to_end_all", "rate"), devq + "#story_type.end_to_end_all.rate"], "always_fact_baseline": 0.845, "outside_anchor": "CheckThat subjectivity balanced accuracy %s %s (src: %s#primary_subj_is_opinion.balanced_accuracy)" % (get(ct, "primary_subj_is_opinion", "balanced_accuracy"), get(ct, "primary_subj_is_opinion", "ci95"), ct)},
 "topic": {"sealed_top2": [get(sealed, "topic_top2", "end_to_end_all", "rate"), get(sealed, "topic_top2", "end_to_end_all", "ci95"), sealed + "#topic_top2.end_to_end_all"], "sealed_top1": get(sealed, "topic_top1", "end_to_end_all", "rate"), "devq_top1": [get(devq, "topic_top1", "end_to_end_all", "rate"), devq + "#topic_top1.end_to_end_all.rate"], "devq_top2": get(devq, "topic_top2", "end_to_end_all", "rate"),
           "outside_anchor_mnds_fresh_top2": [get(mn, "top2_lenient_rate"), get(mn, "top2_lenient_ci95"), mn + "#top2_lenient_rate"], "mnds_top1": get(mn, "top1_lenient_rate")},
 "presence_and_which": {"status": "PARKED at the field gate (ledger L758); end to end %s vs always-no 0.891 (src: %s#condition_present.end_to_end_all.rate); finds %s of real cases" % (get(sealed, "condition_present", "end_to_end_all", "rate"), sealed, get(sealed, "chain_on_sonnet_positive_items", "reach_found", "rate")), "train_it": "yes (multi-task heads share the encoder) but it is not the decision head; no outside anchor for the listed-condition half"}}
plan = {
 "status": "PREPARATION ONLY. Nothing uploaded, no kaggle CLI or API call, no credential file read, no GPU, no hosted call, no web.",
 "1_what_to_train": {"model": "leaf student (mdbr-leaf-mt, 22.6M) fine-tuned with 4 linear heads (story, topic, presence, which-condition) + 5-fold cross-fitted soft targets from Qwen3-Embedding-4B heads; the v6b recipe (finetune_distill.py variant B, 16 epochs, lr 5e-5, 64 tokens)", "arms": {"A_existing_labels_now": "bundle as built; same recipe; changes only the data (+%d items not in v6b's 36,070 training items; label rows grown by Gemma v3b pool labels, more Sonnet)" % new_items, "B_with_gist_teacher_labels": "WAITS for Track C (not made). Adds gist labels; run only after they exist"}, "per_head_score_to_beat": beat,
   "rule6_check": "Playbook 15 rule 6 retrains at each 10,000 articles. Items beyond v6b's training set: %d (below 10,000), so arm A is early by the rule; arm B (Track C labels) is what makes it due." % new_items,
   "note_on_labels": "Mixed codebooks in the store: Haiku/Sonnet ws-v2-frozen, Sonnet/Gemma ws-v3b-nosize and older ws-w* versions. v6b used Sonnet where held (weight 3) else Haiku; Gemma 26B v3b labels exist for ~44k items. Which label wins per item is a DECISION for the owner (open: which codebook governs the pool)."},
 "2_bundle": {"path": str(B), "manifest": man, "leak_check_file": str(OUT / "leak_check.json"), "leak_check_result": leak, "excluded": "devq, old-1466, sealed, dev2, pilot300, near-dups of frozen test (union %d ids) and every anchor (MN-DS, MAVEN-FACT, CheckThat, CARB) - none is read into the bundle, only scanned against it" % len(allheld),
   "not_bundled": ["Qwen3-4B embeddings (recomputed on Kaggle; held-out rows would otherwise ship)", "toolchain pool_v1 (750 MB, tool spans only, ids cc:<url>, 3.0%% overlap with the label store; only %d overlapping rows' strength counts bundled)" % len(ov), "Track C gist labels (not made)"],
   "scan_limits": "exact normalised match of whole text, headline and sentences of 8+ words; id match; raw id-prefix strings. A paraphrase or a lightly edited copy would not be caught."},
 "3_kaggle_job": {"accelerator": "NVIDIA Tesla T4 (earlier kernels: machine_shape NvidiaTeslaT4, kernel-metadata.json in projects/world-state/kaggle_voter/kernel); one GPU used", "chunks": [
     {"chunk": "D1 embed", "what": "Qwen3-Embedding-4B (fp16, ~8 GB) embeds train+dev rows -> soft-target source", "guard": "max_min=45 idle_min=10"},
     {"chunk": "D2 train seed 0", "what": "finetune_distill.py recipe, 16 epochs, writes full-model state + heads", "guard": "max_min=50 idle_min=10"},
     {"chunk": "D3/D4 seeds 1,2", "what": "only if D2 shows a candidate gain locally; separate kernels", "guard": "max_min=50 each"}],
   "script": "reuse projects/world-state/finetune_distill.py (variant B) and ceiling_embed.py (qwen3-4b); wrap with tools/kaggle/guard.py (copied into bundle) as in kaggle_voter/kernel/ws-qwen-voter.py",
   "must_change": ["read the bundle train.jsonl instead of data/pool_train.jsonl + runs/p7*/ + tranche label globs", "no DEVQ/old eval inside the job (held-out rows are not shipped): drop run()'s eval half, score locally after download", "bf16 autocast -> fp16+GradScaler or fp32 (T4 has no native bf16; the 22.6M student fits fp32)", "replace kit/live heartbeat with guard.beat", "HF_HUB_OFFLINE: kernel needs internet or model datasets for mdbr-leaf-mt and Qwen3-Embedding-4B (earlier kernels set enable_internet true); licences of both NOT re-verified here", "save the full model state including the 384-to-1024 Dense projection (ledger L473 flaw)", "label choice: Sonnet-full where held else Haiku-full (v6b rule) or the owner's decision on Gemma v3b"],
   "outputs_to_download": ["student state .pt + head weights", "run log", "kaggle-runs.jsonl line via tools/kaggle/watch.sh"], "after_download_local_cpu": "build_v6_student.py <TAG> <VER> (ONNX export, stack, cuts), score_end2end.py on devq, then sealed ONCE, then MN-DS fresh and CheckThat scoring-only",
   "one_hour_rule": "No unattended job over 60 min (CLAUDE.md, playbook): every chunk guard max_min <= 50, arm a PID-verified stop, watch.sh max-minutes 60",
   "gpu_hours": {"measured_on_5090": {"qwen3-4b embeds 39,533 items": "196 s (src: runs/pulse/ceiling/embed.log)", "student B 16 epochs on 36,070 items": "239 s (src: runs/pulse/ceiling/finetune_t16e16lr5.log)"},
      "earlier_kaggle_t4_jobs": {"ws-qwen-voter retry": "0.50 h meter, hard stop at 30 min", "ws-ministral-voter": "0.26 h meter", "src": "/workspace/tools/kaggle/kaggle-runs.jsonl; ledger L581, L564; those were 14B vLLM inference, not student training"},
      "playbook_08": "students trained in 8-13 minutes each on a T4 in the first project (src: playbook/08-compute-and-runs.md line 8; different data and size)",
      "estimate_single_seed": "0.5 to 1.4 GPU-h (estimate: 5090 times scaled by an assumed 5 to 10x for T4 for D1 and D2, plus model download and boot; the T4 ratio for these two steps is NOT measured)",
      "estimate_three_seeds": "1.1 to 3.0 GPU-h (estimate)",
      "cap": "D12: 3 GPU-h total, 4 a week; 0.99 of 3 already used (ledger L581), so about 2.0 h remain; a three-seed plan can exceed it, so run one seed first or ask for a higher cap",
      "alternative": "same job on the local 5090 would take roughly 10 minutes (measured steps above) but needs the owner's yes for local GPU"}},
 "4_prediction_and_rule_DRAFT_for_owner": {
   "prediction": "Most likely no clear gain from arm A: ledger L624 (72k rows, more Sonnet) scored story 0.883 / topic 0.777 on devq, below v6b's 0.919 / 0.790, and L627 recorded that Sonnet label count is not the lever for story/topic at this recipe. Draft range for arm A on devq: story 0.90-0.925, topic top-1 0.77-0.80; MN-DS fresh top-2 0.78-0.82 (v6b 0.799). Arm B (gist labels) has no prior; predict nothing until Track C labels are measured.",
   "noise_ranges": {"devq_variants_same_seed_epoch_lr": "story 0.906-0.919, topic top-1 0.786-0.790 across finetune_e16lr5 / t16e16lr5 / t16e24lr5 (src: runs/pulse/ceiling/finetune_*.log)", "ci_half_widths": "sealed story 0.014, sealed topic top-2 0.014 (src: end2end_v6b-student_sealed.json); MN-DS fresh top-2 0.02 (src: anchor_mnds_fresh_v6b-student.json); CheckThat balanced accuracy 0.021", "seed_to_seed_variance": "NOT FOUND in the ledger or files for this recipe; a 3-seed run would measure it"},
   "decision_rule_draft": ["Step 1 (devq, local, no sealed): candidate counts only if story or topic top-1 rises >= 0.02 and neither falls > 0.01 (the rule used at L607) with a paired bootstrap lower bound > 0 against v6b-student on the same items.", "Step 2 (outside anchor, scoring only): GAIN = MN-DS fresh topic top-2 >= 0.819 (v6b 0.799 + its 0.02 half-width) AND CheckThat balanced accuracy >= 0.705 (v6b 0.684 + 0.021), paired bootstrap lower bound > 0 on the difference. Both short of that = no gain recorded, v6b stays.", "Step 3: sealed set scored ONCE for the one surviving candidate (as for v6b at L771); story >= 0.905 lower end, no field below v6b by > 0.01.", "Adopt only on owner's yes; the engine card/registration is a separate step (add-model skill, 'registered = all surfaces')."]},
 "5_risks_and_unverified": ["No T4 timing exists for the 4B embedding or the student fine-tune: the GPU-hour range is an estimate.", "Licences of mdbr-leaf-mt and Qwen3-Embedding-4B for the Kaggle kernel not re-read here (earlier cards said Apache-2.0 for Qwen3 voter models only).", "Label mix: codebook versions differ across rows (v2, v3b, w*); training on the mix is untested against v6b's Sonnet-else-Haiku rule; the 4,064 new Sonnet items are mostly v2/v3b.", "Gemma labels are a third family; whether to weight them is an owner decision.", "Leak scan is exact-match; the near-duplicate (paraphrase) risk to MN-DS (2019 news) is not excluded, though bundle ids are 2017-2018 cc, nq and nr items (publishers overlap not tested).", "Track C gist labels do not exist, so arm B cannot be prepared beyond the plan.", "The dev split in the bundle (5%) is for loss monitoring only; the real score runs locally on held-out rows.", "kaggle.env and the Kaggle CLI were not touched; dataset-metadata/kernel-metadata files for a push are NOT written here (they need the owner's account slug).", "bundle holds news text of third parties (headline + teaser) as before; upload would be to a PRIVATE dataset only, owner's yes first."]}
(OUT / "trackD_plan.json").write_text(json.dumps(plan, indent=1)); print("\nPLAN WRITTEN", OUT / "trackD_plan.json")
