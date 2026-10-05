# Embedding litmus test: pre-registered (written before any embedding result was computed)

Embedding model: minishlab/potion-base-8M (Model2Vec static embeddings, MIT, 256 dims, 30.2 MB). Truth: Winnow's direct P(try) for 400 seeded personas x 39 ideas
(17 Neighbour Loop variants, Nightfall, Gardenway, 20 varied ideas in offline.py DIVERSE). Evaluation = leave-one-idea-out over the 22 non-Neighbour-Loop ideas
(the Neighbour Loop family is always in training); pooled Pearson r over all held-out pairs, and mean within-idea r (does it rank personas right inside an idea).
PCA (k=8, fitted on persona texts and idea texts, no labels) reduces each embedding before an outer-product ridge model.

Models: A named (persona latents + demographic flags, x 10 LLM-read idea demands), B embedding (persona text embedding x idea text embedding),
C hybrid (named persona x idea embedding), D = A + B features. Controls: persona rows shuffled within each idea; idea-mean-only is not available for a held-out idea.

Expectations:
 T1 raw cosine(persona text, idea text) vs truth: counts as signal only if mean within-idea |r| >= 0.30.
 T2 B beats its shuffle control by >= 0.20 pooled r, otherwise the embedding carries no persona information.
 T3 D beats A by >= 0.05 pooled r, otherwise embeddings add nothing to the named layers.
 T4 B or C reaches at least A's pooled r on held-out ideas, otherwise embeddings cannot replace named layers for new idea kinds.
 Decision rule: T2 and T3 pass -> keep embeddings as a side channel. T4 also passes -> embeddings may stand in for hand-coded idea attributes.
 Caveats declared in advance: persona texts are templated, so embeddings may cluster by phrasing; 22 held-out ideas, one run, one seed; truth is the model, not people.

## Result (2026-10-02, one run)

Embedding 400 personas + 39 ideas took 0.30 s (256 dims, potion-base-8M, 30.2 MB weights).
T1 raw cosine: within-idea r mean +0.05, pooled r -0.18 -> no signal (similarity is not attraction).
Leave-one-idea-out, 22 held-out ideas (pooled r | within-idea r | MAE): A named x demands +0.62 | +0.51 | 0.232; B embed x embed +0.54 | +0.29 | 0.252;
C named x idea-embed +0.59 | +0.41 | 0.237; D = A+B +0.67 | +0.51 | 0.212. Shuffled-persona controls: pooled +0.47 to +0.50, within about 0.00.
T2 FAIL (B minus its shuffle = 0.07), T3 PASS only just (D minus A = 0.05), T4 FAIL (B +0.54, C +0.59 vs A +0.62).
Flaw in the pre-registered metric (found after seeing results, so exploratory): pooled r is dominated by differences between ideas, which the shuffled control keeps, so it cannot show persona signal.
The within-idea r can: B carries real persona signal (+0.29 vs +0.01 shuffled) but less than the named layers (+0.51); D adds nothing within an idea.
Reading: embeddings of templated persona text add no depth beyond the named layers here. The embedding of the IDEA text placed new ideas about as well as 10 LLM-read demands (C vs A pooled +0.59 vs +0.62), at about 1 ms instead of a model call.
Caveats: persona texts are templated and the named layers are the generator's own truth, so A is an upper bound; k=8 PCA; one run; truth is the model.
