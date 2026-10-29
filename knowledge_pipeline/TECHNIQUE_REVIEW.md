# Is there a better CPU technique than ours?

**Verdict: the core method is right. Keep it; improve five things inside it.** LLM teachers labelling offline and a
small int8 encoder at inference is the standard way to get LLM-like extraction at CPU speed. Nothing we benchmarked
or surveyed beats it on speed at equal quality (T69: best zero-shot model, GLiNER bi-edge, entity overlap .72 vs our
.88 at 2.9× the time). The gains are in how we distill, how much we label, and how much text reaches the encoder.

## What to add, ranked by expected value

| # | Change | Why it should help | Evidence | Cost to test |
|---|---|---|---|---|
| 1 | **Two-stage distillation with soft labels.** LLM labels a few thousand items → fine-tune a large encoder (e.g. ModernBERT/Ettin-400M) on them → the large encoder labels 50–100k items with full probability distributions → train the small student on those soft targets | Soft targets carry more information per item than hard labels; a large encoder labels 100k items in GPU-minutes for $0 instead of API $; more data for the student | Hinton et al. 2015 (soft targets); TinyBERT, Jiao et al. 2020 (two-stage, large → small) | ~2–4 GPU-h on the 5090, $0 API |
| 2 | **Label far more data.** Our students saw ~1,000–1,900 labelled articles | Small students are usually data-limited; #1 makes 50k+ labels cheap | Our learning curve was still rising near 900 items (L325) | Comes with #1 |
| 3 | **One encoder, all heads** (spans, types, topic, POS, coreference merge) | Removes spaCy (57 of 228 ms) and avoids a second pass for topic | Measured stage times (T67, S5) | Part of student v3 |
| 4 | **A static-embedding triage tier** (Model2Vec-style: a transformer distilled into a lookup table) before the encoder | Sub-millisecond per item; skips items that don't need full extraction; the biggest lever toward 3,000–4,000/min | MinishLab Model2Vec (reports up to ~500× faster than the source model, lower accuracy) | CPU only; a router gated on recall |
| 5 | **Faster backbone** (Ettin-17M) | 0.57× encoder time per window on the same CPU | T69 measured; quality untested | Comes with v3 training |

**Also worth knowing:** for category heads with very few labels, SetFit (Tunstall et al. 2022) trains strong
classifiers from tens of examples per class. That's useful for new topics or conditions before the teacher pipeline
exists.

## What not to do (measured or clear-cut)

| Option | Why not |
|---|---|
| Zero-shot GLiNER / GLiNER2 at runtime | Slower and worse on our definition (T69); fine as a teacher or bootstrap |
| LLM at inference, even small | Breaks the cost and speed goal; keep LLMs for labels and novelty review |
| Bigger student | Each layer adds time; grow only while dev keeps improving |
| OpenVINO on CPUs without VNNI/AMX | No gain in fp32, slower in int8, can't load ORT-fused int8 (T69) |
| JavaScript or Rust runtime for server speed | Same ORT engine; use them for browser/edge and privacy, not throughput |
| More prompt rounds on a low-agreement layer | It's a definition problem (event nouns, judges agree at .38) |

## Proposed next experiment (as a task card)

T70 (`agentic/examples/T70-student-v3.card.json`) tests #3 and #5. Add a T71 card for #1 + #2: train an intermediate
large-encoder teacher on the existing consensus labels, label 50k MN-DS articles with soft targets on the local
5090, train the student on them, and compare against v2 on the frozen gold. Definition of done: every layer's lower
bound ≥ v2's point score, or the claim is "no gain".

Sources: Hinton, Vinyals, Dean 2015 https://arxiv.org/abs/1503.02531 · Jiao et al. 2020 (TinyBERT)
https://arxiv.org/abs/1909.10351 · Tunstall et al. 2022 (SetFit) https://arxiv.org/abs/2209.11055 · Model2Vec
https://github.com/MinishLab/model2vec · Ettin encoders https://huggingface.co/jhu-clsp
