# Word cascade: does it work?

2026-11-19. Evidence: ledger L2713–L2717. Live on the sim page, section 8b: http://localhost:8100/docs/notes/sim

## The idea
Every word the tools extract moves **sideways** (synonyms, siblings) and **up** (parents). Words whose chains cross **meet** in a group, at a layer. You get named, checkable structure from a human-built ontology instead of an embedding's guess.

## What we built
| Piece | Source | Example (article 101, "California sues OpenAI") |
|---|---|---|
| Sideways + up | WordNet | lawsuit → proceeding → due process |
| Meeting point | WordNet parents, ≤4 steps, layer ≥5 | lawsuit + sue meet at *proceeding* (layer 6) |
| Verb → event noun | WordNet derivation | sue → lawsuit, litigation, summons |
| Topic group | WordNet topic domain, IPTC | law = {action, file, law, lawsuit, …} |
| Places | GeoNames + WordNet part-of | Delaware, Florida, Texas → United States |

## Does it work? (600 MN-DS articles; same-story = same gold topic)
| Test | Cascade | Embedding (bge-small) | Verdict |
|---|---|---|---|
| Groups form | 89% of articles | — | Pass |
| Same story (shared name + meeting group) | 59%, on 3.4% of pairs | 86% on the same pairs | **Embedding wins** |
| Stricter groups (layer 7) | 59% | 95% | **Embedding wins** |
| Topic vote from topic groups | 14.7% | — | Fail (exact IPTC label: 46.7%) |
| Verbs with any group | 8.7% (22.8% via event noun) | — | Weak |
| Named reason for every link | Yes | No | **Cascade's value** |

## Why it fell short
1. **WordNet groups by kind, not situation.** A lawsuit *is a* proceeding, but it isn't linked to court, judge or plaintiff. News stories are the same when the situation matches, so the cascade misses that link.
2. **Generic meeting points.** Most crossings happen high up the tree (organism, activity, change).
3. **Names don't climb.** WordNet has no OpenAI or Bonta, and they are the "who".
4. **Choosing the meaning is noisy.** The definition-overlap rule switches 29% of words, and nobody has checked whether those switches are right.

## Approach or tool?
Both. The idea is sound: *lexical chains* (Morris & Hirst, 1991) did this on WordNet. But WordNet alone can't capture what happened. Each question needs its own structure:

| Question | Structure | Status |
|---|---|---|
| About what | WordNet + IPTC | Built |
| What happened (roles: plaintiff, defendant) | FrameNet / VerbNet; CAMEO for politics | Not on disk; licence to check |
| Who | Wikidata (types, parent organisation, country) | Waiting on the Wikidata query yes |
| Tone | SentiWordNet | Download needs a yes |

## Embedding landing on IPTC (L2718–L2719)
Each of IPTC's 1,059 active topics becomes one card: label, definition and parent path, embedded once with bge-small. The article lands on the nearest card at any depth. The IPTC file then supplies the path up, the siblings and the Wikidata link. Shown on the sim page, section 8c.

| Method (600 MN-DS, human labels) | Right top-level topic |
|---|---|
| Word matching (today) | 46.7% |
| Landing on the 17 top-level topics only | 42.5% |
| **Landing at any depth** | **53.7%** (in the best 3: 82%). Pass, +7.0 |
| + Wikidata alternative names on the cards | 51.5%. Fail |

Weakness: the single best landing can be wrong. On article 101 it lands on "human mishap"; law is 5th.

## Decision
- **Keep** the cascade as the explanation layer: it names the parent, the group and the layer behind each answer.
- **Don't** use it for similarity, topic or event type. Embeddings are better at similarity.
- **Next proof:** the "what happened" structure. Test verb → situation frame on real articles, measured against MAVEN (an event-type truth set).

## Needs your yes
1. Wikidata ID-join query (names).
2. MAVEN for scoring only.
3. A FrameNet or VerbNet download, once the licence is confirmed.
