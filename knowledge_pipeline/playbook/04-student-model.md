# 04 · Student model

**Goal:** the smallest model that meets the gates, with one forward pass serving every head.

## Rules

1. **Start small.** Our shipped student is a 4-layer, hidden-384 encoder initialised from MiniLM-L12 (19.2M
   params). Compare 2-, 4- and 6-layer variants; stop growing when dev gains stop. Larger is a teacher, not a student.
   Training is cheap: 8–13 minutes per student on a Kaggle T4.
2. **One encoder, many heads.** Token heads (BIO per layer) and sequence heads (topic) share the encoder. Each extra
   head costs milliseconds; each extra standalone model costs a full pass.
3. **Backbone candidates for speed.** Measured per 256-token window, int8, 1 thread: our MiniLM-derived student 77 ms,
   Ettin-17M 44 ms, Ettin-32M 117 ms (T69, same machine). Train the faster backbone and keep it only if dev quality
   holds.
4. **Long text by windows.** 254 tokens + [CLS]/[SEP], stride 192; each token takes the label from the window where
   it is most central. Decode BIO, then snap spans to word boundaries.
5. **Distillation recipe.** Hard labels from teacher consensus; optional soft targets when a teacher exposes scores.
   Class-weight rare layers. Fixed seeds; save dev curves.
6. **Pick on dev only.** Write the selection rule before seeing test scores (e.g. "max dev minimum-layer agreement,
   then lowest latency"). Score the pick once on gold.
7. **Replace pipeline glue with heads over time.** We still call spaCy for part-of-speech (57 ms of 228 per article);
   v3 learns POS as a head and drops spaCy.

## Done when

Dev curves and the selection rule are on the ledger, and the picked checkpoint is exported (chapter 05).
